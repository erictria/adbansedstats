# Banse data API

Read-only FastAPI service for the DuckDB database populated by `repos/ingestion`.
Requires Python 3.10+. Check the interpreter version before creating the virtual
environment; on this Mac, Homebrew provides `python3.14`. The API opens a read-only database connection for each request,
so stop the API before an ingestion run if DuckDB reports a file lock.

```sh
cd repos/banse
python3.14 --version
python3.14 -m venv .venv
source .venv/bin/activate
python --version
python -m pip install -e .
banse --database ../ingestion/data/league.duckdb
```

If `.venv` was created with Python 3.9, deactivate it and recreate it with
`python3.14 -m venv --clear .venv` before activating it again. The pip upgrade
warning is unrelated to the Python version error.

The default address is `http://127.0.0.1:8000`. FastAPI's interactive API docs
are at <http://127.0.0.1:8000/docs>. From the repo root, an environment with
Banse's dependencies can run `PYTHONPATH=repos/banse/src python -m banse.server`.
For a UI hosted on another origin, start Banse with `--cors-origin https://your-ui-host`.
The `banse` command starts Uvicorn; `--host`, `--port`, and `--database` still work.

Routes:

- `GET /api/health`
- `GET /api/tournaments`
- `GET /api/overview?tournament_id=<uuid>`
- `GET /api/players?tournament_id=<uuid>` and `GET /api/players/<uuid>?tournament_id=<uuid>`
- `GET /api/teams?tournament_id=<uuid>` and `GET /api/teams/<uuid>?tournament_id=<uuid>`
- `GET /api/games?tournament_id=<uuid>` and `GET /api/games/<uuid>?tournament_id=<uuid>`

Player totals aggregate games where participation is `played`. Team records come
from final game scores. The player and team profile routes include game logs and
rosters; game details include the player box score. Tournament IDs scope every
statistics query. Start `repos/ui` separately; its Vite proxy sends `/api` requests
to this server.

FastAPI returns HTTP 422 for missing or malformed UUID parameters, and HTTP 404
for a valid UUID that has no record in the selected tournament.

To run the API tests, install `python -m pip install -e '.[test]'` from this
directory and run `python -m unittest discover -s tests`.
