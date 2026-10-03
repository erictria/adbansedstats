import tempfile
import unittest
from pathlib import Path
from uuid import uuid4

import duckdb
from ingestion.duckdb_storage import DuckDBStore
from ingestion.schemas import Player, Team, Game, GameStatistics
from ingestion.engine import IngestionEngine
from ingestion.cleaning import DefaultCleaner
from ingestion.sources.json_file import JsonFileSource


class DuckDBTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'league.duckdb'
        self.store = DuckDBStore(self.path)
        self.player = Player(player_name='Example Player', player_short_name='E. Player', external_id='150')
        self.teams = [Team(team_name=n, external_id=str(i)) for i, n in enumerate(['A', 'B', 'C'])]
        self.game = Game(team_id_1=self.teams[0].team_id, team_id_2=self.teams[1].team_id,
                         team_1_period_scores=[10, 20], external_id='522')
        self.stats = GameStatistics(game_id=self.game.game_id, player_id=self.player.player_id,
                                    team_id=self.teams[0].team_id, points=12)

    def query(self, sql):
        with duckdb.connect(str(self.path), read_only=True) as con:
            return con.execute(sql).fetchall()

    def save(self):
        return self.store.write_models(players=[self.player], teams=self.teams,
                                      games=[self.game], game_statistics=[self.stats])

    def test_upsert_and_types(self):
        self.save()
        self.player.player_name = 'Updated Player'
        self.stats.points = 20
        self.game.team_1_period_scores = [11, 20]
        self.game.team_1_score = 31
        self.save()
        self.assertEqual(self.query('SELECT player_name FROM players'), [('Updated Player',)])
        self.assertEqual(self.query('SELECT points FROM game_statistics'), [(20,)])
        self.assertEqual(self.query('SELECT team_1_period_scores FROM games'), [([11, 20],)])

    def test_transaction_rollback(self):
        self.save()
        new = Player(player_name='New', player_short_name='N.', external_id='2')
        bad = self.stats.model_copy(update={'player_id': uuid4()})
        with self.assertRaises(duckdb.ConstraintException):
            self.store.write_models(players=[new], game_statistics=[bad])
        self.assertEqual(self.query('SELECT count(*) FROM players'), [(1,)])

    def test_team_membership(self):
        self.save()
        bad = self.stats.model_copy(update={'team_id': self.teams[2].team_id})
        with self.assertRaises(ValueError):
            self.store.write_models(game_statistics=[bad])

    def test_staging_repeat_import(self):
        fixture = Path(self.tmp.name) / 'input.json'
        fixture.write_text('[{"entity":"player", "external_id":"1", "payload":{"name":" Test "}}]')
        engine = IngestionEngine(DefaultCleaner(), self.store)
        for _ in range(2):
            engine.run(JsonFileSource(fixture, 'demo'))
        self.assertEqual(self.query('SELECT count(*) FROM records'), [(1,)])
        self.assertEqual(self.query('SELECT count(*) FROM ingestion_runs'), [(2,)])
