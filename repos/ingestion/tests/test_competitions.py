import tempfile
import unittest
from pathlib import Path
from uuid import uuid4
import duckdb
import sqlite3
from ingestion.duckdb_storage import DuckDBStore
from ingestion.storage import SQLiteStore
from ingestion.schemas import League, Tournament, Game, Team


class CompetitionTests(unittest.TestCase):
    def test_hierarchy_and_unknown_parent_rollback(self):
        for store_type, connect in [(DuckDBStore, duckdb.connect), (SQLiteStore, sqlite3.connect)]:
            with self.subTest(backend=store_type), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'test.db'
                store = store_type(path)
                league = League(league_name='PBA')
                tournament = Tournament(league_id=league.league_id, tournament_name='Cup', season='50')
                teams = [Team(team_name=name, external_id=name) for name in ['A', 'B']]
                game = Game(team_id_1=teams[0].team_id, team_id_2=teams[1].team_id, tournament_id=tournament.tournament_id)
                for _ in range(2):
                    store.write_models(leagues=[league], tournaments=[tournament], teams=teams, tournament_teams=[dict(tournament_id=tournament.tournament_id, team_id=t.team_id) for t in teams], games=[game])
                game.tournament_id = uuid4()
                with self.assertRaises(ValueError):
                    store.write_models(leagues=[League(league_name='Rollback')], games=[game])
                con = connect(str(path))
                try:
                    self.assertEqual(con.execute('SELECT count(*) FROM leagues').fetchone()[0], 1)
                    self.assertEqual(con.execute('SELECT count(*) FROM games g JOIN tournaments t ON g.tournament_id=t.tournament_id JOIN leagues l ON t.league_id=l.league_id').fetchone()[0], 1)
                finally:
                    con.close()

    def test_legacy_migration(self):
        for store_type, connect in [(DuckDBStore, duckdb.connect), (SQLiteStore, sqlite3.connect)]:
            with self.subTest(backend=store_type), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'legacy.db'
                store = store_type(path)
                con = connect(str(path))
                sql_file = '001_initial.sql' if store_type is DuckDBStore else 'sqlite_initial.sql'
                sql = (Path(__file__).parents[1] / 'src/ingestion/sql' / sql_file).read_text()
                sql = sql.replace('    tournament_id UUID,\n', '').replace('    tournament_id TEXT,\n', '')
                if store_type is DuckDBStore:
                    con.execute(sql)
                else:
                    con.executescript(sql)
                con.close()
                store.initialize()
                store.initialize()
                con = connect(str(path))
                try:
                    self.assertIn('tournament_id', [r[1] for r in con.execute("PRAGMA table_info('games')").fetchall()])
                finally:
                    con.close()
