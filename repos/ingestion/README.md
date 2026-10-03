# League ingestion engine

Python 3.10+ scaffold for retrieving league data, cleaning records, and persisting
it. Domain schemas use Pydantic v2. SQLite is the initial
storage implementation; sources and storage can be replaced independently.
No live API or scraper is connected yet.

## Run locally

From the repository root:

```sh
cd repos/ingestion
PYTHONPATH=src python3 -m ingestion --source demo --input examples/demo.json
```

This imports two fictional records into `data/league.sqlite3`. Rerunning updates
those records instead of duplicating them. Override the path with
`--database /path/to/league.sqlite3`. Paths are relative to your working directory.
Logs go to stderr, a JSON run summary goes to stdout, and failures exit nonzero.

Optional isolated installation:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
league-ingest --source demo --input examples/demo.json
```

## Pipeline

1. `Source.fetch()` retrieves and yields `RawRecord` objects.
2. A `Cleaner` maps each raw record into a validated `CleanRecord`.
3. `IngestionEngine` rejects duplicate entity/ID pairs within a batch.
4. A `Store` atomically saves the batch and successful-run metadata.

The default cleaner trims strings and object keys recursively and validates
JSON-compatible payloads. It rejects empty identifiers, key collisions, and
non-finite numbers. It deliberately preserves numeric strings and empty strings:
source-specific cleaners must define numeric conversion, missing-value handling,
date formats, units, and basketball validation rules.

## Add an API or scraper

Create a module under `src/ingestion/sources/` implementing the `Source` protocol
in `contracts.py`. Both retrieval methods use the same contract:

```python
from ingestion.models import RawRecord

class LeagueSource:
    name = 'league-provider-dataset'

    def fetch(self):
        # Retrieve through your chosen API client or scraping implementation.
        # Yield one record for each item retrieved.
        yield RawRecord(
            entity='player',
            external_id='provider-player-id',
            payload={'name': 'Example player'},
        )
```

The example above is illustrative, not a live adapter. Each real adapter owns
credentials (read from environment variables), pagination, request timeouts,
rate limits, retries, and cleanup of browsers or HTTP clients. Raise on incomplete
retrieval rather than silently yielding a partial dataset. Do not log credentials.

Wire an adapter and optional source-specific cleaner into the engine:

```python
from pathlib import Path
from ingestion.cleaning import DefaultCleaner
from ingestion.engine import IngestionEngine
from ingestion.storage import SQLiteStore

engine = IngestionEngine(DefaultCleaner(), SQLiteStore(Path('data/league.sqlite3')))
result = engine.run(LeagueSource())
```

The existing PBA scraper in `repos/datasource/pba/` is left independent until its
retrieval and parsing are finalized. A future adapter can convert its output to
`RawRecord` objects. Add retrieval dependencies to `pyproject.toml` when selected.

## Storage and identity

`records` holds source, entity, external ID, cleaned JSON, the latest raw envelope,
UTC update time, and run ID. Its primary key is `(source, entity, external_id)`.
Choose stable source names and IDs. For game/season stats, include the relevant
game/season scope in the external ID. IDs from different providers remain separate;
cross-provider identity matching is not implemented.

`ingestion_runs` tracks successful runs and the number of records written, including
updates. Failed runs are logged but not persisted. Raw JSON is the latest structured
source record, not the original HTML/HTTP response or a versioned archive.

All retrieval and cleaning finishes before database writes begin. SQL writes roll
back together on failure. Batches are held in memory; streaming/checkpoints,
scheduling, concurrent workers, schema migrations, and normalized basketball tables
are future work. Missing records are not automatically deleted. A future database
implementation can replace `SQLiteStore` through the `Store` protocol.

## Verify

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Tests cover cleaning, raw preservation, repeat imports, source isolation, invalid
batches, retrieval failures, and transaction rollback.

## PBA HTTP ingestion

From `repos/ingestion`:

```sh
PYTHONPATH=src python3 -m ingestion --pba \
  --tournament pba-50th-season-governors-cup --game-id 522
