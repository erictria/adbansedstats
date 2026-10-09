"""Exercise the HTTP contract against a small independent DuckDB fixture."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from uuid import uuid4

import duckdb
from fastapi.testclient import TestClient

from banse.server import create_app


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.database = Path(self.tmp.name) / 'test.duckdb'
        self.league_id, self.tournament_id = uuid4(), uuid4()
        self.player_id, self.team_id, self.opponent_id, self.game_id = (uuid4() for _ in range(4))
        with duckdb.connect(str(self.database)) as connection:
            connection.execute('CREATE TABLE leagues (league_id UUID, league_name VARCHAR, abbreviation VARCHAR)')
            connection.execute('CREATE TABLE tournaments (tournament_id UUID, league_id UUID, tournament_name VARCHAR, season VARCHAR, slug VARCHAR)')
            connection.execute('CREATE TABLE players (player_id UUID, player_name VARCHAR, player_short_name VARCHAR, slug VARCHAR, photo_url VARCHAR)')
            connection.execute('CREATE TABLE teams (team_id UUID, team_name VARCHAR, slug VARCHAR, logo_url VARCHAR)')
            connection.execute('CREATE TABLE tournament_teams (tournament_id UUID, team_id UUID)')
            connection.execute('CREATE TABLE roster_memberships (tournament_id UUID, player_id UUID, team_id UUID, jersey_number VARCHAR)')
            connection.execute('''CREATE TABLE games (game_id UUID, external_id VARCHAR, tournament_id UUID,
                date_time_raw VARCHAR, status VARCHAR, venue VARCHAR, team_id_1 UUID, team_id_2 UUID,
                team_1_score INTEGER, team_2_score INTEGER,
                team_1_period_scores INTEGER[], team_2_period_scores INTEGER[])''')
            connection.execute('''CREATE TABLE game_statistics (game_id UUID, player_id UUID, team_id UUID,
                jersey_number VARCHAR, is_starter BOOLEAN, participation_status VARCHAR, minutes_raw VARCHAR,
                points INTEGER, rebounds INTEGER, assists INTEGER, steals INTEGER, blocks INTEGER,
                turnovers INTEGER, field_goals_made INTEGER, field_goals_attempted INTEGER,
                three_pointers_made INTEGER, three_pointers_attempted INTEGER,
                four_pointers_made INTEGER, four_pointers_attempted INTEGER,
                free_throws_made INTEGER, free_throws_attempted INTEGER, plus_minus INTEGER,
                seconds_played INTEGER)''')
            connection.execute('INSERT INTO leagues VALUES (?, ?, ?)', [self.league_id, 'Test League', 'TL'])
            connection.execute('INSERT INTO tournaments VALUES (?, ?, ?, ?, ?)',
                               [self.tournament_id, self.league_id, 'Test Cup', '2026', 'test-cup'])
            connection.execute('INSERT INTO players VALUES (?, ?, ?, ?, ?)',
                               [self.player_id, 'Test Player', 'T. Player', 'test-player', None])
            connection.executemany('INSERT INTO teams VALUES (?, ?, ?, ?)',
                                   [(self.team_id, 'Blue Team', 'blue', None),
                                    (self.opponent_id, 'Red Team', 'red', None)])
            connection.executemany('INSERT INTO tournament_teams VALUES (?, ?)',
                                   [(self.tournament_id, self.team_id), (self.tournament_id, self.opponent_id)])
            connection.execute('INSERT INTO roster_memberships VALUES (?, ?, ?, ?)',
                               [self.tournament_id, self.player_id, self.team_id, '7'])
            connection.execute('INSERT INTO games VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                               [self.game_id, '522', self.tournament_id, '07/11/26 05:15 PM', 'final', 'Test Arena',
                                self.team_id, self.opponent_id, 100, 90, [25, 25, 25, 25], [20, 20, 25, 25]])
            connection.execute('''INSERT INTO game_statistics VALUES
                (?, ?, ?, '7', true, 'played', '30:00', 20, 5, 4, 2, 1, 3,
                 7, 12, 2, 5, 1, 1, 4, 4, 10, 1800)''',
                               [self.game_id, self.player_id, self.team_id])
        self.client = TestClient(create_app(self.database, cors_origin='http://localhost:5173'))

    def tearDown(self):
        self.client.close()
        self.tmp.cleanup()

    def test_overview_and_details(self):
        scope = {'tournament_id': str(self.tournament_id)}
        tournaments = self.client.get('/api/tournaments')
        self.assertEqual(tournaments.status_code, 200)
        self.assertEqual(tournaments.json()[0]['tournament_name'], 'Test Cup')
        overview = self.client.get('/api/overview', params=scope)
        self.assertEqual(overview.status_code, 200)
        self.assertEqual([len(overview.json()[key]) for key in ('teams', 'players', 'games')], [2, 1, 1])
        self.assertEqual(overview.json()['players'][0]['points_total'], 20)
        self.assertEqual(self.client.get('/api/players', params=scope).json()[0]['games'], 1)
        self.assertEqual(self.client.get(f'/api/players/{self.player_id}', params=scope).json()['games_log'][0]['points'], 20)
        self.assertEqual(self.client.get(f'/api/teams/{self.team_id}', params=scope).json()['roster'][0]['player_name'], 'Test Player')
        self.assertEqual(self.client.get(f'/api/games/{self.game_id}', params=scope).json()['box_score'][0]['player_name'], 'Test Player')
        self.assertEqual(self.client.get('/api/games', params=scope).json()[0]['external_id'], '522')
        self.assertEqual(overview.headers['cache-control'], 'no-store')
        self.assertEqual(self.client.get('/docs').status_code, 200)

    def test_validation_scope_and_cors(self):
        self.assertEqual(self.client.get('/api/players').status_code, 422)
        self.assertEqual(self.client.get('/api/players', params={'tournament_id': 'bad'}).status_code, 422)
        self.assertEqual(self.client.get('/api/players', params={'tournament_id': str(uuid4())}).status_code, 404)
        self.assertEqual(self.client.get(f'/api/players/{uuid4()}', params={'tournament_id': str(self.tournament_id)}).status_code, 404)
        response = self.client.get('/api/health', headers={'Origin': 'http://localhost:5173'})
        self.assertEqual(response.json(), {'status': 'ok'})
        self.assertEqual(response.headers['access-control-allow-origin'], 'http://localhost:5173')


if __name__ == '__main__':
    unittest.main()
