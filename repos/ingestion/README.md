# League ingestion engine

Python 3.10+, Pydantic v2, DuckDB or SQLite. Run every command below from
`repos/ingestion` unless stated otherwise.

**Current boundary:** PBA retrieval automatically fills `records` and
`ingestion_runs`. Filling `players`, `teams`, `games`, and `game_statistics` with
real data also requires a reviewed normalized JSON file. Automated player/team
retrieval, identity matching, and staging-to-domain conversion are not implemented.
Steps 5–6 below describe that manual preparation; there is no one-command live
import into all six tables yet.

## Full ingestion workflow

### 1. Install dependencies

From the repository root:

```sh
cd repos/ingestion
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
mkdir -p data
```

On subsequent sessions, activate `.venv` again. No Playwright is required.

### 2. Select and initialize a database

Choose **one** configuration. Keep these environment variables in the same terminal
for the remaining commands.

DuckDB:

```sh
export INGEST_BACKEND=duckdb
export INGEST_DATABASE=data/league.duckdb
```

SQLite:

```sh
export INGEST_BACKEND=sqlite
export INGEST_DATABASE=data/league.sqlite3
```

Create all six tables:

```sh
python ingest.py --init-db --backend "$INGEST_BACKEND" --database "$INGEST_DATABASE"
```

Do not use the same file for both engines. Existing SQLite files are not migrated
to DuckDB. Initialization creates missing tables; it does not migrate changed schemas.

### 3. Discover the published games

```sh
export INGEST_TOURNAMENT=pba-50th-season-governors-cup
python ingest.py --list-games --tournament "$INGEST_TOURNAMENT" > data/games.json
```

Check that this command succeeds before proceeding. The file contains objects with
`game_id`, `url`, `status`, and `teams`, not just an array of IDs. Discovery follows
the tournament's schedule links. IDs need not be consecutive. The inspected page
listed 50 Final games; that is not a guarantee of complete historical coverage.

### 4. Retrieve, clean, and stage all listed completed games

Run this block in the same terminal:

```sh
python - <<'PY'
import json
import os
from pathlib import Path
import subprocess
import sys
import time

schedule = json.loads(Path('data/games.json').read_text())
completed = [game for game in schedule if game['status'].strip().casefold() == 'final']
if not completed:
    raise SystemExit('No completed games found; inspect data/games.json')
for game in completed:
    print(f"Ingesting game {game['game_id']}", flush=True)
    subprocess.run([
        sys.executable, 'ingest.py', '--pba',
        '--tournament', os.environ['INGEST_TOURNAMENT'],
        '--game-id', str(game['game_id']),
        '--backend', os.environ['INGEST_BACKEND'],
        '--database', os.environ['INGEST_DATABASE'],
    ], check=True)
    time.sleep(1)
print(f'Staged {len(completed)} games')
PY
```

Each game commits separately. A failure stops the loop, retaining earlier successful
imports. Fix the failure and rerun; source/entity/external-ID keys update existing
records. Successful reruns add new run-history entries. No automatic retries occur.

The source fetches server-rendered box-score HTML with a 30-second timeout. The
cleaner handles integer counts, minutes as seconds, and shooting including four-point
shots. A missing/changed table or access challenge fails the game instead of silently
importing partial data. Team totals remain separate from player records.

### 5. Export staging records for normalization

```sh
python - <<'PY'
import json
import os
from pathlib import Path
import sqlite3

if os.environ['INGEST_BACKEND'] == 'duckdb':
    import duckdb
    db = duckdb.connect(os.environ['INGEST_DATABASE'], read_only=True)
else:
    db = sqlite3.connect(os.environ['INGEST_DATABASE'])
try:
    rows = db.execute('''
        SELECT entity, external_id, payload_json, raw_json
        FROM records WHERE source = ? ORDER BY entity, external_id
    ''', ['pba-actech']).fetchall()
    records = []
    for entity, external_id, payload, raw in rows:
        payload = json.loads(payload)
        if payload['tournament'] != os.environ['INGEST_TOURNAMENT']:
            continue
        records.append(dict(entity=entity, external_id=external_id,
                            payload=payload, raw=json.loads(raw)))
    Path('data/pba-staging.json').write_text(json.dumps(records, indent=2))
    print(f'Exported {len(records)} staged records')
finally:
    db.close()
PY
```

