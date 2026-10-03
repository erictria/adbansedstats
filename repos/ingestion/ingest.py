#!/usr/bin/env python3
"""Run ingestion directly: python repos/ingestion/ingest.py --help."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / 'src'))

from ingestion.cli import main

if __name__ == '__main__':
    raise SystemExit(main())
