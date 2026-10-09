"""Parse saved PBA directory HTML; image-path IDs remain provider-specific."""
import re
from urllib.parse import urlsplit
from .pba import Document


class DirectoryDocument(Document):
    def handle_comment(self, data):
        # Preserve commented profile links as hints, not active page elements.
        self.stack[-1].children.append(data)


def parse_players(html):
    document = DirectoryDocument()
    document.feed(html)
    players = {}
    for card in document.root.find(cls='player-mask'):
        images = card.find('img', 'player-img')
        first = card.find('p', 'bottom')
        last = card.find('h2', 'top')
        if not images or not first or not last:
            raise ValueError('Unexpected player card layout')
        photo = images[0].attrs.get('src', '')
        match = re.search(r'/organizer/people/(\d+)/', urlsplit(photo).path)
        slug = re.search(r'/players/([a-z0-9-]+)', card.text())
        if not match and not slug:
            raise ValueError('Player has neither a numeric image-path ID nor a profile slug')
        external_id = match[1] if match else 'slug:' + slug[1]
        player = dict(external_id=external_id, player_name=f'{first[0].text()} {last[0].text()}',
                      player_short_name=f'{first[0].text()[0]}. {last[0].text()}',
                      photo_url=photo, slug=slug[1] if slug else None)
        if external_id in players and players[external_id] != player:
            raise ValueError('Conflicting player directory IDs')
        players[external_id] = player
    if not players:
        raise ValueError('No player cards found; save the loaded directory, not a challenge page')
    return list(players.values())


def parse_teams(html):
    document = Document()
    document.feed(html)
    teams = {}
    for link in document.root.find('a'):
        url = link.attrs.get('href', '')
        slug = re.fullmatch(r'/teams/([a-z0-9-]+)', urlsplit(url).path)
        if not slug:
            continue
        images = link.find('img')
        headings = link.find('h3')
        if not images or not headings:
            continue
        logo = images[0].attrs.get('src', '')
        match = re.search(r'/organizer/teams/(\d+)/', urlsplit(logo).path)
        if not match:
            raise ValueError('Team logo does not expose a provider ID')
        team = dict(external_id=match[1], team_name=headings[0].text(), slug=slug[1],
                    profile_url=f'https://www.pba.ph/teams/{slug[1]}', logo_url=logo)
        if match[1] in teams and teams[match[1]] != team:
            raise ValueError('Conflicting team directory IDs')
        teams[match[1]] = team
    if not teams:
        raise ValueError('No team cards found')
    return list(teams.values())
