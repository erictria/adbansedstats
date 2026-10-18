"""Tournament-scoped read queries. IDs are parameters; SQL never interpolates input."""
from datetime import date, datetime
from uuid import UUID

import duckdb


def rows(connection, sql, params=()):
    cursor = connection.execute(sql, params)
    names = [column[0] for column in cursor.description]
    return [dict(zip(names, (str(v) if isinstance(v, (UUID, date, datetime)) else v for v in item)))
            for item in cursor.fetchall()]


def one(connection, sql, params=()):
    result = rows(connection, sql, params)
    return result[0] if result else None


def open_database(path):
    return duckdb.connect(str(path), read_only=True)


def tournaments(connection):
    return rows(connection, """SELECT t.tournament_id, t.tournament_name, t.season,
        t.slug, l.league_id, l.league_name, l.abbreviation AS league_abbreviation,
        (SELECT count(*) FROM games g WHERE g.tournament_id=t.tournament_id) AS games
        FROM tournaments t JOIN leagues l ON l.league_id=t.league_id
        ORDER BY l.league_name, t.tournament_name""")


def tournament(connection, tournament_id):
    return one(connection, """SELECT t.tournament_id, t.tournament_name, t.season,
        t.slug, l.league_id, l.league_name, l.abbreviation AS league_abbreviation
        FROM tournaments t JOIN leagues l ON l.league_id=t.league_id
        WHERE t.tournament_id=?""", [tournament_id])


PLAYER_TOTALS = """SELECT p.player_id, p.player_name, p.player_short_name, p.slug,
    p.photo_url, r.team_id, t.team_name, r.jersey_number,
    count(s.game_id) FILTER (WHERE s.participation_status='played') AS games,
    coalesce(sum(s.points) FILTER (WHERE s.participation_status='played'), 0) AS points_total,
    coalesce(sum(s.rebounds) FILTER (WHERE s.participation_status='played'), 0) AS rebounds_total,
    coalesce(sum(s.assists) FILTER (WHERE s.participation_status='played'), 0) AS assists_total,
    coalesce(sum(s.steals) FILTER (WHERE s.participation_status='played'), 0) AS steals_total,
    coalesce(sum(s.blocks) FILTER (WHERE s.participation_status='played'), 0) AS blocks_total,
    coalesce(sum(s.turnovers) FILTER (WHERE s.participation_status='played'), 0) AS turnovers_total,
    coalesce(sum(s.three_pointers_made) FILTER (WHERE s.participation_status='played'), 0) AS threes_total,
    coalesce(sum(s.four_pointers_made) FILTER (WHERE s.participation_status='played'), 0) AS fours_total,
    coalesce(sum(s.seconds_played) FILTER (WHERE s.participation_status='played'), 0) AS seconds_total
    FROM roster_memberships r JOIN players p ON p.player_id=r.player_id
    JOIN teams t ON t.team_id=r.team_id
    LEFT JOIN game_statistics s ON s.player_id=r.player_id AND s.team_id=r.team_id
      AND s.game_id IN (SELECT game_id FROM games WHERE tournament_id=?)
    WHERE r.tournament_id=?
    GROUP BY p.player_id, p.player_name, p.player_short_name, p.slug, p.photo_url,
      r.team_id, t.team_name, r.jersey_number"""


def players(connection, tournament_id):
    return rows(connection, f"SELECT * FROM ({PLAYER_TOTALS}) ORDER BY points_total DESC, player_name",
                [tournament_id, tournament_id])


def player(connection, tournament_id, player_id):
    return one(connection, f"SELECT * FROM ({PLAYER_TOTALS}) WHERE player_id=?",
               [tournament_id, tournament_id, player_id])


