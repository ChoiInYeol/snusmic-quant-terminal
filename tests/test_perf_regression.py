"""Phase 3d — perf regression gate.

Plan AC #2 (Phase 3): 500 symbols × 5 years must complete a single
``run_walk_forward_backtest`` invocation in under 90 seconds on a CI runner.
The full-scale gate is opt-in (``RUN_PERF=1``) so it does not slow down the
default test suite. A lighter ~50-symbol × 1-year smoke check runs every CI
build to guard the perf harness itself from drift.
"""

from __future__ import annotations

import os
import time

import numpy as np
import pandas as pd
import pytest

from snusmic_pipeline.backtest.engine import run_walk_forward_backtest
from snusmic_pipeline.backtest.schemas import BacktestConfig

PERF_BUDGET_FULL_SECONDS = 90.0
PERF_BUDGET_SMOKE_SECONDS = 8.0


def _build_universe(symbol_count: int, periods: int, seed: int = 42) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2020-01-02", periods=periods)
    rows: list[dict] = []
    symbols = [f"SYM{i:03d}.KS" for i in range(symbol_count)]
    for i, symbol in enumerate(symbols):
        drift = 0.00025 + (i % 11) * 0.00003
        noise = rng.standard_normal(periods) * 0.012
        base = 40.0 + (i % 25) * 4.0
        close = base * np.cumprod(1.0 + drift + noise)
        for date, price in zip(dates, close, strict=True):
            rows.append(
                {
                    "date": date.date().isoformat(),
                    "symbol": symbol,
                    "open": float(price) * 0.998,
                    "high": float(price) * 1.01,
                    "low": float(price) * 0.99,
                    "close": float(price),
                    "volume": 1000,
                }
            )
    prices = pd.DataFrame(rows)
    reports = pd.DataFrame(
        [
            {
                "report_id": f"r{i:03d}",
                "publication_date": (dates[periods // 4]).date().isoformat(),
                "title": f"Report for {symbol}",
                "company": f"Company {i}",
                "ticker": symbol.split(".")[0],
                "exchange": "KRX",
                "symbol": symbol,
                "target_price": 100.0 * (1.4 + (i % 10) * 0.02),
                "report_current_price": 100.0,
            }
            for i, symbol in enumerate(symbols)
        ]
    )
    return reports, prices


def test_perf_smoke_50_symbols_1_year() -> None:
    """Always-on guardrail. Verifies the engine handles a modest universe in
    under :data:`PERF_BUDGET_SMOKE_SECONDS`. Detects perf regressions early
    even when the full ``RUN_PERF=1`` gate is skipped."""
    reports, prices = _build_universe(symbol_count=50, periods=252)
    config = BacktestConfig(
        name="perf-smoke",
        entry_rule="target_only",
        weighting="1/N",
        rebalance="weekly",
        lookback_days=126,
        min_target_upside=0.0,
    )
    t0 = time.perf_counter()
    result = run_walk_forward_backtest(reports, prices, config)
    elapsed = time.perf_counter() - t0
    assert not result["equity_daily"].empty
    assert elapsed < PERF_BUDGET_SMOKE_SECONDS, (
        f"50×1y backtest took {elapsed:.2f}s, exceeding the "
        f"{PERF_BUDGET_SMOKE_SECONDS}s smoke budget — perf regression."
    )


@pytest.mark.skipif(os.environ.get("RUN_PERF") != "1", reason="set RUN_PERF=1 to enable")
def test_perf_full_500_symbols_5_years() -> None:
    """Plan AC #2 — 500 symbols × 5 years must finish under 90 seconds. Opt-in
    because it allocates a sizeable in-memory frame and runs the full engine
    end-to-end; running on every PR would balloon CI time. Trigger with
    ``RUN_PERF=1 uv run pytest tests/test_perf_regression.py``."""
    reports, prices = _build_universe(symbol_count=500, periods=5 * 252)
    config = BacktestConfig(
        name="perf-full",
        entry_rule="target_only",
        weighting="1/N",
        rebalance="weekly",
        lookback_days=252,
        min_target_upside=0.0,
    )
    t0 = time.perf_counter()
    result = run_walk_forward_backtest(reports, prices, config)
    elapsed = time.perf_counter() - t0
    assert not result["equity_daily"].empty
    assert elapsed < PERF_BUDGET_FULL_SECONDS, (
        f"500×5y backtest took {elapsed:.2f}s, exceeding the {PERF_BUDGET_FULL_SECONDS}s budget."
    )
