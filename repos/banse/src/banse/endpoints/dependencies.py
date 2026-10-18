"""Shared FastAPI dependencies for database-backed routes."""
from typing import Annotated
from uuid import UUID

import duckdb
from fastapi import Depends, HTTPException, Request

from ..models.requests import TournamentScope
from ..models.responses import Tournament
from ..service import data


def get_connection(request: Request):
    with data.open_database(request.app.state.database) as connection:
        yield connection


Connection = Annotated[duckdb.DuckDBPyConnection, Depends(get_connection)]


def get_tournament_scope(tournament_id: UUID) -> TournamentScope:
    return TournamentScope(tournament_id=tournament_id)


Scope = Annotated[TournamentScope, Depends(get_tournament_scope)]


def require_tournament(scope: Scope, connection: Connection) -> Tournament:
    tournament = data.tournament(connection, scope.tournament_id)
    if tournament is None:
        raise HTTPException(status_code=404, detail='Tournament not found')
    return Tournament.model_validate(tournament)


SelectedTournament = Annotated[Tournament, Depends(require_tournament)]


def require_record(record):
    if record is None:
        raise HTTPException(status_code=404, detail='Record not found')
    return record
