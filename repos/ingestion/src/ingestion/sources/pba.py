"""HTTP retrieval and parsing of the PBA's server-rendered box scores."""
from dataclasses import dataclass, field
from html.parser import HTMLParser
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin, urlsplit, parse_qs
from urllib.request import Request, urlopen

from ..models import RawRecord

BASE_URL = 'https://pba-api01.actech2.com'
HEADERS = ['NO.', 'PLAYER', 'POS', 'MINS', 'PTS', 'FG', 'FG %', '2P', '2P %',
           '3P', '3P %', '4P', '4P %', 'FT', 'FT %', 'OFF', 'DEF', 'REB',
           'AST', 'TO', 'STL', 'BLK', 'PF', 'Fls on:', '+/-']


@dataclass
class Node:
    tag: str
    attrs: dict = field(default_factory=dict)
    children: list = field(default_factory=list)

    def text(self):
        return ' '.join(''.join(c if isinstance(c, str) else c.text() + ' '
                                for c in self.children).split())

    def find(self, tag=None, cls=None):
        found = []
        for child in self.children:
            if isinstance(child, Node):
                if (tag is None or child.tag == tag) and (cls is None or cls in child.attrs.get('class', '').split()):
                    found.append(child)
                found.extend(child.find(tag, cls))
        return found


class Document(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node('document')
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        node = Node(tag, dict(attrs))
        self.stack[-1].children.append(node)
        if tag not in {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.stack[-1].children.append(Node(tag, dict(attrs)))

    def handle_endtag(self, tag):
        for i in range(len(self.stack)-1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                break

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def game_url(tournament: str, game_id: int) -> str:
    if not re.fullmatch(r'[a-z0-9-]+', tournament) or game_id <= 0:
        raise ValueError('Use a tournament slug and positive game ID')
    return f'{BASE_URL}/tournaments/{tournament}?{urlencode({"game_id": game_id})}'


def fetch_html(tournament: str, game_id: int | None = None, timeout: float = 30) -> str:
    url = game_url(tournament, game_id or 1)
    if game_id is None:
        url = url.split('?')[0]
    request = Request(url, headers={'User-Agent': 'AdbansedStats/0.1', 'Accept': 'text/html'})
    try:
        with urlopen(request, timeout=timeout) as response:
            html = response.read().decode(response.headers.get_content_charset() or 'utf-8')
    except HTTPError as exc:
        raise RuntimeError(f'PBA returned HTTP {exc.code} for {url}; no data imported') from exc
    except (URLError, TimeoutError) as exc:
        raise RuntimeError(f'Could not retrieve {url}: {exc}') from exc
    if 'challenge-platform' in html or '<title>Just a moment...' in html:
        raise ValueError('PBA returned a verification page, not game data')
    return html


def parse_box_score(html: str, tournament: str, game_id: int) -> list[RawRecord]:
    url = game_url(tournament, game_id)
    document = Document()
    document.feed(html)
    titles = document.root.find(cls='box-score_title')
    tables = document.root.find('table', 'box-score')
    if len(tables) != 2 or len(titles) != 2:
        raise ValueError('Expected two team headings and box-score tables; game may be unavailable or page layout changed')
    records = []
    for title, table in zip(titles, tables):
        codes, names = title.find(cls='team_code'), title.find(cls='team_name')
        if len(codes) != 1 or len(names) != 1 or not codes[0].text() or not names[0].text():
            raise ValueError('Missing team identity')
        code, name = codes[0].text(), names[0].text()
        rows = table.find('tr')
        if not rows or [c.text() for c in rows[0].find('th')] != HEADERS:
            raise ValueError('Unexpected PBA box-score columns')
        section = None
        totals = 0
        players = 0
        for row in rows[1:]:
            classes = row.attrs.get('class', '').split()
            if 'bsheader_type' in classes:
                section = row.text().lower()
                continue
            if 'team-coach' in classes:
                continue  # Included in published team totals, not a player.
            cells = row.find('td')
            if len(cells) != len(HEADERS):
                raise ValueError(f'Unexpected row width for {code}: {len(cells)}')
            stats = dict(zip(HEADERS, (c.text() for c in cells)))
            total = 'team-totals' in classes
            if total:
                totals += 1
                identity = 'totals'
            else:
                players += 1
                if not stats['NO.'] or not stats['PLAYER']:
                    raise ValueError('Player row missing jersey number or name')
                identity = stats['NO.']
            records.append(RawRecord(
                'team_game_stats' if total else 'player_game_stats',
                f'{tournament}:{game_id}:{code}:{identity}',
                {'tournament': tournament, 'game_id': game_id, 'team_code': code,
                 'team_name': name, 'source_url': url, 'section': None if total else section,
                 'stats': stats},
            ))
        if totals != 1 or players == 0:
            raise ValueError(f'Incomplete box score for {code}')
    if len({r.external_id for r in records}) != len(records):
        raise ValueError('Duplicate team or jersey identity in box score')
    return records


class PbaSource:
    name = 'pba-actech'

    def __init__(self, tournament: str, game_id: int):
        self.tournament, self.game_id = tournament, game_id

    def fetch(self):
        return parse_box_score(fetch_html(self.tournament, self.game_id), self.tournament, self.game_id)


@dataclass(frozen=True)
class ScheduledGame:
    game_id: int
    url: str
    status: str
    teams: list[str]


def parse_schedule(html: str, tournament: str) -> list[ScheduledGame]:
    """Return unique games explicitly linked by the tournament, in page order."""
    base = game_url(tournament, 1).split('?')[0]
    expected = urlsplit(base)
    document = Document()
    document.feed(html)
    games = {}
    for link in document.root.find('a', 'schedule-box'):
        url = urljoin(base, link.attrs.get('href', ''))
        parts = urlsplit(url)
        if parts.netloc != expected.netloc or parts.path != expected.path:
            continue
        ids = parse_qs(parts.query).get('game_id', [])
        if len(ids) != 1 or not ids[0].isdigit() or int(ids[0]) <= 0:
            raise ValueError('Schedule link has an invalid game ID')
        game_id = int(ids[0])
        details = link.find(cls='schedule-details')
        teams = [team.text() for team in link.find(cls='team')]
        game = ScheduledGame(game_id, game_url(tournament, game_id),
                             details[0].text() if details else 'Unknown', teams)
        if game_id in games and games[game_id] != game:
            raise ValueError(f'Conflicting schedule entries for game {game_id}')
        games[game_id] = game
    if not games:
        raise ValueError('No schedule games found; tournament may be empty or unavailable')
    return list(games.values())


def discover_games(tournament: str) -> list[ScheduledGame]:
    return parse_schedule(fetch_html(tournament), tournament)
