from datetime import datetime, timezone
from .schemas import TournamentTeam, RosterMembership, SourceMapping, TeamGameStatistics
"""Shared validated domain writes for DuckDB and SQLite."""
from pydantic import HttpUrl
from .schemas import Game, GameStatistics, Player, Team, League, Tournament


class DomainStore:
    def write_models(self, *, leagues=(), tournaments=(), players=(), teams=(), games=(), game_statistics=(), tournament_teams=(), roster_memberships=(), source_mappings=(), team_game_statistics=()):
        """Atomic full-row upserts in dependency order. Pass existing UUIDs on reruns.

        Accepts schema instances or dictionaries. Omitted optional values replace
        existing values with NULL; this is not a partial-update API.
        """
        batches = []
        for table, model, keys, items in (
            ('leagues', League, ('league_id',), leagues),
            ('tournaments', Tournament, ('tournament_id',), tournaments),
            ('players', Player, ('player_id',), players),
            ('teams', Team, ('team_id',), teams),
            ('tournament_teams', TournamentTeam, ('tournament_id', 'team_id'), tournament_teams),
            ('roster_memberships', RosterMembership, ('roster_id',), roster_memberships),
            ('games', Game, ('game_id',), games),
            ('game_statistics', GameStatistics, ('game_id', 'player_id'), game_statistics),
            ('team_game_statistics', TeamGameStatistics, ('game_id', 'team_id'), team_game_statistics),
            ('source_mappings', SourceMapping, ('source', 'entity_type', 'scope', 'external_id'), source_mappings),
        ):
            rows = [model.model_validate(item.model_dump() if isinstance(item, model) else item)
                    for item in items]
            identities = [tuple(getattr(row, key) for key in keys) for row in rows]
            if len(set(identities)) != len(identities):
                raise ValueError(f'Duplicate identities in {table} batch')
            for row in rows:
                if isinstance(row, Game) and row.scheduled_at is not None and row.scheduled_at.utcoffset() is None:
                    raise ValueError('scheduled_at must include a timezone; use date_time_raw if unknown')
            batches.append((table, keys, rows))
        with self.transaction() as connection:
            for table, keys, rows in batches:
                for row in rows:
                    validate_relationships(connection, row)
                    if isinstance(row, (GameStatistics, TeamGameStatistics)):
                        game = connection.execute('SELECT team_id_1, team_id_2 FROM games WHERE game_id=?', [row.game_id]).fetchone()
                        if game is None or str(row.team_id) not in {str(team) for team in game}:
                            raise ValueError('Statistics team must participate in the referenced game')
                    if isinstance(row, Game):
                        if row.tournament_id is not None:
                            parent = connection.execute('SELECT tournament_id FROM tournaments WHERE tournament_id=?', [row.tournament_id]).fetchone()
                            if parent is None:
                                raise ValueError('Game references an unknown tournament')
                        invalid = connection.execute('SELECT count(*) FROM game_statistics WHERE game_id=? AND team_id NOT IN (?, ?)', [row.game_id, row.team_id_1, row.team_id_2]).fetchone()[0]
                        if invalid:
                            raise ValueError('Changing teams would invalidate existing game statistics')
                    values = row.model_dump()
                    values["updated_at"] = datetime.now(timezone.utc)
                    columns = list(values)
                    params = [str(v) if isinstance(v, HttpUrl) else v for v in values.values()]
                    where = ' AND '.join(f'{key}=?' for key in keys)
                    key_values = [values[key] for key in keys]
                    existing = connection.execute(f"SELECT {', '.join(columns)} FROM {table} WHERE {where}", key_values).fetchone()
                    if existing is None:
                        connection.execute(f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({', '.join('?' for _ in columns)})", params)
                    else:
                        changes = [(c, v) for c, v, old in zip(columns, params, existing) if c not in keys and v != old]
                        if changes:
                            connection.execute(f"UPDATE {table} SET {', '.join(c + '=?' for c, _ in changes)} WHERE {where}", [v for _, v in changes] + key_values)
        return {table: len(rows) for table, _, rows in batches}


def validate_relationships(connection, row):
    def exists(table, key, value):
        if connection.execute(f'SELECT 1 FROM {table} WHERE {key}=?', [value]).fetchone() is None:
            raise ValueError(f'Unknown {table} reference: {value}')

    def member(tournament_id, team_id):
        if connection.execute('SELECT 1 FROM tournament_teams WHERE tournament_id=? AND team_id=?', [tournament_id, team_id]).fetchone() is None:
            raise ValueError('Team must be registered in the tournament')

    if isinstance(row, TournamentTeam):
        exists('tournaments', 'tournament_id', row.tournament_id)
        exists('teams', 'team_id', row.team_id)
    if isinstance(row, RosterMembership):
        exists('players', 'player_id', row.player_id)
        member(row.tournament_id, row.team_id)
        overlap = connection.execute("""SELECT roster_id FROM roster_memberships
            WHERE player_id=? AND tournament_id=? AND roster_id<>?
            AND (valid_to IS NULL OR valid_to>=?) AND (? IS NULL OR valid_from<=?)""",
            [row.player_id, row.tournament_id, row.roster_id, row.valid_from, row.valid_to, row.valid_to]).fetchone()
        if overlap:
            raise ValueError('Overlapping roster intervals for this player and tournament')
    if isinstance(row, SourceMapping):
        table = {'league':'leagues','tournament':'tournaments','team':'teams','player':'players','game':'games'}[row.entity_type]
        exists(table, row.entity_type + '_id', row.internal_id)
        prior = connection.execute('SELECT internal_id FROM source_mappings WHERE source=? AND entity_type=? AND scope=? AND external_id=?', [row.source, row.entity_type, row.scope, row.external_id]).fetchone()
        if prior and str(prior[0]) != str(row.internal_id):
            raise ValueError('Source ID is already mapped to a different identity')
    if isinstance(row, Game):
        prior = connection.execute('SELECT tournament_id FROM games WHERE game_id=?', [row.game_id]).fetchone()
        if row.tournament_id is None:
            if prior is None or prior[0] is not None:
                raise ValueError('New games require tournament_id; existing links cannot be cleared')
        else:
            member(row.tournament_id, row.team_id_1)
            member(row.tournament_id, row.team_id_2)
        invalid = connection.execute('SELECT 1 FROM team_game_statistics WHERE game_id=? AND team_id NOT IN (?, ?)', [row.game_id, row.team_id_1, row.team_id_2]).fetchone()
        if invalid:
            raise ValueError('Changing teams would invalidate team statistics')
