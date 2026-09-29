"""Typed box-score fields. Percentages retain the provider's 0–100 scale."""
import re
from .cleaning import DefaultCleaner
from .models import CleanRecord

COUNTS = {'PTS': 'points', 'OFF': 'offensive_rebounds', 'DEF': 'defensive_rebounds',
          'REB': 'rebounds', 'AST': 'assists', 'TO': 'turnovers', 'STL': 'steals',
          'BLK': 'blocks', 'PF': 'personal_fouls', 'Fls on:': 'fouls_drawn', '+/-': 'plus_minus'}
SHOTS = {'FG': 'field_goals', '2P': 'two_pointers', '3P': 'three_pointers',
         '4P': 'four_pointers', 'FT': 'free_throws'}


class PbaCleaner(DefaultCleaner):
    def clean(self, record):
        base = super().clean(record)
        payload = dict(base.payload)
        stats = payload.pop('stats')
        cleaned = {'jersey_number': stats['NO.'] or None, 'player_name': stats['PLAYER'],
                   'position': stats['POS'] or None}
        missing = {'', '-', '--', 'N/A', 'DNP'}
        for column, name in COUNTS.items():
            value = stats[column]
            cleaned[name] = None if value.upper() in missing else int(value)
        minutes = stats['MINS']
        if minutes.upper() in missing:
            cleaned['seconds_played'] = None
        else:
            match = re.fullmatch(r'(\d+):([0-5]\d)', minutes)
            if not match:
                raise ValueError(f'Invalid minutes: {minutes}')
            cleaned['seconds_played'] = int(match[1])*60 + int(match[2])
        for column, name in SHOTS.items():
            value = stats[column]
            if value.upper() in missing:
                made = attempted = None
            else:
                match = re.fullmatch(r'(\d+)-(\d+)', value)
                if not match or int(match[1]) > int(match[2]):
                    raise ValueError(f'Invalid shooting value: {value}')
                made, attempted = int(match[1]), int(match[2])
            pct = stats[column + ' %'].rstrip('%')
            percentage = None if pct.upper() in missing else float(pct)
            if percentage is not None and not 0 <= percentage <= 100:
                raise ValueError(f'Invalid percentage: {pct}')
            cleaned[name] = {'made': made, 'attempted': attempted, 'percentage': percentage}
        payload['stats'] = cleaned
        return CleanRecord(base.entity, base.external_id, payload)
