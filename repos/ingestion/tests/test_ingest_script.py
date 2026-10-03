import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

import duckdb

ROOT = Path(__file__).resolve().parents[1]


class ScriptTests(unittest.TestCase):
    def test_both_backends_repeat_and_rollback(self):
        for backend in ('sqlite', 'duckdb'):
            with self.subTest(backend=backend), tempfile.TemporaryDirectory() as directory:
                db = Path(directory) / 'league.db'
                command = [sys.executable, str(ROOT / 'ingest.py'), '--backend', backend,
                           '--database', str(db), '--normalized']
                for _ in range(2):
                    result = subprocess.run(command + [str(ROOT / 'examples/normalized.json')], capture_output=True, text=True)
                    self.assertEqual(result.returncode, 0, result.stderr)
                payload = json.loads((ROOT / 'examples/normalized.json').read_text())
                payload['players'][0]['player_name'] = 'Should roll back'
                payload['game_statistics'][0]['team_id'] = '00000000-0000-4000-8000-000000000099'
                bad = Path(directory) / 'bad.json'
                bad.write_text(json.dumps(payload))
                result = subprocess.run(command + [str(bad)], capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0)
                connection = sqlite3.connect(db) if backend == 'sqlite' else duckdb.connect(str(db))
                try:
                    self.assertEqual(connection.execute('SELECT player_name FROM players').fetchall(), [('Alex Reyes',)])
                    self.assertEqual(connection.execute('SELECT count(*) FROM game_statistics').fetchone()[0], 1)
                finally:
                    connection.close()
