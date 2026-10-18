"""FastAPI application for read-only access to ingested basketball data."""
import argparse
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware

from .endpoints.routes import router


DEFAULT_DATABASE = Path(__file__).resolve().parents[3] / 'ingestion/data/league.duckdb'


def create_app(database: Path = DEFAULT_DATABASE, cors_origin: str | None = None) -> FastAPI:
    """Create an app for one DuckDB file; open a read-only connection per request."""
    app = FastAPI(title='Banse API', description='Basketball statistics from ingested DuckDB data')
    app.state.database = Path(database).resolve()

    if cors_origin:
        app.add_middleware(CORSMiddleware, allow_origins=[cors_origin], allow_methods=['GET'],
                           allow_headers=['*'])

    @app.middleware('http')
    async def disable_cache(request, call_next):
        response: Response = await call_next(request)
        response.headers['Cache-Control'] = 'no-store'
        return response

    app.include_router(router)
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
