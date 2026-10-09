# League ingestion engine

Python 3.10+, Pydantic v2, DuckDB or SQLite. Run every command below from
`repos/ingestion` unless stated otherwise.

**Current boundary:** `--prepare-pba` and `--import-pba` now automate cached game
retrieval, metadata extraction, normalization, and atomic staging/domain imports.
Player/team directory HTML and confirmed identity mappings are still required.
The player directory currently blocks direct retrieval from this environment.
No Alembic restructuring is needed for this workflow.

## Recommended PBA tournament workflow

From `repos/ingestion`, install and activate the environment as in step 1 below.

### Prepare and cache completed games

```sh
python ingest.py --prepare-pba \
  --tournament pba-50th-season-governors-cup \
  --work-dir data/pba-season50
```

This fetches the schedule and games explicitly marked Final, caches the original
HTML and structured records, and creates a persistent `identities.json` review file.
Requests are sequential with a one-second pause. Repeating preparation reuses the
cache and preserves reviewed identities. Use `--refresh` for a fresh snapshot or
`--limit 1` for a smoke run; a limited run is not a complete tournament import.
Completeness means all published Final links, not all historical games. Unmarked
or scheduled games are deliberately excluded even if their date is in the past.

### Load directory information and review identity matches

Save the loaded pages from `https://www.pba.ph/players` and
`https://www.pba.ph/teams` as HTML into the work directory. A Cloudflare challenge
page will not parse. No browser cookies are stored in code or the review file.

```sh
python ingest.py --prepare-pba \
  --tournament pba-50th-season-governors-cup \
  --work-dir data/pba-season50 \
  --players-html data/pba-season50/players.html \
  --teams-html data/pba-season50/teams.html
```

The directory parsers extract names, provider IDs from image paths, photos/logos,
team profile links, and commented player profile slugs. They populate the `players`
and `teams` catalogs, keyed by string provider ID, with UUIDs assigned once. These
image-path IDs are provider-specific candidates: confirm them during review.
Short names derived from the first initial are editable suggestions.

Match unambiguous directory entries before manual review:

```sh
python ingest.py --match-pba --work-dir data/pba-season50
```

This matches exact normalized team names and unique abbreviated-player-name plus
jersey combinations. Evidence is written to `identity-match-evidence.json`.
Existing matches are preserved. Jersey mismatches remain unresolved; matching a
current directory does not establish historical roster intervals. Duplicate cards
with identical full name/profile slug can use the single numeric photo-path ID.
Where a numeric ID is absent, the catalog uses `slug:<profile-slug>` as a clearly
namespaced source identifier, not an invented numeric person ID.

Edit `data/pba-season50/identities.json`:

- Set each `team_matches` value from null to a verified team catalog key, e.g.
  `"GIN": "4"` when supported by your roster/team evidence.
- Set each `player_matches` value from null to a verified player catalog key.
  Keys contain `[team code, jersey number, exact box-score name]`; they identify
  observations, not permanent players. Different observations can map to one player.
- Verify full names, short names, provider IDs, and UUIDs in the catalogs. You can
  supply the catalogs manually using the Player/Team schema fields if saved HTML is
  unavailable. Do not invent provider IDs or match on jersey number alone.
- If an observation could refer to more than one person over the selected games,
  do not approve it; the current match format needs a more specific scope first.
- The import creates one assumed roster membership for each player seen in a game.
  Its `valid_from` is the earliest imported game date and `valid_to` is empty;
  `source` is `pba-assumed` to distinguish this from verified roster history.
  A player's actual signing date may differ. Add a manual membership for a player
  in `roster_memberships` to override the assumption. Players appearing for more
  than one team require manual dated memberships before import.
- When importing into a populated database, use its existing UUIDs. New work folders
  assign new UUIDs; conflicting source mappings are rejected, not silently merged.

Keep and back up this file. It contains the reviewed identity work needed for
repeatable imports. Directory refreshes never overwrite existing catalog entries;
apply corrections explicitly. `data/` is ignored by Git.

### Normalize and import into either database

```sh
python ingest.py --import-pba --work-dir data/pba-season50 \
  --backend duckdb --database data/league.duckdb
```

For SQLite, use `--backend sqlite --database data/league.sqlite3`.
Unconfirmed mappings generate `unresolved.json` and stop before any database writes.
Successful normalization writes a reviewable `normalized.json` and imports the
selected games in one transaction, including staging rows/run metadata. A failure
rolls back both staging and normalized writes. Reimports reuse saved UUIDs and update
existing records; no game/player IDs are generated from names or jersey numbers.

