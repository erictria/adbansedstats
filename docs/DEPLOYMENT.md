# Deployment runbook

This runbook describes the first production deployment: one Ubuntu VM, a
persistent local DuckDB file, Banse as a `systemd` service, a built static UI
served by Caddy, and a timer that prepares new PBA games for review. Replace
`stats.example.com`, `deploy`, and the Git remote with your own values. Paths
below assume the project checkout is `/srv/adbansedstats/app` and persistent
data is `/srv/adbansedstats/data`.

This is a deployment procedure, not a claim that the ingestion workflow is
fully unattended. New player or team identities can still require review before
an import. See the [ingestion guide](../repos/ingestion/README.md).

## Architecture and prerequisites

```text
Browser -- HTTPS --> Caddy -- /api/* --> Banse (127.0.0.1:8000)
                       |
                       +-- static --> repos/ui/dist

systemd timer --> PBA prepare job --> reviewed work files
                                       |
                                manual import --> DuckDB
                                                     |
                                                  Banse reads
```

Use a VM with a persistent **local** disk. Keep `/srv/adbansedstats/data` outside
the Git checkout and back it up separately. Banse opens DuckDB read only for each
request. DuckDB's normal file access allows multiple read-only processes or one
read/write process; do not run the importer against the live file while Banse is
serving it. [DuckDB concurrency](https://duckdb.org/docs/current/connect/concurrency)

Before starting, have:

- A Linux VM with SSH access, DNS pointing `stats.example.com` to it, and inbound
  ports 80 and 443 open. Keep port 8000 private; Banse binds to loopback.
- Git, Python 3.10+ with `venv` and `pip`, and Node.js 22.12+ with npm available
  for the initial build. Install Caddy using its
  [official Ubuntu instructions](https://caddyserver.com/docs/install).
- A Git checkout or deploy method for the code, and a way to transfer the
  existing local `repos/ingestion/data` directory. It is ignored by Git and
  contains the database plus reviewed identity mappings.

Do not use `make dev` or the Vite development server as production supervisors.
`make setup` and `make dev` remain convenient local commands; PDM is not needed
to keep production processes alive.

## 1. Create the service account and directories

On the VM, create an unprivileged account and the expected directory layout:

```sh
sudo useradd --system --create-home --home-dir /srv/adbansedstats \
  --shell /usr/sbin/nologin adbansedstats
sudo install -d -o adbansedstats -g adbansedstats -m 0755 \
  /srv/adbansedstats/data
```

Place the Git checkout in `/srv/adbansedstats/app` and make it owned by
`adbansedstats`. For example, after configuring a read-only deploy key for that
account, run this on the VM (replace the remote):

```sh
sudo -H -u adbansedstats git clone \
  git@github.com:YOUR_ORG/adbansedstats.git /srv/adbansedstats/app
```

Alternatively, copy a checkout from your laptop with `rsync`. Do not put
credentials in the repository. Verify the checkout contains `repos/banse`,
`repos/ui`, and `repos/ingestion`.

## 2. Put the existing data on the VM

The current local database and `pba-season50/identities.json` are not committed.
Transfer the **contents** of local `repos/ingestion/data/` to
`/srv/adbansedstats/data/`. For example, from the project root on your laptop:

```sh
rsync -av repos/ingestion/data/ deploy@SERVER:~/adbansedstats-data/
```

Then on the VM (substitute the actual SSH user's home path):

```sh
sudo rsync -a /home/deploy/adbansedstats-data/ /srv/adbansedstats/data/
sudo chown -R adbansedstats:adbansedstats /srv/adbansedstats/data
sudo test -f /srv/adbansedstats/data/league.duckdb
sudo test -f /srv/adbansedstats/data/pba-season50/identities.json
```

If this is a new environment without a database, follow the
[ingestion workflow](../repos/ingestion/README.md) to build one before starting
Banse. Keep the cached HTML and identity review files; new imports depend on the
stable UUID mappings in `identities.json`.

## 3. Install Banse and ingestion

Check `python3 --version` first; use an explicit newer interpreter if the VM's
default is below 3.10. Create separate virtual environments:

```sh
sudo -u adbansedstats python3 -m venv /srv/adbansedstats/app/repos/banse/.venv
sudo -u adbansedstats /srv/adbansedstats/app/repos/banse/.venv/bin/python \
  -m pip install -e /srv/adbansedstats/app/repos/banse

sudo -u adbansedstats python3 -m venv /srv/adbansedstats/app/repos/ingestion/.venv
sudo -u adbansedstats /srv/adbansedstats/app/repos/ingestion/.venv/bin/python \
  -m pip install -e /srv/adbansedstats/app/repos/ingestion
```

Confirm Banse can read the database before registering the service:

```sh
sudo -u adbansedstats /srv/adbansedstats/app/repos/banse/.venv/bin/python -c \
  'from banse.service.data import open_database, tournaments; c = open_database("/srv/adbansedstats/data/league.duckdb"); print(tournaments(c)); c.close()'
```

## 4. Build and serve the UI

Build with Node.js 22.12+ (check `node --version`). The browser code calls
same-origin `/api` by default, which Caddy will proxy to Banse:

```sh
sudo -H -u adbansedstats sh -c \
  'cd /srv/adbansedstats/app/repos/ui && npm ci && npm run build'
```

The result is `repos/ui/dist/`; no Node process is needed to serve it in
production. [Vite static deployment](https://vite.dev/guide/static-deploy.html)

Put this in `/etc/caddy/Caddyfile`, replacing the domain:

```caddyfile
stats.example.com {
    root * /srv/adbansedstats/app/repos/ui/dist
    reverse_proxy /api/* 127.0.0.1:8000
    file_server
}
```

Caddy must be able to traverse the parent directories and read `dist`. Point
DNS at the VM and allow ports 80/443 so Caddy can serve HTTPS. The `/api` path
is passed through unchanged; Banse expects that prefix. The UI uses hash routes,
so a server-side page rewrite is unnecessary. This static/proxy pattern follows
the [Caddy documentation](https://caddyserver.com/docs/caddyfile/patterns).

```sh
sudo caddy validate --config /etc/caddy/Caddyfile
sudo systemctl reload caddy
```

Only `/api/*` is publicly proxied. FastAPI's `/docs` and `/openapi.json` remain
accessible locally on the VM or through an SSH tunnel, if you need them.

## 5. Run Banse as a service

Create `/etc/systemd/system/banse.service`:

```ini
[Unit]
Description=Banse basketball statistics API
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=adbansedstats
Group=adbansedstats
WorkingDirectory=/srv/adbansedstats/app
ExecStart=/srv/adbansedstats/app/repos/banse/.venv/bin/banse --database /srv/adbansedstats/data/league.duckdb --host 127.0.0.1 --port 8000
Restart=on-failure
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

Enable it and check both the API and the public site:

```sh
sudo systemctl daemon-reload
sudo systemctl enable --now banse
sudo systemctl status banse
curl -fsS http://127.0.0.1:8000/api/tournaments
curl -fsS https://stats.example.com/api/tournaments
```

Open `https://stats.example.com` and follow a player and team link. The current
`/api/health` endpoint only reports that the FastAPI process is responding; use
`/api/tournaments` when checking that DuckDB is readable. Inspect failures with
`journalctl -u banse -n 100 --no-pager`.

## 6. Schedule retrieval, then review and import

For now, schedule **preparation only**. It refreshes the PBA schedule and saved
final game pages, but does not write DuckDB. The player directory may still need
manual HTML capture, and new box-score names may need reviewed identity matches.
Airflow would not remove that review step.

Create `/etc/systemd/system/adbansedstats-prepare.service`:

```ini
[Unit]
Description=Prepare PBA final games for review
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=adbansedstats
Group=adbansedstats
WorkingDirectory=/srv/adbansedstats/app/repos/ingestion
ExecStart=/srv/adbansedstats/app/repos/ingestion/.venv/bin/python /srv/adbansedstats/app/repos/ingestion/ingest.py --prepare-pba --tournament pba-50th-season-governors-cup --work-dir /srv/adbansedstats/data/pba-season50 --refresh
```

Create `/etc/systemd/system/adbansedstats-prepare.timer`:

```ini
[Unit]
Description=Daily PBA retrieval

[Timer]
OnCalendar=*-*-* 02:00:00 UTC
Persistent=true

[Install]
WantedBy=timers.target
```

The example runs at 02:00 UTC; change it to suit the source's publication time.
`Persistent=true` catches up once after downtime. [systemd timer manual](https://man7.org/linux/man-pages/man5/systemd.timer.5.html)

```sh
sudo systemctl daemon-reload
sudo systemctl enable --now adbansedstats-prepare.timer
systemctl list-timers adbansedstats-prepare.timer
sudo systemctl start adbansedstats-prepare.service   # manual test
journalctl -u adbansedstats-prepare.service -n 100 --no-pager
```

After new games arrive:

1. Refresh `players.html` and `teams.html` in the work directory if the
   directories changed, then rerun `--prepare-pba` with `--players-html` and
   `--teams-html` as described in the ingestion guide.
2. Run the directory matcher, then review `identities.json`,
   `identity-match-evidence.json`, and any `unresolved.json`. Confirm new
   identities before import. Do not let a scheduled job guess them.
3. Back up the current database, stop Banse, run the import, restart Banse, and
   verify `/api/tournaments` plus game/player counts. The importer writes one
   transaction and can be rerun with the reviewed UUIDs.

Example import commands, run on the VM **after** identity review:

```sh
sudo -H -u adbansedstats /srv/adbansedstats/app/repos/ingestion/.venv/bin/python \
  /srv/adbansedstats/app/repos/ingestion/ingest.py --match-pba \
  --work-dir /srv/adbansedstats/data/pba-season50

sudo systemctl stop banse
sudo -u adbansedstats cp -p /srv/adbansedstats/data/league.duckdb \
  /srv/adbansedstats/data/league.duckdb.pre-import
sudo -u adbansedstats /srv/adbansedstats/app/repos/ingestion/.venv/bin/python \
  /srv/adbansedstats/app/repos/ingestion/ingest.py --import-pba \
  --work-dir /srv/adbansedstats/data/pba-season50 \
  --backend duckdb --database /srv/adbansedstats/data/league.duckdb
sudo systemctl start banse
curl -fsS http://127.0.0.1:8000/api/tournaments
```

**Restart Banse even if the import fails.** Then inspect the importer output,
`unresolved.json`, and the service logs. Do not delete the pre-import copy until
the result has been checked. To roll back, stop Banse, restore the copy over
`league.duckdb`, start Banse, and repeat the API checks.

## 7. Backups, updates, and monitoring

Back up both the DuckDB file and the whole `pba-season50` work directory to a
**different machine or object store** after an import completes and its writer
connection closes. Include `identities.json`, cached source HTML, and review
evidence. Keep dated versions and test a restore. A second copy on the same VM
helps immediate rollback but is not an off-host backup. Do not back up while
ingestion is writing the file.

For code updates, run the Banse and ingestion test suites, update the checkout,
reinstall Python dependencies if their `pyproject.toml` files changed, rebuild
the UI (`npm ci && npm run build`), then `sudo systemctl restart banse`. Check
the public UI and `/api/tournaments` again. Use `journalctl -u banse -f` and the
prepare-service journal for errors; add alerts for failed timer runs and backup
failures before relying on unattended operation.

`make dev` remains for local development. If you later deploy with Docker, keep
DuckDB and the reviewed work files on persistent host storage or a volume, and
preserve the exclusive writer/readers sequence. Docker packages processes; it
does not turn DuckDB into a multi-writer database. See
[Docker volumes](https://docs.docker.com/engine/storage/volumes/).

Airflow is a later option if you add enough leagues, sources, dependent tasks,
backfills, and run monitoring to justify its scheduler, DAG processor, API
server, and metadata database. [Airflow architecture](https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/overview.html)
