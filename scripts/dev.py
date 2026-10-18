"""Run Banse and Vite together for local development."""
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[1]
API = ROOT / 'repos/banse/.venv/bin/banse'
DATABASE = ROOT / 'repos/ingestion/data/league.duckdb'
UI = ROOT / 'repos/ui'
NODE = UI / 'node_modules/node/bin/node'
VITE = UI / 'node_modules/.bin/vite'


def prerequisites():
    missing = []
    if not API.is_file():
        missing.append('Banse virtual environment')
    if not DATABASE.is_file():
        missing.append('DuckDB database (see repos/ingestion/README.md)')
    if not NODE.is_file() or not VITE.is_file():
        missing.append('UI dependencies')
    if not shutil.which('npm'):
        missing.append('npm')
    if missing:
        raise RuntimeError('Missing ' + ', '.join(missing) + '. Run `make setup` for dependencies.')
    version = subprocess.check_output([str(NODE), '--version'], text=True).strip()
    major, minor = (int(part) for part in version.removeprefix('v').split('.')[:2])
    if (major, minor) < (22, 12):
        raise RuntimeError(f'UI needs Node 22.12 or newer; project-local Node is {version}. Run `make setup`.')


def stop(processes):
    for process in processes:
        if process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
    for process in processes:
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()


def main():
    prerequisites()
    environment = os.environ.copy()
    environment['PATH'] = str(UI / 'node_modules/.bin') + os.pathsep + environment.get('PATH', '')
    processes = []
    stopping = False

    def request_stop(_signum, _frame):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)
    try:
        print('Starting Banse on http://127.0.0.1:8000 and UI on http://127.0.0.1:5173', flush=True)
        processes.append(subprocess.Popen(
            [str(API), '--database', str(DATABASE)], cwd=ROOT, start_new_session=True))
        processes.append(subprocess.Popen(
            ['npm', 'run', 'dev', '--', '--host', '127.0.0.1', '--port', '5173', '--strictPort'],
            cwd=UI, env=environment, start_new_session=True))
        while not stopping:
            for name, process in zip(('Banse', 'UI'), processes):
                code = process.poll()
                if code is not None:
                    print(f'{name} exited with code {code}; stopping the other service.', file=sys.stderr)
                    return code or 1
            time.sleep(0.2)
        return 0
    finally:
        stop(processes)


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, RuntimeError) as error:
        print(error, file=sys.stderr)
        sys.exit(1)
