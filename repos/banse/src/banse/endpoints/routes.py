"""Read-only basketball statistics endpoints."""
from uuid import UUID

from fastapi import APIRouter

from ..models import responses
from ..service import data
from .dependencies import Connection, Scope, SelectedTournament, require_record


router = APIRouter(prefix='/api')


@router.get('/health', tags=['system'], response_model=responses.HealthResponse)
def health():
    return {'status': 'ok'}


@router.get('/tournaments', tags=['tournaments'], response_model=list[responses.TournamentSummary])
def tournaments(connection: Connection):
    return data.tournaments(connection)


@router.get('/overview', tags=['tournaments'], response_model=responses.Overview)
def overview(scope: Scope, selected: SelectedTournament, connection: Connection):
    return {'tournament': selected, 'teams': data.teams(connection, scope.tournament_id),
            'players': data.players(connection, scope.tournament_id),
            'games': data.games(connection, scope.tournament_id)}


@router.get('/players', tags=['players'], response_model=list[responses.Player])
def players(scope: Scope, _tournament: SelectedTournament, connection: Connection):
    return data.players(connection, scope.tournament_id)


@router.get('/players/{player_id}', tags=['players'], response_model=responses.PlayerDetail)
def player(player_id: UUID, scope: Scope, _tournament: SelectedTournament, connection: Connection):
    result = require_record(data.player(connection, scope.tournament_id, player_id))
    result['games_log'] = data.player_games(connection, scope.tournament_id, player_id)
    return result


@router.get('/teams', tags=['teams'], response_model=list[responses.Team])
def teams(scope: Scope, _tournament: SelectedTournament, connection: Connection):
    return data.teams(connection, scope.tournament_id)


@router.get('/teams/{team_id}', tags=['teams'], response_model=responses.TeamDetail)
def team(team_id: UUID, scope: Scope, _tournament: SelectedTournament, connection: Connection):
    result = require_record(data.team(connection, scope.tournament_id, team_id))
    result['roster'] = [p for p in data.players(connection, scope.tournament_id)
                        if p['team_id'] == str(team_id)]
    result['games_log'] = [g for g in data.games(connection, scope.tournament_id)
                           if str(team_id) in (g['team_id_1'], g['team_id_2'])]
    return result


@router.get('/games', tags=['games'], response_model=list[responses.Game])
def games(scope: Scope, _tournament: SelectedTournament, connection: Connection):
    return data.games(connection, scope.tournament_id)


@router.get('/games/{game_id}', tags=['games'], response_model=responses.GameDetail)
def game(game_id: UUID, scope: Scope, _tournament: SelectedTournament, connection: Connection):
    result = require_record(data.game(connection, scope.tournament_id, game_id))
    result['box_score'] = data.game_box_score(connection, scope.tournament_id, game_id)
    return result
