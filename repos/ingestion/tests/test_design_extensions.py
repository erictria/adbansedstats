import json
from pathlib import Path
import tempfile
import unittest
from uuid import uuid4

from pydantic import ValidationError
from ingestion.schemas import Game, GameStatistics, RosterMembership
from ingestion.storage import SQLiteStore
from ingestion.duckdb_storage import DuckDBStore


class ExtensionTests(unittest.TestCase):
    def test_participation_and_date_validation(self):
        with self.assertRaises(ValidationError):
            GameStatistics(game_id=uuid4(), player_id=uuid4(), team_id=uuid4(), participation_status='dnp', points=1)
        with self.assertRaises(ValidationError):
            RosterMembership(player_id=uuid4(), team_id=uuid4(), tournament_id=uuid4(), valid_from='2026-02-01', valid_to='2026-01-01')
        with self.assertRaises(ValidationError):
            Game(team_id_1=uuid4(), team_id_2=uuid4(), status='finished')

    def test_relationships_and_views(self):
        payload = json.loads((Path(__file__).parents[1] / 'examples/normalized.json').read_text())
        for cls in (DuckDBStore, SQLiteStore):
            with self.subTest(backend=cls), tempfile.TemporaryDirectory() as directory:
                store = cls(Path(directory)/'test.db')
                store.write_models(**payload)
                store.write_models(**payload)
                with store.transaction() as con:
                    self.assertEqual(con.execute('SELECT games_played, points_per_game FROM player_tournament_statistics').fetchone(), (1,20.0))
                    self.assertEqual(con.execute('SELECT count(*) FROM team_game_statistics').fetchone()[0],2)
                overlap = dict(payload['roster_memberships'][0], roster_id=str(uuid4()))
                with self.assertRaises(ValueError):
                    store.write_models(roster_memberships=[overlap])
                with self.assertRaises(ValueError):
                    store.write_models(games=[dict(payload['games'][0], game_id=str(uuid4()), tournament_id=None)])
                with self.assertRaises(ValueError):
                    store.write_models(source_mappings=[dict(payload['source_mappings'][0], internal_id=str(uuid4()))])
