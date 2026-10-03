"""Single-writer DuckDB storage for staging records and validated domain models."""
from contextlib import contextmanager
from datetime import datetime, timezone
from importlib.resources import files
import json
from pathlib import Path

import duckdb
from pydantic import HttpUrl

from .schemas import Game, GameStatistics, Player, Team


class DuckDBStore:
    def __init__(self, path: Path):
        self.path = Path(path)

    @contextmanager
    def transaction(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = duckdb.connect(str(self.path))
        try:
            connection.execute(files('ingestion').joinpath('sql/001_initial.sql').read_text())
            connection.execute('BEGIN TRANSACTION')
            try:
                yield connection
                connection.execute('COMMIT')
            except Exception:
                connection.execute('ROLLBACK')
                raise
        finally:
            connection.close()

    def initialize(self):
        with self.transaction():
            pass

    def write_batch(self, source, run_id, started_at, records):
        now = datetime.now(timezone.utc)
        with self.transaction() as connection:
            connection.execute('INSERT INTO ingestion_runs VALUES (?, ?, ?, ?, ?)',
                               [run_id, source, started_at, now, len(records)])
            for record in records:
                raw, clean = record.raw, record.clean
                connection.execute('''INSERT INTO records VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT (source, entity, external_id) DO UPDATE SET
                    payload_json=excluded.payload_json, raw_json=excluded.raw_json,
                    updated_at=excluded.updated_at, run_id=excluded.run_id''',
                    [source, clean.entity, clean.external_id,
                     json.dumps(clean.payload, allow_nan=False),
                     json.dumps({'entity': raw.entity, 'external_id': raw.external_id,
                                 'payload': raw.payload}, allow_nan=False), now, run_id])
        return len(records)

    def write_models(self, *, players=(), teams=(), games=(), game_statistics=()):
        """Atomic full-row upserts in dependency order. Pass existing UUIDs on reruns.

        Accepts schema instances or dictionaries. Omitted optional values replace
        existing values with NULL; this is not a partial-update API.
        """
        batches = []
        for table, model, keys, items in (
            ('players', Player, ('player_id',), players),
            ('teams', Team, ('team_id',), teams),
            ('games', Game, ('game_id',), games),
            ('game_statistics', GameStatistics, ('game_id', 'player_id'), game_statistics),
        ):
            rows = [model.model_validate(item.model_dump() if isinstance(item, model) else item)
                    for item in items]
            identities = [tuple(getattr(row, key) for key in keys) for row in rows]
            if len(set(identities)) != len(identities):
                raise ValueError(f'Duplicate identities in {table} batch')
            for row in rows:
                if isinstance(row, Game) and row.scheduled_at is not None and row.scheduled_at.utcoffset() is None:
                    raise ValueError('scheduled_at must include a timezone; use date_time_raw if unknown')
            batches.append((table, keys, rows))
        with self.transaction() as connection:
            for table, keys, rows in batches:
                for row in rows:
                    if isinstance(row, GameStatistics):
                        game = connection.execute('SELECT team_id_1, team_id_2 FROM games WHERE game_id=?', [row.game_id]).fetchone()
                        if game is None or row.team_id not in game:
                            raise ValueError('Statistics team must participate in the referenced game')
                    if isinstance(row, Game):
                        invalid = connection.execute('SELECT count(*) FROM game_statistics WHERE game_id=? AND team_id NOT IN (?, ?)', [row.game_id, row.team_id_1, row.team_id_2]).fetchone()[0]
                        if invalid:
                            raise ValueError('Changing teams would invalidate existing game statistics')
                    values = row.model_dump()
                    columns = list(values)
                    params = [str(v) if isinstance(v, HttpUrl) else v for v in values.values()]
                    updates = ', '.join(f'{c}=excluded.{c}' for c in columns if c not in keys)
                    connection.execute(f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({', '.join('?' for _ in columns)}) ON CONFLICT ({', '.join(keys)}) DO UPDATE SET {updates}", params)
        return {table: len(rows) for table, _, rows in batches}
