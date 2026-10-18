"""Response models matching the read-only query projections."""
from uuid import UUID

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str


class Tournament(BaseModel):
    tournament_id: UUID
    tournament_name: str
    season: str | None
    slug: str | None
    league_id: UUID
    league_name: str
    league_abbreviation: str | None


class TournamentSummary(Tournament):
    games: int


class Player(BaseModel):
    player_id: UUID
    player_name: str
    player_short_name: str | None
    slug: str | None
    photo_url: str | None
    team_id: UUID
    team_name: str
    jersey_number: str | None
    games: int
    points_total: int
    rebounds_total: int
    assists_total: int
    steals_total: int
    blocks_total: int
    turnovers_total: int
    threes_total: int
    fours_total: int
    seconds_total: int


class Team(BaseModel):
    team_id: UUID
    team_name: str
    slug: str | None
    logo_url: str | None
    games: int
    wins: int
    losses: int
    draws: int
    points_for: int
    points_against: int
    roster_count: int


class Game(BaseModel):
    game_id: UUID
    external_id: str | None
    tournament_id: UUID
    date_time_raw: str | None
    status: str
    venue: str | None
    team_id_1: UUID
    team_1_name: str
    team_1_score: int | None
    team_1_period_scores: list[int] | None
    team_id_2: UUID
    team_2_name: str
    team_2_score: int | None
    team_2_period_scores: list[int] | None


class PlayerGame(BaseModel):
    game_id: UUID
    external_id: str | None
    date_time_raw: str | None
    team_id: UUID
    opponent_id: UUID
    opponent_name: str
    jersey_number: str | None
    is_starter: bool | None
    participation_status: str
    minutes_raw: str | None
    points: int | None
    rebounds: int | None
    assists: int | None
    steals: int | None
    blocks: int | None
    turnovers: int | None
    field_goals_made: int | None
    field_goals_attempted: int | None
    three_pointers_made: int | None
    three_pointers_attempted: int | None
    four_pointers_made: int | None
    four_pointers_attempted: int | None
    free_throws_made: int | None
    free_throws_attempted: int | None
    plus_minus: int | None


class BoxScore(BaseModel):
    game_id: UUID
    player_id: UUID
    team_id: UUID
    player_name: str
    photo_url: str | None
    jersey_number: str | None
    position: str | None = None
    is_starter: bool | None
    minutes_raw: str | None
    seconds_played: int | None
    points: int | None
    offensive_rebounds: int | None = None
    defensive_rebounds: int | None = None
    rebounds: int | None
    assists: int | None
    turnovers: int | None
    steals: int | None
    blocks: int | None
    personal_fouls: int | None = None
    fouls_drawn: int | None = None
    plus_minus: int | None
    field_goals_made: int | None
    field_goals_attempted: int | None
    field_goals_percentage: float | None = None
    two_pointers_made: int | None = None
    two_pointers_attempted: int | None = None
    two_pointers_percentage: float | None = None
    three_pointers_made: int | None
    three_pointers_attempted: int | None
    three_pointers_percentage: float | None = None
    four_pointers_made: int | None
    four_pointers_attempted: int | None
    four_pointers_percentage: float | None = None
    free_throws_made: int | None
    free_throws_attempted: int | None
    free_throws_percentage: float | None = None
    source: str | None = None
    retrieved_at: str | None = None
    updated_at: str | None = None
    participation_status: str


class Overview(BaseModel):
    tournament: Tournament
    teams: list[Team]
    players: list[Player]
    games: list[Game]


class PlayerDetail(Player):
    games_log: list[PlayerGame]


class TeamDetail(Team):
    roster: list[Player]
    games_log: list[Game]


class GameDetail(Game):
    box_score: list[BoxScore]
