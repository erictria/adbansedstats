"""Prepare cached PBA games, review identities, then normalize without guessing."""
from dataclasses import asdict
from contextlib import nullcontext
from .domain_storage import DomainStore
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import re
import time
from uuid import NAMESPACE_URL, uuid4, uuid5

from .models import RawRecord, IngestedRecord
from .pba_cleaning import PbaCleaner
from .sources.pba import Document, fetch_html, parse_box_score, parse_schedule
from .sources.pba_directory import parse_players, parse_teams
from .schemas import League, Tournament, Player, Team, Game, GameStatistics, TeamGameStatistics


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    temporary.replace(path)


def metadata(html, records):
    doc = Document()
    doc.feed(html)
    boards = [node for node in doc.root.find() if node.attrs.get('id') == 'scoreboard']
    if len(boards) != 1:
        raise ValueError('Expected one scoreboard')
    board = boards[0]
    codes = [n.text() for n in board.find(cls='team_code')]
    scores = [int(n.text()) for n in board.find(cls='team_score')]
    totals = {r.payload['team_code']: int(r.payload['stats']['PTS']) for r in records if r.entity == 'team_game_stats'}
    if len(codes) != 2 or len(scores) != 2 or dict(zip(codes, scores)) != totals:
        raise ValueError('Scoreboard and box-score team totals disagree')
    details = {}
    for node in doc.root.find(cls='game-detail'):
        labels, values = node.find('h6'), node.find('span')
        if labels and values:
            details[labels[0].text()] = values[0].text()
    quarters = {}
    for node in board.find('tr'):
        labels = node.find(cls='score-team-code')
        if labels:
            quarters[labels[0].text()] = [int(n.text()) for n in node.find(cls='period-score')]
    for code, score in zip(codes, scores):
        if code in quarters and sum(quarters[code]) != score:
            raise ValueError('Quarter scores disagree with total')
    period = board.find(cls='period')
    clock = board.find(cls='clock')
    number = re.search(r'\d+', period[0].text()) if period else None
    return dict(team_codes=codes, team_scores=scores, period_scores=quarters,
                competition_name=details.get('Competition'), venue=details.get('Venue'),
                date_time_raw=details.get('Game Details'),
                period=int(number[0]) if number else None, clock=clock[0].text() if clock else None)


def observation(record):
    p = record.payload
    return json.dumps([p['team_code'], p['stats']['NO.'], p['stats']['PLAYER']], ensure_ascii=False)


def prepare(tournament, directory, *, players_html=None, teams_html=None, limit=None, refresh=False):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    review_path = directory / 'identities.json'
    review = json.loads(review_path.read_text()) if review_path.exists() else dict(
        tournament=tournament, league_id=str(uuid4()), tournament_id=str(uuid4()),
        players={}, teams={}, player_matches={}, team_matches={}, games={}, roster_memberships=[])
    if review['tournament'] != tournament:
        raise ValueError('Use a separate work directory for each tournament')
    for path, parser, key, identity in [(players_html, parse_players, 'players', 'player_id'),
                                       (teams_html, parse_teams, 'teams', 'team_id')]:
        if path:
            for item in parser(Path(path).read_text(encoding='utf-8')):
                external = item['external_id']
                # Never overwrite reviewed identities or names on re-prepare.
                review[key].setdefault(external, dict(item, **{identity: str(uuid4())}))
    schedule_path = directory / 'schedule.html'
    if refresh or not schedule_path.exists():
        schedule_path.write_text(fetch_html(tournament), encoding='utf-8')
    schedule = [g for g in parse_schedule(schedule_path.read_text(), tournament) if g.status.casefold() == 'final']
    if limit is not None:
        if limit < 1:
            raise ValueError('limit must be positive')
        schedule = schedule[:limit]
    if not schedule:
        raise ValueError('No final games available')
    selected = []
    for game in schedule:
        logging.getLogger(__name__).info('Preparing PBA game %s', game.game_id)
        html_path = directory / f'game-{game.game_id}.html'
        fetched_path = directory / f'game-{game.game_id}.retrieved.json'
        if refresh or not html_path.exists():
            html_path.write_text(fetch_html(tournament, game.game_id), encoding='utf-8')
            save(fetched_path, datetime.now(timezone.utc).isoformat())
            time.sleep(1)
        # Saved HTML without acquisition metadata has unknown retrieval time.
        retrieved = json.loads(fetched_path.read_text()) if fetched_path.exists() else None
        html = html_path.read_text(encoding='utf-8')
        records = parse_box_score(html, tournament, game.game_id)
        meta = metadata(html, records)
        review['games'].setdefault(str(game.game_id), str(uuid4()))
        for raw in records:
            payload = raw.payload
            review['team_matches'].setdefault(payload['team_code'], None)
            if raw.entity == 'player_game_stats':
                key = observation(raw)
                review['player_matches'].setdefault(key, None)
        save(directory / f'game-{game.game_id}.json', dict(metadata=meta, records=[asdict(r) for r in records], retrieved_at=retrieved))
        selected.append(game.game_id)
        save(review_path, review)
    save(directory / 'selected-games.json', selected)
    return dict(games=len(selected), unmatched_teams=sum(v is None for v in review['team_matches'].values()),
                unmatched_players=sum(v is None for v in review['player_matches'].values()), identities=str(review_path))


