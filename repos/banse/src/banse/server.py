"""FastAPI application for read-only access to ingested basketball data."""
import argparse
from pathlib import Path
from typing import Annotated
from uuid import UUID

import duckdb
import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware

from . import data


DEFAULT_DATABASE = Path(__file__).resolve().parents[3] / 'ingestion/data/league.duckdb'


def create_app(database: Path = DEFAULT_DATABASE, cors_origin: str | None = None) -> FastAPI:
    """Create an app for one DuckDB file; open a read-only connection per request."""
    database = Path(database).resolve()
    app = FastAPI(title='Banse API', description='Basketball statistics from ingested DuckDB data')

    if cors_origin:
        app.add_middleware(CORSMiddleware, allow_origins=[cors_origin], allow_methods=['GET'],
                           allow_headers=['*'])

    @app.middleware('http')
    async def disable_cache(request, call_next):
        response: Response = await call_next(request)
        response.headers['Cache-Control'] = 'no-store'
        return response

    def get_connection():
        with data.open_database(database) as connection:
            yield connection

    Connection = Annotated[duckdb.DuckDBPyConnection, Depends(get_connection)]

    def require_tournament(connection, tournament_id: UUID):
        result = data.tournament(connection, tournament_id)
        if result is None:
            raise HTTPException(status_code=404, detail='Tournament not found')
        return result

    def require_record(result):
        if result is None:
            raise HTTPException(status_code=404, detail='Record not found')
        return result

    @app.get('/api/health', tags=['system'])
    def health():
        return {'status': 'ok'}

    @app.get('/api/tournaments', tags=['tournaments'])
    def tournaments(connection: Connection):
        return data.tournaments(connection)

    @app.get('/api/overview', tags=['tournaments'])
    def overview(tournament_id: UUID, connection: Connection):
        selected = require_tournament(connection, tournament_id)
        return {'tournament': selected, 'teams': data.teams(connection, tournament_id),
                'players': data.players(connection, tournament_id),
                'games': data.games(connection, tournament_id)}

    @app.get('/api/players', tags=['players'])
    def players(tournament_id: UUID, connection: Connection):
        require_tournament(connection, tournament_id)
        return data.players(connection, tournament_id)

    @app.get('/api/players/{player_id}', tags=['players'])
    def player(player_id: UUID, tournament_id: UUID, connection: Connection):
        require_tournament(connection, tournament_id)
        result = require_record(data.player(connection, tournament_id, player_id))
        result['games_log'] = data.player_games(connection, tournament_id, player_id)
        return result

    @app.get('/api/teams', tags=['teams'])
    def teams(tournament_id: UUID, connection: Connection):
        require_tournament(connection, tournament_id)
        return data.teams(connection, tournament_id)

    @app.get('/api/teams/{team_id}', tags=['teams'])
    def team(team_id: UUID, tournament_id: UUID, connection: Connection):
        require_tournament(connection, tournament_id)
        result = require_record(data.team(connection, tournament_id, team_id))
        result['roster'] = [p for p in data.players(connection, tournament_id)
                            if p['team_id'] == str(team_id)]
        result['games_log'] = [g for g in data.games(connection, tournament_id)
                               if str(team_id) in (g['team_id_1'], g['team_id_2'])]
        return result

    @app.get('/api/games', tags=['games'])
    def games(tournament_id: UUID, connection: Connection):
        require_tournament(connection, tournament_id)
        return data.games(connection, tournament_id)

    @app.get('/api/games/{game_id}', tags=['games'])
    def game(game_id: UUID, tournament_id: UUID, connection: Connection):
        require_tournament(connection, tournament_id)
        result = require_record(data.game(connection, tournament_id, game_id))
        result['box_score'] = data.game_box_score(connection, tournament_id, game_id)
        return result

    return app


app = create_app()


def main():
    parser = argparse.ArgumentParser(description='Serve ingested basketball statistics')
    parser.add_argument('--database', type=Path, default=DEFAULT_DATABASE)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--cors-origin', help='Allowed browser origin for a separately hosted UI')
    args = parser.parse_args()
    if not args.database.is_file():
        parser.error(f'Database does not exist: {args.database}')
    uvicorn.run(create_app(args.database, args.cors_origin), host=args.host, port=args.port)


if __name__ == '__main__':
    main()
