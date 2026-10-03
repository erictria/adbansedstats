import unittest
from ingestion.sources.pba import HEADERS, parse_box_score
from ingestion.pba_cleaning import PbaCleaner


def fixture():
    blocks = []
    for code in ('AAA', 'BBB'):
        values = ['00', 'A. Player', 'G', '12:34', '9', '3-5', '60', '1-2', '50', '1-2', '50', '1-1', '100', '0-0', '0', '1', '2', '3', '4', '1', '0', '1', '2', '1', '-3']
        def row(items):
            return ''.join(f'<td>{v}</td>' for v in items)
        totals = values.copy()
        totals[:2] = ['', 'TEAM TOTALS']
        blocks.append(f'<div class="box-score_title"><div class="team_code">{code}</div><div class="team_name">Team {code}</div></div><table class="box-score"><tr>' + ''.join(f'<th>{h}</th>' for h in HEADERS) + '</tr><tr class="bsheader_type"><th></th><th>starters</th></tr><tr>' + row(values) + '</tr><tr class="team-coach"><td>Team / Coach</td></tr><tr class="team-totals">' + row(totals) + '</tr></table>')
    return ''.join(blocks)


class PbaTests(unittest.TestCase):
    def test_parse_and_clean(self):
        records = parse_box_score(fixture(), 'test-cup', 522)
        self.assertEqual([r.entity for r in records], ['player_game_stats', 'team_game_stats'] * 2)
        self.assertEqual(records[0].external_id, 'test-cup:522:AAA:00')
        stats = PbaCleaner().clean(records[0]).payload['stats']
        self.assertEqual(stats['seconds_played'], 754)
        self.assertEqual(stats['four_pointers']['made'], 1)
        self.assertEqual(stats['jersey_number'], '00')
        self.assertEqual(records[0].payload['stats']['MINS'], '12:34')

    def test_bad_layout(self):
        for html in ('<html>Just a moment...</html>', fixture().replace('<th>4P</th>', '<th>UNKNOWN</th>')):
            with self.assertRaises(ValueError):
                parse_box_score(html, 'test-cup', 522)

    def test_bad_values(self):
        for old, new in [('3-5', '6-5'), ('12:34', '12:99')]:
            records = parse_box_score(fixture().replace(old, new), 'test-cup', 522)
            with self.assertRaises(ValueError):
                PbaCleaner().clean(records[0])


class ScheduleTests(unittest.TestCase):
    def test_unique_ids_status_and_scope(self):
        from ingestion.sources.pba import parse_schedule
        link = '<a class="schedule-box" href="/tournaments/test-cup?game_id=12&amp;x=1"><div class="team">AAA</div><div class="schedule-details">Final</div><div class="team">BBB</div></a>'
        games = parse_schedule(link + link + link.replace('test-cup', 'other-cup'), 'test-cup')
        self.assertEqual(len(games), 1)
        self.assertEqual(games[0].game_id, 12)
        self.assertEqual(games[0].teams, ['AAA', 'BBB'])
        self.assertEqual(games[0].status, 'Final')

    def test_empty_or_invalid_schedule_fails(self):
        from ingestion.sources.pba import parse_schedule
        for html in ('<html>Blocked</html>', '<a class="schedule-box" href="?game_id=no">Game</a>'):
            with self.assertRaises(ValueError):
                parse_schedule(html, 'test-cup')
