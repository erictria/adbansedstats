"""Private, loopback-only HTTP launcher for the ingestion CLI."""
import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
from threading import Lock, Thread
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, FastAPI, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
import uvicorn


NAME = r'^[A-Za-z0-9][A-Za-z0-9_-]*$'
SLUG = r'^[a-z0-9][a-z0-9-]*$'
bearer = HTTPBearer()


class WorkRequest(BaseModel):
    work_dir: str = Field(pattern=NAME)


class TournamentRequest(BaseModel):
    tournament: str = Field(pattern=SLUG)


class PrepareRequest(WorkRequest, TournamentRequest):
    refresh: bool = False
    limit: int | None = Field(default=None, ge=1)
    use_saved_directories: bool = False


class GameRequest(TournamentRequest):
    game_id: int = Field(gt=0)


class FileRequest(WorkRequest):
    filename: str = Field(pattern=r'^[A-Za-z0-9][A-Za-z0-9_.-]*\.json$')


class FixtureRequest(FileRequest):
    source: str = Field(default='demo', pattern=NAME)


class JobResponse(BaseModel):
    job_id: UUID
    command: str
    status: str
    started_at: datetime
    finished_at: datetime | None = None
    result: object | None = None
    error: str | None = None


@dataclass(frozen=True)
class Settings:
    token: str
    work_root: Path
    database: Path
    backend: str = 'duckdb'

    def __post_init__(self):
        if not self.token:
            raise ValueError('INGESTION_API_TOKEN is required')
        if self.backend not in ('duckdb', 'sqlite'):
            raise ValueError('backend must be duckdb or sqlite')


class Jobs:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.lock = Lock()
        self.active: UUID | None = None
        self.records: dict[UUID, JobResponse] = {}

    def start(self, command: str, arguments: list[str]) -> JobResponse:
        with self.lock:
            if self.active is not None:
                raise HTTPException(status_code=409, detail=f'Job {self.active} is still running')
            job_id = uuid4()
            job = JobResponse(job_id=job_id, command=command, status='running',
                              started_at=datetime.now(timezone.utc))
            self.records[job_id] = job
            self.active = job_id
        Thread(target=self._run, args=(job_id, arguments), daemon=False).start()
        return job.model_copy()

    def get(self, job_id: UUID) -> JobResponse:
        with self.lock:
            job = self.records.get(job_id)
            if job is None:
                raise HTTPException(status_code=404, detail='Job not found')
            return job.model_copy()

    def _run(self, job_id: UUID, arguments: list[str]) -> None:
        try:
            process = subprocess.run(
                [sys.executable, '-m', 'ingestion.cli', *arguments],
                capture_output=True, text=True, timeout=7200, check=False,
            )
            if process.returncode:
                state, result, error = 'failed', None, (process.stderr or process.stdout)[-4000:]
            else:
                state, result, error = 'succeeded', json.loads(process.stdout), None
        except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
            state, result, error = 'failed', None, str(exc)[-4000:]
        with self.lock:
            job = self.records[job_id]
            job.status = state
            job.result = result
            job.error = error
            job.finished_at = datetime.now(timezone.utc)
            self.active = None


