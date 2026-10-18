"""Private HTTP access to the existing ingestion commands."""
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import duckdb
from fastapi.testclient import TestClient

from ingestion.api import Settings, create_app


class IngestionApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.database = self.root / 'league.duckdb'
        self.client = TestClient(create_app(Settings('test-secret', self.root / 'work', self.database)))
        self.auth = {'Authorization': 'Bearer test-secret'}

    def tearDown(self):
        self.client.close()
        self.temp.cleanup()

    def wait_for(self, job_id):
        for _ in range(100):
            response = self.client.get(f'/ingestion/jobs/{job_id}', headers=self.auth)
            self.assertEqual(response.status_code, 200)
            job = response.json()
            if job['status'] != 'running':
                return job
            time.sleep(0.05)
        self.fail('ingestion job did not complete')

    def test_authentication_and_database_initialization(self):
        self.assertEqual(self.client.post('/ingestion/init-db').status_code, 401)
        self.assertEqual(self.client.post('/ingestion/init-db',
                         headers={'Authorization': 'Bearer wrong'}).status_code, 401)
        response = self.client.post('/ingestion/init-db', headers=self.auth)
        self.assertEqual(response.status_code, 202)
        job = self.wait_for(response.json()['job_id'])
        self.assertEqual(job['status'], 'succeeded', job['error'])
        self.assertTrue(job['result']['initialized'])
        with duckdb.connect(str(self.database), read_only=True) as connection:
            self.assertEqual(connection.execute('SELECT count(*) FROM tournaments').fetchone()[0], 0)

    def test_file_inputs_are_limited_to_work_directory(self):
        bad = {'work_dir': '../other', 'filename': 'fixture.json'}
        self.assertEqual(self.client.post('/ingestion/fixture', headers=self.auth,
                                         json=bad).status_code, 422)
        missing = {'work_dir': 'season50', 'filename': 'fixture.json'}
        self.assertEqual(self.client.post('/ingestion/fixture', headers=self.auth,
                                         json=missing).status_code, 404)
        self.assertEqual(self.client.post('/ingestion/normalized', headers=self.auth,
                                         json={'work_dir': 'season50', 'filename': '../secret.json'}).status_code, 422)

    def test_jobs_are_serialized_and_all_cli_modes_are_exposed(self):
        paths = self.client.get('/openapi.json').json()['paths']
        for operation in ('list-games', 'prepare-pba', 'match-pba', 'import-pba',
                          'init-db', 'pba-game', 'normalized', 'fixture'):
            self.assertIn('post', paths[f'/ingestion/{operation}'])
        release = Event()

        def slow_command(*_args, **_kwargs):
            release.wait(timeout=2)
            return SimpleNamespace(returncode=0, stdout='{"initialized": true}', stderr='')

        with patch('ingestion.api.subprocess.run', side_effect=slow_command):
            first = self.client.post('/ingestion/init-db', headers=self.auth)
            self.assertEqual(first.status_code, 202)
            self.assertEqual(self.client.post('/ingestion/init-db', headers=self.auth).status_code, 409)
            release.set()
            self.assertEqual(self.wait_for(first.json()['job_id'])['status'], 'succeeded')


if __name__ == '__main__':
    unittest.main()