```

Fetches server-rendered HTML from `https://pba-api01.actech2.com` with a 30-second
request timeout. No browser or extra dependencies are required. Both team tables
must be present and match the expected columns. Player rows and team totals are
separate records; section headers and Team / Coach rows are not player records.

Raw envelopes preserve table strings. The PBA cleaner converts counts to integers,
minutes to seconds, and shooting to made/attempted/percentage fields, including
four-pointers. Percentages use a 0–100 scale; missing values become null.
IDs combine tournament, game ID, team code, and jersey number (or `totals`). These
are game-row identities, not cross-game player identities. Reimports update rows.

For a raw JSON export without a database, from the repository root:

```sh
python3 repos/datasource/pba/scraper.py --game-id 522 --output /tmp/pba-522.json
```

Use `--pba` for typed PBA cleaning; generic `--input` uses the default cleaner.
Only game 522 has been verified live. Schedule discovery, polling, retries,
play-by-play ingestion, and cross-game player identity matching are not implemented.
HTML changes or access challenges fail the run instead of importing partial data.

### Discover published games

```sh
PYTHONPATH=src python3 -m ingestion --list-games \
  --tournament pba-50th-season-governors-cup
```

Returns JSON with game IDs, canonical URLs, status text, and team codes without
writing to the database. It follows `a.schedule-box` links for the selected
tournament, deduplicates IDs, and preserves page order. Do not assume IDs are
consecutive. The inspected page listed 50 Final games; this is the published page
list, not a guarantee of complete historical coverage. No pagination was visible.

To ingest the listed completed games programmatically:

```python
import time
from pathlib import Path
from ingestion.sources.pba import discover_games, PbaSource
from ingestion.pba_cleaning import PbaCleaner
from ingestion.engine import IngestionEngine
from ingestion.storage import SQLiteStore

tournament = 'pba-50th-season-governors-cup'
engine = IngestionEngine(PbaCleaner(), SQLiteStore(Path('data/league.sqlite3')))
for game in discover_games(tournament):
    if game.status.casefold() != 'final':
        continue
    engine.run(PbaSource(tournament, game.game_id))
    time.sleep(1)
```

Each game commits separately. An error stops this example, retaining previously
completed games; rerunning updates those records. Discovery itself does not fetch
the individual games.


## Player schema

Install the project (`python -m pip install -e .`) to include Pydantic v2.

```python
from ingestion.schemas import Player

player = Player(
    player_name="Rhon Jay Abarrientos",
    player_short_name="R. Abarrientos",
    external_id="150",
)
print(player.model_dump_json())
```

`player_id` defaults to a new UUID. Supply the existing UUID when loading or
updating a player; this schema does not perform identity matching. All three text
fields are required, trimmed, and cannot be blank. External IDs remain strings
to preserve leading zeroes. This defines validation only; a database player table
and mappings from game stats are not created by this schema.

## Game schemas

`from ingestion.schemas import Game, GameStatistics`

`Game` uses an internal UUID and two team UUID references. Optional metadata covers
provider game ID, tournament slug, competition name, venue, scheduled datetime,
original date/time text, status, period, clock, scores, period scores, and source URL.
Team order follows the source and does not imply home/away. Keep the raw date string
until its date format and timezone are confirmed.

`GameStatistics` represents one player in a game, with required game/player/team
UUID references. It includes jersey number, source player name, position, starter
flag, original minutes text, seconds played, all counting stats, signed plus/minus,
and flat made/attempted/percentage fields for FG, 2P, 3P, 4P, and FT. Missing stats
remain null; percentages use 0–100. Intended uniqueness is `(game_id, player_id)`.

These are Pydantic validation schemas, not SQL migrations. Database foreign keys,
uniqueness, metadata extraction, and mapping the cleaner's nested shooting values
into these flat fields must be wired in when adding normalized persistence.
