import json
from pathlib import Path
import tempfile
import unittest
from uuid import uuid4
from unittest.mock import patch

from test_pba import fixture
from ingestion.pba_workflow import prepare, build, ingest
from ingestion.sources.pba_directory import parse_players, parse_teams
from ingestion.storage import SQLiteStore
from ingestion.duckdb_storage import DuckDBStore


def html():
    board = '<div id="scoreboard">'
    for code in ['AAA', 'BBB']:
        board += f'<div class="team_code">{code}</div><div class="team_score">9</div>'
    board += '<div class="period">period 4</div><div class="clock">00:00</div></div>'
    return ('<a class="schedule-box" href="?game_id=522"><div class="schedule-details">Final</div></a>'
            + '<div class="game-detail"><h6>Game Details</h6><span>07/11/26 05:15 PM</span></div>'
            + board + fixture())


class WorkflowTests(unittest.TestCase):
    def prepare(self, directory):
        with patch('ingestion.pba_workflow.fetch_html', return_value=html()), patch('ingestion.pba_workflow.time.sleep'):
            prepare('test-cup', directory)
        path = directory / 'identities.json'
        return path, json.loads(path.read_text())

    def resolve(self, review):
        for index, code in enumerate(review['team_matches']):
            eid = str(index)
            review['teams'][eid] = dict(team_id=str(uuid4()), team_name=code, external_id=eid)
            review['team_matches'][code] = eid
        for index, key in enumerate(review['player_matches']):
            eid = str(index)
            review['players'][eid] = dict(player_id=str(uuid4()), player_name=f'Player {index}', player_short_name='A. Player', external_id=eid)
            review['player_matches'][key] = eid

    def test_blocked_then_repeat_import_both_backends(self):
        for cls in [SQLiteStore, DuckDBStore]:
            with self.subTest(backend=cls), tempfile.TemporaryDirectory() as tmp:
                directory = Path(tmp)
                path, review = self.prepare(directory)
                store = cls(directory / 'db')
                with self.assertRaises(ValueError):
                    ingest(directory, store)
                self.assertFalse((directory / 'db').exists())
                self.resolve(review)
                path.write_text(json.dumps(review))
                first = ingest(directory, store)
                second = ingest(directory, store)
                self.assertEqual(first, second)
                self.assertEqual(first['normalized']['roster_memberships'], 2)
                with store.transaction() as con:
                    self.assertEqual(con.execute('SELECT count(*) FROM games').fetchone()[0], 1)
                    self.assertEqual(con.execute('SELECT count(*) FROM game_statistics').fetchone()[0], 2)
                    self.assertEqual(con.execute('SELECT count(*) FROM team_game_statistics').fetchone()[0], 2)
                    self.assertEqual(con.execute('SELECT count(*) FROM roster_memberships').fetchone()[0], 2)
                    self.assertEqual(con.execute("SELECT count(*) FROM roster_memberships WHERE source='pba-assumed' AND valid_to IS NULL").fetchone()[0], 2)
                # A new UUID for an existing provider identity must roll back the batch.
                changed = json.loads(json.dumps(review))
                changed['players']['0']['player_id'] = str(uuid4())
                path.write_text(json.dumps(changed))
                with self.assertRaises(ValueError):
                    ingest(directory, store)
                with store.transaction() as con:
                    self.assertEqual(con.execute('SELECT count(*) FROM players').fetchone()[0], 2)
                    self.assertEqual(con.execute('SELECT count(*) FROM ingestion_runs').fetchone()[0], 2)
                path.write_text(json.dumps(review))
                # Reprepare preserves reviewed mappings and internal identities.
                with patch('ingestion.pba_workflow.fetch_html', side_effect=AssertionError('Unexpected fetch')):
                    prepare('test-cup', directory)
                self.assertEqual(json.loads(path.read_text()), review)

    def test_duplicate_player_mapping_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            path, review = self.prepare(directory)
            self.resolve(review)
            keys = list(review['player_matches'])
            review['player_matches'][keys[1]] = review['player_matches'][keys[0]]
            path.write_text(json.dumps(review))
            with self.assertRaises(ValueError):
                build(directory)

    def test_directory_ids(self):
        players = parse_players('''<div class="player-mask"><!-- <a href="https://www.pba.ph/players/rhon-jay-abarrientos"> -->
            <img class="player-img" src="https://example.com/organizer/people/150/photo.png">
            <h2 class="player-mask-other top">Abarrientos</h2><p class="player-mask-other bottom">Rhon Jay</p></div>''')
        self.assertEqual(players[0]['external_id'], '150')
        self.assertEqual(players[0]['slug'], 'rhon-jay-abarrientos')
        teams = parse_teams('<a href="/teams/ginebra"><img src="https://example.com/organizer/teams/4/logo.png"><h3>Ginebra</h3></a>')
        self.assertEqual(teams[0]['external_id'], '4')