The workflow fills leagues, tournaments, players, teams, tournament membership,
games, player game stats, official team game stats, source mappings, staging records,
and ingestion runs. Reviewed roster memberships are imported when supplied.
Game metadata includes venue, competition name, raw displayed date, period, clock,
scoreboard and quarter scores; dates remain unparsed until format/timezone is
confirmed. It cross-checks team totals against the scoreboard. Minutes above zero
mean played, explicit DNP means dnp, and zero/unknown minutes remain unknown.

Run all tests with `python -m unittest discover -s tests -v`. The manual workflow
below remains available for other sources and for preparing normalized input by hand.

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

Create all twelve tables:

```sh
python ingest.py --init-db --backend "$INGEST_BACKEND" --database "$INGEST_DATABASE"
```

Do not use the same file for both engines. Existing SQLite files are not migrated
to DuckDB. Initialization creates missing tables and adds a nullable `games.tournament_id` column
to older databases. Existing data is preserved; tournament links are not inferred.

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

Create `data/pba-normalized.json` with these ten top-level arrays:

```json
{
  "leagues": [],
  "tournaments": [],
  "players": [],
  "teams": [],
  "games": [],
  "game_statistics": [],
  "tournament_teams": [],
  "roster_memberships": [],
  "source_mappings": [],
  "team_game_statistics": []
}
```

First populate `leagues` and `tournaments`:

- **League:** `league_id` UUID, required `league_name`, optional `abbreviation`,
  `external_id`, `slug`, and `website_url`. For example, Philippine Basketball Association / PBA.
- **Tournament:** `tournament_id` UUID, required `league_id` and `tournament_name`,
  optional `season` (e.g. `"50"`), `external_id`, `slug`, and `source_url`.
  Create a separate tournament for each season/competition, e.g. Season 50 Governors’ Cup.
  Do not invent provider identifiers when unavailable; these external IDs are optional.

Populate the remaining arrays as follows. `examples/normalized.json` is a complete **fictional**
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
   Include `tournament_id` referencing the competition UUID, and `team_id_1` and `team_id_2` using the team UUIDs, plus string `external_id`
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

### 7. Import all ten normalized tables

After completing the reviewed file:

```sh
python ingest.py --normalized data/pba-normalized.json \
  --backend "$INGEST_BACKEND" --database "$INGEST_DATABASE"
```

