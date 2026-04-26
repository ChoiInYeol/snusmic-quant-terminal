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
    pd.DataFrame([e.model_dump() for e in result.position_episodes]).to_csv(
        out / "position_episodes.csv", index=False
    )
    pd.DataFrame([h.model_dump() for h in result.current_holdings]).to_csv(
        out / "current_holdings.csv", index=False
    )
    pd.DataFrame([s.model_dump() for s in result.symbol_stats]).to_csv(out / "symbol_stats.csv", index=False)
    pd.DataFrame([p.model_dump() for p in result.report_performance]).to_csv(
        out / "report_performance.csv", index=False
    )
    if result.report_stats is not None:
        (out / "report_stats.json").write_text(
            result.report_stats.model_dump_json(indent=2), encoding="utf-8"
        )

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

    print("\n=== Current holdings (top 5 by market value per persona) ===")
    by_persona: dict[str, list] = {}
    for holding in result.current_holdings:
        by_persona.setdefault(holding.persona, []).append(holding)
    for persona, holdings in by_persona.items():
        label = next((s.label for s in result.summaries if s.persona == persona), persona)
        print(f"  [{label}]  total {len(holdings)} 종목")
        for h in holdings[:5]:
            name = (h.company or h.symbol)[:24]
            ret = f"{h.unrealized_return * 100:+.1f}%" if h.unrealized_return is not None else "n/a"
            print(
                f"    {h.symbol:<14s} {name:<24s}  qty={h.qty:>6d}  "
                f"avg_cost={h.avg_cost_krw:>10,.0f}  last={h.last_close_krw or 0:>10,.0f}  "
                f"value={h.market_value_krw / 1e6:>7,.2f}M  unreal={ret:>7s}  "
                f"holding_days={h.holding_days}"
            )

    rs = result.report_stats
    if rs is not None:
        print("\n=== SMIC report universe statistics (persona-agnostic) ===")
        print(
            f"  total reports={rs.total_reports}  with prices={rs.reports_with_prices}  "
            f"target_hit={rs.target_hit_count} ({rs.target_hit_rate * 100:.1f}%)"
        )
        if rs.avg_days_to_target is not None:
            print(f"  days to target: avg={rs.avg_days_to_target:.0f}  median={rs.median_days_to_target:.0f}")
        if rs.avg_current_return is not None:
            print(
                f"  realised return so far: avg={rs.avg_current_return * 100:+.1f}%  "
                f"median={rs.median_current_return * 100:+.1f}%"
            )
        if rs.avg_target_upside_at_pub is not None:
            print(f"  avg target upside promised at publication: {rs.avg_target_upside_at_pub * 100:+.1f}%")

        def _fmt_perf(p, key: str) -> str:
            value = getattr(p, key)
            if value is None:
                return f"{p.symbol:<14s} {p.company[:18]:<18s}  n/a"
            return (
                f"{p.symbol:<14s} {p.company[:18]:<18s}  pub={p.publication_date}  {key}={value * 100:+.1f}%"
            )

        print("\n  -- Top 5 winners (current return since publication):")
        for p in rs.top_winners[:5]:
            print(f"    {_fmt_perf(p, 'current_return')}")
        print("\n  -- Top 5 losers (current return since publication):")
        for p in rs.top_losers[:5]:
            print(f"    {_fmt_perf(p, 'current_return')}")
        print("\n  -- Top 5 furthest below target (still open):")
        for p in rs.biggest_target_gaps_below[:5]:
            print(f"    {_fmt_perf(p, 'target_gap_pct')}")
        print("\n  -- Top 5 fastest target hits (days to target):")
        for p in rs.fastest_target_hits[:5]:
            d = p.days_to_target if p.days_to_target is not None else "?"
            print(f"    {p.symbol:<14s} {p.company[:18]:<18s}  pub={p.publication_date}  days={d}")

    print(f"\nArtifacts written to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
