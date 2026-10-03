import argparse
import json
import logging
from dataclasses import asdict
from pathlib import Path

from .cleaning import DefaultCleaner
from .engine import IngestionEngine
from .sources.json_file import JsonFileSource
from .storage import SQLiteStore
from .duckdb_storage import DuckDBStore
from .sources.pba import PbaSource, discover_games
from .pba_cleaning import PbaCleaner


def main() -> int:
    parser = argparse.ArgumentParser(description="Retrieve, clean and ingest league records")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--input", type=Path, help="Local JSON fixture")
    mode.add_argument("--pba", action="store_true", help="Retrieve a PBA game over HTTP")
    mode.add_argument("--list-games", action="store_true", help="List published PBA games as JSON without ingestion")
    mode.add_argument("--init-db", action="store_true", help="Initialize DuckDB tables")
    mode.add_argument("--normalized", type=Path, help="JSON object of players, teams, games, game_statistics")
    parser.add_argument("--backend", choices=["duckdb", "sqlite"], default="duckdb")
    parser.add_argument("--tournament", help="PBA tournament slug")
    parser.add_argument("--game-id", type=int, help="PBA game ID")
    parser.add_argument("--source", default="demo", help="Stable dataset name, e.g. demo")
    parser.add_argument("--database", type=Path, default=None)
    args = parser.parse_args()
    if args.pba and (not args.tournament or not args.game_id):
        parser.error("--pba requires --tournament and --game-id")
    if args.list_games and not args.tournament:
        parser.error("--list-games requires --tournament")
    if (args.init_db or args.normalized) and args.backend != "duckdb":
        parser.error("--init-db and --normalized require DuckDB")
    database = args.database or Path("data/league.duckdb" if args.backend == "duckdb" else "data/league.sqlite3")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    try:
        if args.list_games:
            print(json.dumps([asdict(game) for game in discover_games(args.tournament)]))
            return 0
        store = DuckDBStore(database) if args.backend == "duckdb" else SQLiteStore(database)
        if args.init_db:
            store.initialize()
            print(json.dumps({"database": str(database), "initialized": True}))
            return 0
        if args.normalized:
            payload = json.loads(args.normalized.read_text(encoding="utf-8"))
            print(json.dumps(store.write_models(**payload)))
            return 0
        source = PbaSource(args.tournament, args.game_id) if args.pba else JsonFileSource(args.input, args.source)
        cleaner = PbaCleaner() if args.pba else DefaultCleaner()
        result = IngestionEngine(cleaner, store).run(source)
    except Exception:
        logging.exception("Ingestion command failed")
        return 1  # The engine logs the failure with its run ID and traceback.
    print(json.dumps(asdict(result)))
    return 0
