import json
from pathlib import Path
import tempfile
import unittest
from ingestion.pba_identity import match_directory
from ingestion.sources.pba_directory import parse_players


def card(photo, slug, number, first='John', last='Smith'):
    return f'''<div class="player-mask"><!-- <a href="/players/{slug}"> -->
        <img class="player-img" src="{photo}"><h2 class="top">{last}</h2>
        <p class="bottom">{first}</p><h2 class="player-mask-point">{number}</h2></div>'''


class IdentityTests(unittest.TestCase):
    def test_slug_fallback_and_exact_match_with_duplicate_card(self):
        a = card('https://example.com/organizer/people/1/photo.png', 'john-smith', '7')
        b = card('https://example.com/noimage.png', 'john-smith', '7')
        self.assertEqual(parse_players(b)[0]['external_id'], 'slug:john-smith')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            matched = json.dumps(['AAA', '7', 'J. Smith'])
            mismatch = json.dumps(['AAA', '8', 'J. Smith'])
            review = dict(players={}, teams={'3':{'team_name':'Team A'}},
                          team_matches={'AAA':None}, player_matches={matched:None, mismatch:None})
            (root/'identities.json').write_text(json.dumps(review))
            (root/'players.html').write_text(a+b)
            (root/'selected-games.json').write_text('[1]')
            (root/'game-1.json').write_text(json.dumps({'records':[{'payload':{'team_code':'AAA','team_name':'Team A'}}]}))
            result = match_directory(root)
            self.assertEqual(result['unmatched_players'], [mismatch])
            updated = json.loads((root/'identities.json').read_text())
            self.assertEqual(updated['player_matches'][matched], '1')
            self.assertEqual(updated['team_matches']['AAA'], '3')
            self.assertTrue((root/'identity-match-evidence.json').exists())
