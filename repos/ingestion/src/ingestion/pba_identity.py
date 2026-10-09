"""Conservative saved-directory matching with an auditable evidence report."""
import json
from pathlib import Path
import re

from .pba_workflow import save
from .sources.pba_directory import DirectoryDocument


def normalized(text):
    return re.sub(r'[^a-z0-9]', '', text.casefold())


def match_directory(directory):
    directory = Path(directory)
    review = json.loads((directory / 'identities.json').read_text())
    doc = DirectoryDocument()
    doc.feed((directory / 'players.html').read_text(encoding='utf-8'))
    candidates = []
    for card in doc.root.find(cls='player-mask'):
        first, last = card.find('p', 'bottom')[0].text(), card.find('h2', 'top')[0].text()
        jersey = card.find(cls='player-mask-point')[0].text()
        photo = card.find('img', 'player-img')[0].attrs['src']
        number = re.search(r'/people/(\d+)/', photo)
        slug = re.search(r'/players/([a-z0-9-]+)', card.text())
        external = number[1] if number else 'slug:' + slug[1]
        candidates.append(dict(external_id=external, name=f'{first} {last}', short_name=f'{first[0]}. {last}',
                               jersey=jersey, slug=slug[1] if slug else None))
    evidence = []
    for observation, current in review['player_matches'].items():
        if current is not None:
            continue
        team, jersey, name = json.loads(observation)
        by_name = [c for c in candidates if normalized(c['short_name']) == normalized(name)]
        exact = [c for c in by_name if c['jersey'] == jersey]
        # Duplicate cards may expose numeric and slug IDs for the same profile.
        if len(exact) > 1 and len({(c['name'], c['slug']) for c in exact}) == 1 and exact[0]['slug']:
            numeric = [c for c in exact if c['external_id'].isdigit()]
            if len(numeric) == 1:
                exact = numeric
        selected = exact[0]['external_id'] if len(exact) == 1 else None
        if selected is not None:
            review['player_matches'][observation] = selected
        evidence.append(dict(observation=observation, matched_external_id=selected,
                             rule='unique abbreviated name + jersey (directory evidence only)', candidates=by_name))
    team_names = {}
    for gid in json.loads((directory / 'selected-games.json').read_text()):
        for row in json.loads((directory / f'game-{gid}.json').read_text())['records']:
            p = row['payload']
            team_names.setdefault(p['team_code'], set()).add(normalized(p['team_name']))
    for code, current in review['team_matches'].items():
        if current is not None:
            continue
        matches = [key for key, team in review['teams'].items() if normalized(team['team_name']) in team_names.get(code, set())]
        if len(matches) == 1:
            review['team_matches'][code] = matches[0]
    save(directory / 'identity-match-evidence.json', evidence)
    save(directory / 'identities.json', review)
    return dict(unmatched_players=[k for k,v in review['player_matches'].items() if v is None],
                unmatched_teams=[k for k,v in review['team_matches'].items() if v is None])