### 6. Prepare the real normalized dataset (manual step)

Create `data/pba-normalized.json` with these four top-level arrays:

```json
{
  "players": [],
  "teams": [],
  "games": [],
  "game_statistics": []
}
```

Populate the arrays as follows. `examples/normalized.json` is a complete **fictional**
example of the format, not real PBA data to import into your production database.

1. **Teams:** collect the team names and verified source identifiers. Assign one
   internal `team_id` UUID per team. Include `team_name`, string `external_id`, and
   optional `slug`, `profile_url`, and `logo_url`. Map box-score codes such as `GIN`
   to these UUIDs. Numeric logo-path IDs are source-specific candidates, not assumed
   equivalent to the box-score provider's identifiers.
2. **Players:** collect full names and source identifiers, assign one `player_id`
   UUID per player, and include required `player_name`, `player_short_name`, and
   string `external_id`. Optional fields are `slug` and `photo_url`. Match abbreviated
   box-score names using a reviewed roster, team, jersey, and game/season context.
   Do not use jersey numbers as permanent player identities or invent external IDs.
   Unresolved players must be resolved before declaring the import complete.
3. **Games:** assign one internal `game_id` UUID per tournament/provider game ID.
   Include `team_id_1` and `team_id_2` using the team UUIDs, plus string `external_id`
   (for example `"522"`), `tournament`, and available metadata. The staging payload
   includes tournament, numeric provider game ID, team code/name, and source URL.
   Competition name, venue, displayed date/time, period, clock, scoreboard, and
   quarter scores require manual extraction from the game page: the current parser
   does not capture those fields. Store the original displayed date in `date_time_raw`
   unless its format/timezone is verified. `scheduled_at`, if supplied, must have a
   timezone offset. Team order follows the page and does not imply home/away.
4. **Game statistics:** produce one row per staged `player_game_stats` record, using
   the resolved internal `game_id`, `player_id`, and `team_id`. Do not convert
   `team_game_stats` totals or Team / Coach rows into players. Use the mappings below.

Generate UUIDs once and save them in your normalized file/mapping records:

```sh
python -c 'from uuid import uuid4; print(uuid4())'
```

On later imports, look up existing UUIDs and reuse them. The store does not resolve
identities by name or external ID. Regenerating UUIDs would create duplicates.

#### Box-score to GameStatistics mapping

| Staged cleaned payload | Normalized field |
| --- | --- |
| `stats.player_name`, `stats.jersey_number`, `stats.position` | Same field names |
| `stats.seconds_played` | `seconds_played` |
| `stats.points`, `stats.offensive_rebounds`, `stats.defensive_rebounds`, `stats.rebounds` | Same field names |
| `stats.assists`, `stats.turnovers`, `stats.steals`, `stats.blocks` | Same field names |
| `stats.personal_fouls`, `stats.fouls_drawn`, `stats.plus_minus` | Same field names |
| `stats.field_goals.made/attempted/percentage` | `field_goals_made`, `field_goals_attempted`, `field_goals_percentage` |
| `stats.two_pointers.made/attempted/percentage` | `two_pointers_made`, `two_pointers_attempted`, `two_pointers_percentage` |
| `stats.three_pointers.made/attempted/percentage` | `three_pointers_made`, `three_pointers_attempted`, `three_pointers_percentage` |
| `stats.four_pointers.made/attempted/percentage` | `four_pointers_made`, `four_pointers_attempted`, `four_pointers_percentage` |
| `stats.free_throws.made/attempted/percentage` | `free_throws_made`, `free_throws_attempted`, `free_throws_percentage` |
| `section` | `is_starter`: true for starters, false for confirmed bench, null if unknown |
| Raw envelope `payload.stats.MINS` | `minutes_raw` |

Percentages use 0–100, not fractions. Preserve missing values as JSON `null` rather
than zero. Keep jersey numbers as strings (for example `"00"`). Provider game IDs
must be mapped to internal UUIDs rather than put directly into foreign-key fields.

### 7. Import all four normalized tables

After completing the reviewed file:

```sh
python ingest.py --normalized data/pba-normalized.json \
  --backend "$INGEST_BACKEND" --database "$INGEST_DATABASE"
```