The importer validates all rows, writes leagues before tournaments, then players/teams before tournament membership, rosters, games, stats, and source mappings,
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
    for table in ('records', 'ingestion_runs', 'leagues', 'tournaments', 'players', 'teams', 'games', 'game_statistics', 'tournament_teams', 'roster_memberships', 'source_mappings', 'team_game_statistics'):
        print(table, db.execute(f'SELECT count(*) FROM {table}').fetchone()[0])
    payload = json.loads(Path('data/pba-normalized.json').read_text())
    for table, keys in [('leagues', ('league_id',)), ('tournaments', ('tournament_id',)), ('players', ('player_id',)), ('teams', ('team_id',)),
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

To exercise all twelve tables without live retrieval or manual normalization, use a
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


## Leagues, seasons, and upgrading existing databases

Use `from ingestion.schemas import League, Tournament`. Both stores accept
`write_models(leagues=[...], tournaments=[...], players=[...], teams=[...],
games=[...], game_statistics=[...])`. All arrays are optional for incremental
imports, but referenced parent rows must already exist or be included in the batch.
League membership is recorded on tournaments; games link to tournaments. Players
and teams retain independent identities across competitions.

For an existing database, run step 2's `--init-db`, then import league/tournament
records and reimport the complete existing game records with `tournament_id` filled
in. Reuse every existing UUID and preserve optional values to avoid clearing them.
The legacy `games.tournament` string remains the provider slug for compatibility;
`tournament_id` is the normalized relationship. Legacy unlinked games are accepted;
new game inserts require `tournament_id` and tournament membership for both teams.

The database enforces tournament → league references; the store validates game →
tournament references inside the write transaction, like game-statistics → game.
Direct SQL can bypass that check. Live `--pba` staging and `--list-games` still use
`--tournament` as a provider slug; they do not automatically create league/tournament
UUIDs or normalize staging records. Other leagues need their own retrieval adapter.

A tournament is one competition in a season; `season` is a label, not a separate
season table. Tournament membership and dated roster history are now stored separately.


## Extended identity and statistics tables

The normalized file also accepts these arrays (see the updated complete
`examples/normalized.json`). They use the same transactional importer and both backends:

| Array / schema | Fields and identity |
| --- | --- |
| `tournament_teams` / `TournamentTeam` | Composite key `tournament_id`, `team_id`; register both teams before adding a game |
| `roster_memberships` / `RosterMembership` | `roster_id` UUID, `player_id`, `team_id`, `tournament_id`, required `valid_from`, optional `valid_to` and `jersey_number` |
| `source_mappings` / `SourceMapping` | Composite key `source`, `entity_type`, `scope`, `external_id`; target `internal_id` UUID |
| `team_game_statistics` / `TeamGameStatistics` | Composite key `game_id`, `team_id`; official team counting and shooting totals |

Roster dates are inclusive; leave `valid_to` null for an open interval. Overlapping
intervals for the same player within a tournament are rejected. Close a previous
interval before inserting a transfer/jersey change. The PBA workflow starts assumed
memberships on the first imported game date; this date is a proxy for season start.
Roster intervals support future
identity resolution; imports do not yet automatically reconcile player-game rows
against dated rosters or provider aliases.

Mapping entity types are `league`, `tournament`, `team`, `player`, `game`. Use a
stable provider name in `source`. `scope` defaults to an empty string; supply a
provider tournament slug when its IDs are not globally unique. Targets must exist.
A mapping cannot silently change its target; resolve identity corrections explicitly.
Legacy entity `external_id` fields remain for compatibility; mappings are the place
for multiple provider identities. Do not infer a provider match from equal numbers.

For every staged `team_game_stats` row, populate `team_game_statistics` using the
same flattened count/shooting mapping as player stats but without player names,
jersey numbers, starter flags, minutes_raw, or participation fields. Official team
totals include Team / Coach contributions and may differ from sums of player rows.

Game status must be `scheduled`, `live`, `final`, `postponed`, `cancelled`, or
`unknown`. Normalize provider text (e.g. `Final` → `final`) before importing.
Player `participation_status` must be `played`, `dnp`, `inactive`, or `unknown`.
Default is unknown; do not infer DNP merely from missing minutes. DNP/inactive rows
cannot have nonzero stats. Confirm participation before computing games played.

All normalized models accept `source`, `retrieved_at`, and `updated_at`.
Supply provenance when known; retrieval timestamps require a timezone. The store
sets `updated_at` in UTC on each write, including repeat imports. Legacy rows keep
unknown provenance as null rather than fabricated timestamps. These describe the
latest row, not a full audit history. Existing full-row replacement semantics apply.

The `player_tournament_statistics` view includes only final games and explicitly
played rows. It provides games played, total points, per-game points/rebounds/assists,
and a field-goal percentage calculated from summed makes and attempts (not mean
percentages). Missing shooting values yield a null percentage; zero attempts yield
null. Per-game averages use available non-null values. Other aggregates can follow
this same totals-first approach; source-reported percentages remain stored for comparison.

### Upgrade and populate the expanded design

1. Stop other database users, back up your database, and reinstall dependencies
   with `python -m pip install -e .`.
2. Run `python ingest.py --init-db --backend "$INGEST_BACKEND" --database "$INGEST_DATABASE"`.
   This adds missing tables/provenance/participation columns and recreates the
   aggregate view. It preserves existing data; old participation defaults to unknown.
3. Add tournament memberships, dated roster records, source mappings, and official
   team totals to the normalized JSON. Set source/retrieval times where verified.
4. Normalize game statuses and participation statuses. Link old games to tournaments
   by reimporting their full rows with the original UUIDs. Legacy unlinked games can
   still be updated without a tournament; new games cannot be inserted that way.
5. Rerun step 7, then inspect counts for the four additional arrays/tables. For a full
   completed-game import, check two team-total rows per game, both tournament-team
   memberships, and reviewed source mappings. Missing roster/mapping records are
   not automatically generated by ingestion.

Relationship checks for the four new tables are application-level and transactional.
Use the store for writes; direct SQL can bypass them. This accommodates DuckDB's
referenced-row update restrictions. Existing SQL keys still prevent duplicate rows.