def build(directory):
    directory = Path(directory)
    review = json.loads((directory / 'identities.json').read_text())
    tournament = review['tournament']
    selected = json.loads((directory / 'selected-games.json').read_text())
    if not selected or len(set(selected)) != len(selected):
        raise ValueError('Selected games must be nonempty and unique')
    result = dict(leagues=[], tournaments=[], teams=[], players=[], games=[], tournament_teams=[],
                  game_statistics=[], team_game_statistics=[], source_mappings=[],
                  roster_memberships=list(review.get('roster_memberships', [])))
    unresolved, staging = [], []
    teams, players = {}, {}
    def mapping(entity, source, external, internal, scope=''):
        result['source_mappings'].append(dict(source=source, entity_type=entity, external_id=str(external), internal_id=internal, scope=scope))
    result['leagues'] = [League(league_id=review['league_id'], league_name='Philippine Basketball Association', abbreviation='PBA', slug='pba', website_url='https://www.pba.ph').model_dump(mode='json')]
    mapping('league', 'pba-website', 'pba', review['league_id'])
    mapping('tournament', 'pba-actech', tournament, review['tournament_id'])
    for game_id in selected:
        package = json.loads((directory / f'game-{game_id}.json').read_text())
        meta = package['metadata']
        records = [RawRecord(**r) for r in package['records']]
        if any(r.payload['tournament'] != tournament or r.payload['game_id'] != game_id for r in records):
            raise ValueError('Cached record belongs to a different tournament/game')
        gid = review['games'][str(game_id)]
        for raw in records:
            if raw.entity == 'player_game_stats':
                key = observation(raw)
                external = review['player_matches'].get(key)
                if external is None or external not in review['players']:
                    unresolved.append(dict(game_id=game_id, observation=key, reason='Unconfirmed player mapping'))
        resolved_teams = []
        for code in meta['team_codes']:
            external = review['team_matches'].get(code)
            if external is None or external not in review['teams']:
                unresolved.append(dict(game_id=game_id, team=code, reason='Unconfirmed team mapping'))
                continue
            team = Team(**review['teams'][external])
            if team.external_id != external:
                raise ValueError('Team catalog key differs from external_id')
            teams[external] = team.model_dump(mode='json')
            resolved_teams.append(str(team.team_id))
        if len(resolved_teams) != 2:
            continue
        provenance = dict(source='pba-actech', retrieved_at=package['retrieved_at'])
        game = Game(game_id=gid, tournament_id=review['tournament_id'], team_id_1=resolved_teams[0], team_id_2=resolved_teams[1],
                    external_id=str(game_id), tournament=tournament, status='final',
                    competition_name=meta['competition_name'], venue=meta['venue'], date_time_raw=meta['date_time_raw'],
                    period=meta['period'], clock=meta['clock'], team_1_score=meta['team_scores'][0], team_2_score=meta['team_scores'][1],
                    team_1_period_scores=meta['period_scores'].get(meta['team_codes'][0]), team_2_period_scores=meta['period_scores'].get(meta['team_codes'][1]),
                    source_url=records[0].payload['source_url'], **provenance)
        result['games'].append(game.model_dump(mode='json'))
        mapping('game', 'pba-actech', game_id, gid, tournament)
        for raw in records:
            cleaned = PbaCleaner().clean(raw)
            staging.append(IngestedRecord(raw, cleaned))
            payload, stats = cleaned.payload, dict(cleaned.payload['stats'])
            tid = teams[review['team_matches'][payload['team_code']]]['team_id']
            for field in ('player_name', 'jersey_number', 'position'):
                stats.pop(field)
            for name in ('field_goals', 'two_pointers', 'three_pointers', 'four_pointers', 'free_throws'):
                for suffix, value in stats.pop(name).items():
                    stats[f'{name}_{suffix}'] = value
            common = dict(game_id=gid, team_id=tid, **stats, **provenance)
            if raw.entity == 'team_game_stats':
                result['team_game_statistics'].append(TeamGameStatistics(**common).model_dump(mode='json'))
            else:
                key = observation(raw)
                external = review['player_matches'].get(key)
                if external is None or external not in review['players']:
                    continue
                player = Player(**review['players'][external])
                if player.external_id != external:
                    raise ValueError('Player catalog key differs from external_id')
                players[external] = player.model_dump(mode='json')
                minutes = raw.payload['stats']['MINS'].strip()
                status = 'dnp' if minutes.upper() == 'DNP' else 'played' if (stats['seconds_played'] or 0) > 0 else 'unknown'
                section = payload['section']
                result['game_statistics'].append(GameStatistics(**common, player_id=player.player_id,
                    player_name=payload['stats']['player_name'], jersey_number=payload['stats']['jersey_number'],
                    position=payload['stats']['position'], minutes_raw=minutes or None,
                    is_starter=True if section == 'starters' else False if section == 'bench' else None,
                    participation_status=status).model_dump(mode='json'))
    save(directory / 'unresolved.json', unresolved)
    if unresolved:
        raise ValueError(f'{len(unresolved)} unresolved identities; review {directory / "unresolved.json"}. No database writes performed.')
    if len({(r['game_id'], r['player_id']) for r in result['game_statistics']}) != len(result['game_statistics']):
        raise ValueError('Two rows resolve to the same player in one game')
    if len(result['games']) != len(selected):
        raise ValueError('Incomplete normalized game coverage')
    result['tournaments'] = [Tournament(tournament_id=review['tournament_id'], league_id=review['league_id'], tournament_name=result['games'][0]['competition_name'] or tournament, slug=tournament, external_id=tournament, source_url=result['games'][0]['source_url'].split('?')[0]).model_dump(mode='json')]
    # Treat the first observed game as the assumed season roster start. This is
    # an explicit proxy date, not a claim about a player's actual signing date.
    start = min(datetime.strptime(game['date_time_raw'], '%m/%d/%y %I:%M %p').date()
                for game in result['games'])
    manual_players = {row['player_id'] for row in result['roster_memberships']}
    appearances = {}
    for stat in result['game_statistics']:
        appearances.setdefault(stat['player_id'], []).append(stat)
    for player_id, stats in appearances.items():
        if player_id in manual_players:
            continue
        team_ids = {stat['team_id'] for stat in stats}
        if len(team_ids) != 1:
            raise ValueError(f'Player {player_id} appeared for multiple teams; add dated roster memberships manually')
        jerseys = {stat['jersey_number'] for stat in stats if stat['jersey_number']}
        team_id = next(iter(team_ids))
        result['roster_memberships'].append(dict(
            source='pba-assumed',
            roster_id=str(uuid5(NAMESPACE_URL, f'pba-roster:{review["tournament_id"]}:{player_id}:{team_id}')),
            player_id=player_id, team_id=team_id,
            tournament_id=review['tournament_id'], valid_from=start.isoformat(),
            valid_to=None, jersey_number=next(iter(jerseys)) if len(jerseys) == 1 else None))
    result['teams'], result['players'] = list(teams.values()), list(players.values())
    for external, team in teams.items():
        result['tournament_teams'].append(dict(tournament_id=review['tournament_id'], team_id=team['team_id']))
        mapping('team', 'pba-website', external, team['team_id'])
    for external, player in players.items():
        mapping('player', 'pba-website', external, player['player_id'])
    save(directory / 'normalized.json', result)
    return result, staging


def ingest(directory, store):
    normalized, staging = build(directory)
    # Shared transaction: identity conflicts or staging failures roll everything back.
    now = datetime.now(timezone.utc)
    run_id = str(uuid4())
    with store.transaction() as connection:
        class TransactionStore(DomainStore):
            def transaction(self):
                return nullcontext(connection)
        counts = TransactionStore().write_models(**normalized)
        connection.execute('INSERT INTO ingestion_runs VALUES (?, ?, ?, ?, ?)',
                           [run_id, 'pba-actech', now, now, len(staging)])
        for record in staging:
            raw, clean = record.raw, record.clean
            connection.execute("""INSERT INTO records VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (source, entity, external_id) DO UPDATE SET
                payload_json=excluded.payload_json, raw_json=excluded.raw_json,
                updated_at=excluded.updated_at, run_id=excluded.run_id""",
                ['pba-actech', clean.entity, clean.external_id,
                 json.dumps(clean.payload, allow_nan=False), json.dumps(asdict(raw), allow_nan=False), now, run_id])
    return dict(normalized=counts, staged=len(staging))
