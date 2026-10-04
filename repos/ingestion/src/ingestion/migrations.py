"""Additive upgrades preserve legacy rows; new domain writes enforce stricter rules."""
TABLES = ('leagues', 'tournaments', 'players', 'teams', 'games', 'game_statistics',
          'tournament_teams', 'roster_memberships', 'source_mappings', 'team_game_statistics')


def upgrade(connection, backend):
    timestamp = 'TIMESTAMPTZ' if backend == 'duckdb' else 'TEXT'
    for table in TABLES:
        columns = {r[1] for r in connection.execute(f"PRAGMA table_info('{table}')").fetchall()}
        for name, kind in [('source', 'VARCHAR'), ('retrieved_at', timestamp), ('updated_at', timestamp)]:
            if name not in columns:
                connection.execute(f'ALTER TABLE {table} ADD COLUMN {name} {kind}')
        if table == 'game_statistics' and 'participation_status' not in columns:
            connection.execute("ALTER TABLE game_statistics ADD COLUMN participation_status VARCHAR DEFAULT 'unknown'")
    connection.execute('DROP VIEW IF EXISTS player_tournament_statistics')
    connection.execute('''CREATE VIEW player_tournament_statistics AS
        SELECT g.tournament_id, s.player_id, COUNT(*) AS games_played,
               SUM(s.points) AS points, AVG(s.points) AS points_per_game,
               AVG(s.rebounds) AS rebounds_per_game, AVG(s.assists) AS assists_per_game,
               CASE WHEN COUNT(s.field_goals_made)=COUNT(*) AND COUNT(s.field_goals_attempted)=COUNT(*)
                    THEN 100.0 * SUM(s.field_goals_made) / NULLIF(SUM(s.field_goals_attempted), 0)
                    ELSE NULL END AS field_goal_percentage
        FROM game_statistics s JOIN games g ON g.game_id=s.game_id
        WHERE s.participation_status='played' AND g.status='final'
        GROUP BY g.tournament_id, s.player_id''')
