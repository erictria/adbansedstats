"""Single-writer DuckDB storage for staging records and validated domain models."""
from contextlib import contextmanager
from datetime import datetime, timezone
from importlib.resources import files
import json
from pathlib import Path

import duckdb

from .domain_storage import DomainStore


class DuckDBStore(DomainStore):
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

