"""Shared validated domain writes for DuckDB and SQLite."""
from pydantic import HttpUrl
from .schemas import Game, GameStatistics, Player, Team


class DomainStore:
    def write_models(self, *, players=(), teams=(), games=(), game_statistics=()):
        """Atomic full-row upserts in dependency order. Pass existing UUIDs on reruns.

        Accepts schema instances or dictionaries. Omitted optional values replace
        existing values with NULL; this is not a partial-update API.
        """
        batches = []
        for table, model, keys, items in (
            ('players', Player, ('player_id',), players),
            ('teams', Team, ('team_id',), teams),
            ('games', Game, ('game_id',), games),
            ('game_statistics', GameStatistics, ('game_id', 'player_id'), game_statistics),
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
                    if isinstance(row, GameStatistics):
                        game = connection.execute('SELECT team_id_1, team_id_2 FROM games WHERE game_id=?', [row.game_id]).fetchone()
                        if game is None or str(row.team_id) not in {str(team) for team in game}:
                            raise ValueError('Statistics team must participate in the referenced game')
                    if isinstance(row, Game):
                        invalid = connection.execute('SELECT count(*) FROM game_statistics WHERE game_id=? AND team_id NOT IN (?, ?)', [row.game_id, row.team_id_1, row.team_id_2]).fetchone()[0]
                        if invalid:
                            raise ValueError('Changing teams would invalidate existing game statistics')
                    values = row.model_dump()
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
