"""HTTP box-score export. Uses the same parser as the ingestion adapter."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

# Allow direct execution from this repository without installing the package.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'ingestion' / 'src'))
from ingestion.sources.pba import fetch_html, parse_box_score


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tournament', default='pba-50th-season-governors-cup')
    parser.add_argument('--game-id', type=int, default=522)
    parser.add_argument('--output', type=Path, default=Path('pba_box_score.json'))
    args = parser.parse_args()
    records = parse_box_score(fetch_html(args.tournament, args.game_id), args.tournament, args.game_id)
    args.output.write_text(json.dumps([asdict(r) for r in records], indent=2, ensure_ascii=False), encoding='utf-8')
    print(f'Exported {len(records)} player/team records to {args.output}')


if __name__ == '__main__':
    main()