The importer validates all rows, writes players and teams before games and stats,
and commits the normalized batch atomically. Any validation or database error rolls
back the batch. It prints counts for each array; these include updates, not just new
rows. Normalized imports do not add entries to `ingestion_runs`.

Updates replace complete rows. Omitted optional fields become NULL; preserve
existing values in your input file when they should remain unchanged.

### 8. Verify all tables and compare against your input

```sh
python - <<'PY'
import json
import os
import sqlite3
from pathlib import Path

if os.environ['INGEST_BACKEND'] == 'duckdb':
    import duckdb
    db = duckdb.connect(os.environ['INGEST_DATABASE'], read_only=True)
else:
    db = sqlite3.connect(os.environ['INGEST_DATABASE'])
try:
    for table in ('records', 'ingestion_runs', 'players', 'teams', 'games', 'game_statistics'):
        print(table, db.execute(f'SELECT count(*) FROM {table}').fetchone()[0])
    payload = json.loads(Path('data/pba-normalized.json').read_text())
    for table, keys in [('players', ('player_id',)), ('teams', ('team_id',)),
                        ('games', ('game_id',)), ('game_statistics', ('game_id', 'player_id'))]:
        assert payload[table], f'{table} input is empty'
        for row in payload[table]:
            where = ' AND '.join(f'{key} = ?' for key in keys)
            assert db.execute(f'SELECT count(*) FROM {table} WHERE {where}',
                              [row[key] for key in keys]).fetchone()[0] == 1
    staged = json.loads(Path('data/pba-staging.json').read_text())
    player_rows = [r for r in staged if r['entity'] == 'player_game_stats']
    assert len(payload['game_statistics']) == len(player_rows), 'Unmapped or extra player stat rows'
    expected_games = {r['payload']['game_id'] for r in player_rows}
    assert {str(g['external_id']) for g in payload['games']} == {str(i) for i in expected_games}
    print('All normalized input keys exist; game and player-row coverage checks passed.')
finally:
    db.close()
PY
```

These checks confirm presence and counts, not the correctness of identity matching.
Review per-game player totals against the published team totals and spot-check
shooting and minutes. Team rebounds or turnovers may include Team / Coach values,
so player sums need not equal every team aggregate.

## Offline smoke run (fictional data)

To exercise all six tables without live retrieval or manual normalization, use a
separate demo database after step 1:

```sh
python ingest.py --backend duckdb --database data/demo.duckdb --init-db
python ingest.py --backend duckdb --database data/demo.duckdb --input examples/demo.json --source demo
python ingest.py --backend duckdb --database data/demo.duckdb --normalized examples/normalized.json
```

For SQLite change all three commands to `--backend sqlite --database data/demo.sqlite3`.
The staging demo and normalized demo are independent fixtures; this is a storage
smoke check, not a demonstration of automatic staging-to-domain conversion.

## Storage and extension notes

- Schemas are in `src/ingestion/schemas/`. SQL definitions are in
  `src/ingestion/sql/001_initial.sql` and `sqlite_initial.sql`.
- DuckDB uses UUIDs, TIMESTAMPTZ, and integer arrays. SQLite uses text UUIDs,
  ISO timestamp strings, and JSON text arrays.
- Database primary keys and team/player foreign keys are enforced. Game-statistics
  game references and team participation are validated by the store in the transaction,
  not by a game SQL foreign key, to accommodate DuckDB referenced-row update limits.
  Direct SQL writes can bypass these application checks.
- Use one writer process. Close ingestion before opening DuckDB in another process.
- `records` retains latest raw and cleaned structured data, not HTML or versioned
  source history. Successful staging runs are recorded; failed runs are logged.
- No automatic deletion, historical roster resolution, schema migrations,
  scheduling, or retries are implemented.
- New API/scraper adapters implement `Source.fetch()` from `contracts.py` and yield
  `RawRecord` objects. Source-specific cleaners implement `Cleaner`; storage implements
  `Store`. Adapters own pagination, timeouts, authentication, and resource cleanup.
- `repos/datasource/pba/scraper.py` is an optional JSON exporter using the same PBA
  parser. It is not required for database ingestion.

## Tests

From the activated environment in `repos/ingestion`:

```sh
python -m unittest discover -s tests -v
python ingest.py --help
```
