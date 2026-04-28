"""Export local strategy-search trials as web-consumable artifacts."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from snusmic_pipeline.strategy_search.export import export_strategy_artifacts  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study-db", type=Path, default=ROOT / "data" / "optuna" / "studies" / "smic_follower_v1.db", help="Accepted for plan-compatible CLI; trials CSV is the artifact source in the fallback path.")
    parser.add_argument("--trials-csv", type=Path, default=ROOT / "data" / "optuna" / "exports" / "trials.csv")
    parser.add_argument("--study", default="smic-follower-v1")
    parser.add_argument("--out", type=Path, default=ROOT / "data" / "web")
    parser.add_argument("--top", type=int, default=20)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    paths = export_strategy_artifacts(args.trials_csv, args.out, study_name=args.study, top_n=args.top)
    for name, path in paths.items():
        print(f"{name}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
