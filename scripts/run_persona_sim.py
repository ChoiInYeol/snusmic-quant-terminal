"""CLI entrypoint for the persona simulation.

Run from the repo root::

    uv run python scripts/run_persona_sim.py \
        --start 2021-01-04 --end 2026-04-15 \
        --warehouse data/warehouse \
        --out data/sim

Produces ``personas.json``, ``equity_daily.csv``, ``trades.csv``,
``summary.csv``, ``equity_curves.png``, ``net_profit_bar.png``, and
``drawdowns.png``.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

# Make `src/` importable when launched as a plain script.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd  # noqa: E402

from snusmic_pipeline.sim.contracts import SimulationConfig  # noqa: E402
from snusmic_pipeline.sim.runner import run_simulation  # noqa: E402
from snusmic_pipeline.sim.visualize import (  # noqa: E402
    plot_drawdowns,
    plot_equity_curves,
    plot_net_profit_bars,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", type=str, default="2021-01-04")
    parser.add_argument("--end", type=str, default="2026-04-15")
    parser.add_argument("--warehouse", type=Path, default=ROOT / "data" / "warehouse")
    parser.add_argument("--out", type=Path, default=ROOT / "data" / "sim")
    parser.add_argument(
        "--refresh-benchmark",
        action="store_true",
        help="Force re-download of the All-Weather benchmark prices.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    out: Path = args.out
    out.mkdir(parents=True, exist_ok=True)
    config = SimulationConfig(
        start_date=date.fromisoformat(args.start),
        end_date=date.fromisoformat(args.end),
    )
    print(f"Running simulation {config.start_date} → {config.end_date}")
    print(f"  warehouse: {args.warehouse}")
    print(f"  personas : {[p.persona_name for p in config.personas]}")

    result = run_simulation(config, args.warehouse, refresh_benchmark=args.refresh_benchmark)

    (out / "personas.json").write_text(result.model_dump_json(indent=2), encoding="utf-8")
    pd.DataFrame([s.model_dump() for s in result.summaries]).to_csv(out / "summary.csv", index=False)
    pd.DataFrame([p.model_dump() for p in result.equity_points]).to_csv(out / "equity_daily.csv", index=False)
    pd.DataFrame([t.model_dump() for t in result.trades]).to_csv(out / "trades.csv", index=False)

    plot_equity_curves(result, out / "equity_curves.png")
    plot_net_profit_bars(result, out / "net_profit_bar.png")
    plot_drawdowns(result, out / "drawdowns.png")

    print("\n=== Final results ===")
    rows = sorted(result.summaries, key=lambda s: -s.net_profit_krw)
    for summary in rows:
        print(
            f"  {summary.label:<32s} "
            f"final={summary.final_equity_krw / 1e6:>9,.2f}M  "
            f"net_profit={summary.net_profit_krw / 1e6:>+9,.2f}M  "
            f"IRR={summary.money_weighted_return * 100:>6.2f}%  "
            f"MDD={summary.max_drawdown * 100:>5.2f}%  "
            f"trades={summary.trade_count}"
        )
    print(f"\nArtifacts written to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
