"""Phase 1a AC #1 — determinism.

Running the same synthetic backtest twice with the same seed must produce
byte-identical ``execution_events`` and ``strategy_runs`` DataFrames. This
locks in Principle 4's regression surface for any Phase-3 vectorization work.
"""

from __future__ import annotations

import hashlib
import random

import numpy as np
import pandas as pd

from snusmic_pipeline.backtest.engine import run_walk_forward_backtest
from snusmic_pipeline.backtest.schemas import BacktestConfig


def _seed(n: int = 42) -> None:
    random.seed(n)
    np.random.seed(n)


def _make_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    _seed(42)
    dates = pd.bdate_range("2023-01-02", periods=300)
    close = pd.Series(range(len(dates)), dtype=float) * 0.12 + 80.0
    prices = pd.DataFrame(
        [
            {
                "date": d.date().isoformat(),
                "symbol": "AAA.KS",
                "open": p,
                "high": p,
                "low": p,
                "close": p,
                "volume": 1000,
            }
            for d, p in zip(dates, close, strict=True)
        ]
    )
    reports = pd.DataFrame(
        [
            {
                "report_id": "r1",
                "publication_date": "2024-01-10",
                "title": "Alpha",
                "company": "Alpha",
                "ticker": "AAA",
                "exchange": "KRX",
                "symbol": "AAA.KS",
                "target_price": 180.0,
                "report_current_price": 100.0,
            }
        ]
    )
    return reports, prices


def _hash(frame: pd.DataFrame) -> str:
    return hashlib.sha256(frame.to_csv(index=False).encode("utf-8")).hexdigest()


def test_two_runs_produce_identical_outputs() -> None:
    reports_a, prices_a = _make_inputs()
    reports_b, prices_b = _make_inputs()
    config = BacktestConfig(
        name="determinism",
        entry_rule="target_only",
        weighting="1/N",
        rebalance="daily",
        min_target_upside=0.0,
    )

    _seed(42)
    run_a = run_walk_forward_backtest(reports_a, prices_a, config)
    _seed(42)
    run_b = run_walk_forward_backtest(reports_b, prices_b, config)

    for key in ("execution_events", "strategy_runs", "equity_daily"):
        assert _hash(run_a[key]) == _hash(run_b[key]), (
            f"{key} diverged between two seeded runs — engine has non-deterministic state."
        )
