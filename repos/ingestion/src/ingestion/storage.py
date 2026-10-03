import json
import sqlite3
from contextlib import contextmanager
from importlib.resources import files
from uuid import UUID

from .domain_storage import DomainStore
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path

from .models import IngestedRecord

SCHEMA = """
CREATE TABLE IF NOT EXISTS ingestion_runs (
    run_id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT NOT NULL,
    records_written INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS records (
    source TEXT NOT NULL,
    entity TEXT NOT NULL,
    external_id TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    raw_json TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    run_id TEXT NOT NULL REFERENCES ingestion_runs(run_id),
    PRIMARY KEY (source, entity, external_id)
);
"""


class SQLiteConnection:
    """Bind domain values to SQLite's scalar types without global adapters."""
    def __init__(self, connection):
        self.connection = connection

    def execute(self, sql, params=()):
        values = []
        for value in params:
            if isinstance(value, UUID):
                value = str(value)
            elif isinstance(value, datetime):
                value = value.isoformat()
            elif isinstance(value, list):
                value = json.dumps(value)
            values.append(value)
        return self.connection.execute(sql, values)


class SQLiteStore(DomainStore):
    """Latest raw and clean values per source/entity/ID, with successful-run history."""
    def __init__(self, path: Path):
        self.path = path

    @contextmanager
    def transaction(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.executescript(files('ingestion').joinpath('sql/sqlite_initial.sql').read_text())
            with connection:
                connection.execute("BEGIN")
                yield SQLiteConnection(connection)
        finally:
            connection.close()

    def initialize(self):
        with self.transaction():
            pass

    def write_batch(
        self, source: str, run_id: str, started_at: str,
        records: Sequence[IngestedRecord],
    ) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        completed_at = datetime.now(timezone.utc).isoformat()
        connection = sqlite3.connect(self.path)
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.executescript(SCHEMA)
            with connection:
                connection.execute(
                    "INSERT INTO ingestion_runs VALUES (?, ?, ?, ?, ?)",
                    (run_id, source, started_at, completed_at, len(records)),
                )
                for record in records:
                    raw, clean = record.raw, record.clean
                    connection.execute(
                        """INSERT INTO records VALUES (?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(source, entity, external_id) DO UPDATE SET
                            payload_json=excluded.payload_json,
                            raw_json=excluded.raw_json,
                            updated_at=excluded.updated_at,
                            run_id=excluded.run_id""",
                        (source, clean.entity, clean.external_id,
                         json.dumps(clean.payload, allow_nan=False, ensure_ascii=False),
                         json.dumps({"entity": raw.entity, "external_id": raw.external_id,
                                     "payload": raw.payload}, allow_nan=False, ensure_ascii=False),
                         completed_at, run_id),
                    )
        finally:
            connection.close()
        return len(records)
