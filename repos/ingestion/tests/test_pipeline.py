import json
import logging
import sqlite3
import tempfile
import unittest
from pathlib import Path

from ingestion.cleaning import DefaultCleaner
from ingestion.engine import IngestionEngine
from ingestion.models import RawRecord
from ingestion.storage import SQLiteStore


class StubSource:
    name = 'demo'

    def __init__(self, records):
        self.records = records

    def fetch(self):
        yield from self.records


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'league.sqlite3'
        self.engine = IngestionEngine(DefaultCleaner(), SQLiteStore(self.path))
        self.record = RawRecord('player', '7', {'name': ' Alex ', 'number': '007'})

    def query(self, sql):
        connection = sqlite3.connect(self.path)
        try:
            return connection.execute(sql).fetchall()
        finally:
            connection.close()

    def test_cleaning_raw_preservation_and_upsert(self):
        self.engine.run(StubSource([self.record]))
        payload, raw = self.query('SELECT payload_json, raw_json FROM records')[0]
        self.assertEqual(json.loads(payload), {'name': 'Alex', 'number': '007'})
        self.assertEqual(json.loads(raw)['payload']['name'], ' Alex ')
        self.engine.run(StubSource([RawRecord('player', '7', {'name': 'Updated'})]))
        self.assertEqual(len(self.query('SELECT * FROM records')), 1)
        self.assertEqual(len(self.query('SELECT * FROM ingestion_runs')), 2)
        self.assertEqual(json.loads(self.query('SELECT payload_json FROM records')[0][0]), {'name': 'Updated'})

    def test_sources_are_isolated(self):
        self.engine.run(StubSource([self.record]))
        other = StubSource([self.record])
        other.name = 'another-league'
        self.engine.run(other)
        self.assertEqual(len(self.query('SELECT * FROM records')), 2)

    def test_invalid_or_duplicate_batch_does_not_write(self):
        self.engine.run(StubSource([self.record]))
        for records in ([self.record, RawRecord('player', '', {})], [self.record, self.record]):
            with self.assertRaises(ValueError):
                self.engine.run(StubSource(records))
        self.assertEqual(len(self.query('SELECT * FROM ingestion_runs')), 1)

    def test_retrieval_failure_does_not_write(self):
        def broken():
            yield self.record
            raise RuntimeError('Retrieval interrupted')
        with self.assertRaises(RuntimeError):
            self.engine.run(StubSource(broken()))
        self.assertFalse(self.path.exists())

    def test_storage_failure_rolls_back_batch_and_run(self):
        self.engine.run(StubSource([self.record]))
        # The cleaner converts this key to valid JSON, but the raw tuple key
        # cannot be serialized. Fail after the first SQL record write.
        bad = RawRecord('player', '8', {('invalid',): 'value'})
        class CustomCleaner:
            def clean(inner, record):
                from ingestion.models import CleanRecord
                return CleanRecord(record.entity, record.external_id, {'name': 'clean'})
        engine = IngestionEngine(CustomCleaner(), SQLiteStore(self.path))
        with self.assertRaises(TypeError):
            engine.run(StubSource([RawRecord('player', '9', {}), bad]))
        self.assertEqual(len(self.query('SELECT * FROM records')), 1)
        self.assertEqual(len(self.query('SELECT * FROM ingestion_runs')), 1)

    def test_cleaner_rejects_collisions_and_nonfinite_numbers(self):
        for payload in ({'name': 'a', ' name ': 'b'}, {'points': float('nan')}):
            with self.assertRaises(ValueError):
                DefaultCleaner().clean(RawRecord('player', '7', payload))


if __name__ == '__main__':
    logging.disable(logging.CRITICAL)
    unittest.main()
