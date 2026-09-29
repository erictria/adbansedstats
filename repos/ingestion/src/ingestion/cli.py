import argparse
import json
import logging
from dataclasses import asdict
from pathlib import Path

from .cleaning import DefaultCleaner
from .engine import IngestionEngine
from .sources.json_file import JsonFileSource
from .storage import SQLiteStore
from .sources.pba import PbaSource
from .pba_cleaning import PbaCleaner


def main() -> int:
    parser = argparse.ArgumentParser(description="Retrieve, clean and ingest league records")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--input", type=Path, help="Local JSON fixture")
    mode.add_argument("--pba", action="store_true", help="Retrieve a PBA game over HTTP")
    parser.add_argument("--tournament", help="PBA tournament slug")
    parser.add_argument("--game-id", type=int, help="PBA game ID")
    parser.add_argument("--source", default="demo", help="Stable dataset name, e.g. demo")
    parser.add_argument("--database", type=Path, default=Path("data/league.sqlite3"))
    args = parser.parse_args()
    if args.pba and (not args.tournament or not args.game_id):
        parser.error("--pba requires --tournament and --game-id")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    try:
        source = PbaSource(args.tournament, args.game_id) if args.pba else JsonFileSource(args.input, args.source)
        cleaner = PbaCleaner() if args.pba else DefaultCleaner()
        result = IngestionEngine(cleaner, SQLiteStore(args.database)).run(source)
    except Exception:
        return 1  # The engine logs the failure with its run ID and traceback.
    print(json.dumps(asdict(result)))
    return 0