def create_app(settings: Settings) -> FastAPI:
    settings = Settings(settings.token, settings.work_root.resolve(),
                        settings.database.resolve(), settings.backend)
    settings.work_root.mkdir(parents=True, exist_ok=True)
    jobs = Jobs(settings)
    app = FastAPI(title='Private ingestion API')

    def authenticate(credentials: HTTPAuthorizationCredentials = Depends(bearer)):
        if not secrets.compare_digest(credentials.credentials, settings.token):
            raise HTTPException(status_code=401, detail='Invalid token',
                                headers={'WWW-Authenticate': 'Bearer'})

    router = APIRouter(prefix='/ingestion', dependencies=[Depends(authenticate)])

    def work_path(name: str) -> Path:
        path = (settings.work_root / name).resolve()
        if not path.is_relative_to(settings.work_root):
            raise HTTPException(status_code=400, detail='Work directory leaves configured root')
        return path

    def file_path(request: FileRequest) -> Path:
        directory = work_path(request.work_dir)
        path = (directory / request.filename).resolve()
        if not path.is_relative_to(directory):
            raise HTTPException(status_code=400, detail='Input file leaves work directory')
        if not path.is_file():
            raise HTTPException(status_code=404, detail='Input file not found')
        return path

    def store_args() -> list[str]:
        return ['--backend', settings.backend, '--database', str(settings.database)]

    @router.get('/health')
    def health():
        return {'status': 'ok'}

    @router.get('/jobs/{job_id}', response_model=JobResponse)
    def get_job(job_id: UUID):
        return jobs.get(job_id)

    @router.post('/list-games', response_model=JobResponse, status_code=status.HTTP_202_ACCEPTED)
    def list_games(request: TournamentRequest):
        return jobs.start('list-games', ['--list-games', '--tournament', request.tournament])

    @router.post('/prepare-pba', response_model=JobResponse, status_code=status.HTTP_202_ACCEPTED)
    def prepare_pba(request: PrepareRequest):
        args = ['--prepare-pba', '--tournament', request.tournament,
                '--work-dir', str(work_path(request.work_dir))]
        if request.refresh:
            args.append('--refresh')
        if request.limit is not None:
            args += ['--limit', str(request.limit)]
        if request.use_saved_directories:
            directory = work_path(request.work_dir)
            for option, filename in (('--players-html', 'players.html'), ('--teams-html', 'teams.html')):
                path = directory / filename
                if not path.is_file():
                    raise HTTPException(status_code=404, detail=f'{filename} not found')
                args += [option, str(path)]
        return jobs.start('prepare-pba', args)

    @router.post('/match-pba', response_model=JobResponse, status_code=status.HTTP_202_ACCEPTED)
    def match_pba(request: WorkRequest):
        return jobs.start('match-pba', ['--match-pba', '--work-dir', str(work_path(request.work_dir))])

    @router.post('/import-pba', response_model=JobResponse, status_code=status.HTTP_202_ACCEPTED)
    def import_pba(request: WorkRequest):
        return jobs.start('import-pba', ['--import-pba', '--work-dir', str(work_path(request.work_dir)), *store_args()])

    @router.post('/init-db', response_model=JobResponse, status_code=status.HTTP_202_ACCEPTED)
    def init_db():
        return jobs.start('init-db', ['--init-db', *store_args()])

    @router.post('/pba-game', response_model=JobResponse, status_code=status.HTTP_202_ACCEPTED)
    def pba_game(request: GameRequest):
        return jobs.start('pba-game', ['--pba', '--tournament', request.tournament,
                                      '--game-id', str(request.game_id), *store_args()])

    @router.post('/normalized', response_model=JobResponse, status_code=status.HTTP_202_ACCEPTED)
    def normalized(request: FileRequest):
        return jobs.start('normalized', ['--normalized', str(file_path(request)), *store_args()])

    @router.post('/fixture', response_model=JobResponse, status_code=status.HTTP_202_ACCEPTED)
    def fixture(request: FixtureRequest):
        return jobs.start('fixture', ['--input', str(file_path(request)),
                                      '--source', request.source, *store_args()])

    app.include_router(router)
    return app


def main() -> None:
    parser = argparse.ArgumentParser(description='Run the private ingestion API on loopback')
    parser.add_argument('--port', type=int, default=8001)
    parser.add_argument('--work-root', type=Path, default=Path('data'))
    parser.add_argument('--database', type=Path, default=Path('data/league.duckdb'))
    parser.add_argument('--backend', choices=['duckdb', 'sqlite'], default='duckdb')
    args = parser.parse_args()
    settings = Settings(os.environ.get('INGESTION_API_TOKEN', ''), args.work_root,
                        args.database, args.backend)
    uvicorn.run(create_app(settings), host='127.0.0.1', port=args.port, workers=1)


if __name__ == '__main__':
    main()