TEAM_LIST = """SELECT t.team_id, t.team_name, t.slug, t.logo_url,
    count(g.game_id) AS games,
    count(g.game_id) FILTER (WHERE (g.team_id_1=t.team_id AND g.team_1_score>g.team_2_score)
      OR (g.team_id_2=t.team_id AND g.team_2_score>g.team_1_score)) AS wins,
    count(g.game_id) FILTER (WHERE (g.team_id_1=t.team_id AND g.team_1_score<g.team_2_score)
      OR (g.team_id_2=t.team_id AND g.team_2_score<g.team_1_score)) AS losses,
    count(g.game_id) FILTER (WHERE g.team_1_score=g.team_2_score) AS draws,
    coalesce(sum(CASE WHEN g.team_id_1=t.team_id THEN g.team_1_score ELSE g.team_2_score END),0) AS points_for,
    coalesce(sum(CASE WHEN g.team_id_1=t.team_id THEN g.team_2_score ELSE g.team_1_score END),0) AS points_against,
    (SELECT count(*) FROM roster_memberships r WHERE r.tournament_id=? AND r.team_id=t.team_id) AS roster_count
    FROM tournament_teams tt JOIN teams t ON t.team_id=tt.team_id
    LEFT JOIN games g ON g.tournament_id=tt.tournament_id AND g.status='final'
      AND (g.team_id_1=t.team_id OR g.team_id_2=t.team_id)
    WHERE tt.tournament_id=? GROUP BY t.team_id, t.team_name, t.slug, t.logo_url"""


def teams(connection, tournament_id):
    return rows(connection, f"SELECT * FROM ({TEAM_LIST}) ORDER BY wins DESC, team_name",
                [tournament_id, tournament_id])


def team(connection, tournament_id, team_id):
    return one(connection, f"SELECT * FROM ({TEAM_LIST}) WHERE team_id=?",
               [tournament_id, tournament_id, team_id])


GAME_LIST = """SELECT g.game_id, g.external_id, g.tournament_id, g.date_time_raw,
    g.status, g.venue, g.team_id_1, a.team_name AS team_1_name, g.team_1_score,
    g.team_1_period_scores, g.team_id_2, b.team_name AS team_2_name,
    g.team_2_score, g.team_2_period_scores
    FROM games g JOIN teams a ON a.team_id=g.team_id_1
    JOIN teams b ON b.team_id=g.team_id_2 WHERE g.tournament_id=?"""


def games(connection, tournament_id):
    return rows(connection, f"SELECT * FROM ({GAME_LIST}) ORDER BY try_strptime(date_time_raw, '%m/%d/%y %I:%M %p') DESC NULLS LAST, external_id DESC", [tournament_id])


def game(connection, tournament_id, game_id):
    return one(connection, f"SELECT * FROM ({GAME_LIST}) WHERE game_id=?", [tournament_id, game_id])


def player_games(connection, tournament_id, player_id):
    return rows(connection, """SELECT s.game_id, g.external_id, g.date_time_raw, s.team_id,
      CASE WHEN s.team_id=g.team_id_1 THEN g.team_id_2 ELSE g.team_id_1 END AS opponent_id,
      CASE WHEN s.team_id=g.team_id_1 THEN b.team_name ELSE a.team_name END AS opponent_name,
      s.jersey_number, s.is_starter, s.participation_status, s.minutes_raw,
      s.points, s.rebounds, s.assists, s.steals, s.blocks, s.turnovers,
      s.field_goals_made, s.field_goals_attempted, s.three_pointers_made,
      s.three_pointers_attempted, s.four_pointers_made, s.four_pointers_attempted,
      s.free_throws_made, s.free_throws_attempted, s.plus_minus
      FROM game_statistics s JOIN games g ON g.game_id=s.game_id
      JOIN teams a ON a.team_id=g.team_id_1 JOIN teams b ON b.team_id=g.team_id_2
      WHERE g.tournament_id=? AND s.player_id=?
      ORDER BY try_strptime(g.date_time_raw, '%m/%d/%y %I:%M %p') DESC NULLS LAST""",
      [tournament_id, player_id])


def game_box_score(connection, tournament_id, game_id):
    return rows(connection, """SELECT s.*, p.player_name, p.photo_url
      FROM game_statistics s JOIN games g ON g.game_id=s.game_id
      JOIN players p ON p.player_id=s.player_id
      WHERE g.tournament_id=? AND g.game_id=?
      ORDER BY s.team_id, s.is_starter DESC NULLS LAST, s.points DESC NULLS LAST""",
      [tournament_id, game_id])
