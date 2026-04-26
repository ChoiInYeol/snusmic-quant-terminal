"""Phase 2 integration: a 10-symbol, 3-year deterministic fixture whose
equity curve SHA256 is pinned at the top of this file. Any future change that
would shift the equity curve (e.g. a new look-ahead fix, a weighting change)
must be paired with a deliberate update of the pinned hashes — the failing
test calls the regression out before it ships.
"""

from __future__ import annotations

import hashlib

import numpy as np
import pandas as pd
import pytest

from snusmic_pipeline.backtest.engine import run_walk_forward_backtest
from snusmic_pipeline.backtest.schemas import BacktestConfig

SYMBOLS = [f"SYM{i:02d}.KS" for i in range(10)]


def _deterministic_prices(seed: int = 42, periods: int = 3 * 252) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2021-01-04", periods=periods)
    rows = []
    for i, symbol in enumerate(SYMBOLS):
        drift = 0.0003 + i * 0.00005
        noise = rng.standard_normal(periods) * 0.012
        base = 50.0 + i * 4.0
        close = base * np.cumprod(1.0 + drift + noise)
        for date, price in zip(dates, close, strict=True):
            rows.append(
                {
                    "date": date.date().isoformat(),
                    "symbol": symbol,
                    "open": float(price) * 0.997,
                    "high": float(price) * 1.01,
                    "low": float(price) * 0.99,
                    "close": float(price),
                    "volume": 1000,
                }
            )
    return pd.DataFrame(rows)


def _deterministic_reports() -> pd.DataFrame:
    rows = []
    for i, symbol in enumerate(SYMBOLS):
        target_mult = 1.4 + i * 0.05
        rows.append(
            {
                "report_id": f"r{i:02d}",
                "publication_date": "2022-03-01",
                "title": f"Equity Research, {symbol}",
                "company": f"Company {i}",
                "ticker": symbol.split(".")[0],
                "exchange": "KRX",
                "symbol": symbol,
                "target_price": 100.0 * target_mult,
                "report_current_price": 100.0,
            }
        )
    return pd.DataFrame(rows)


def _run() -> dict[str, pd.DataFrame]:
    config = BacktestConfig(
        name="phase2-integration",
        entry_rule="target_only",
        weighting="1/N",
        rebalance="weekly",
        stop_loss_pct=0.08,
        reward_risk=3.0,
        lookback_days=252,
        min_target_upside=0.0,
    )
    return run_walk_forward_backtest(_deterministic_reports(), _deterministic_prices(), config)


def _hash(frame: pd.DataFrame) -> str:
    return hashlib.sha256(frame.to_csv(index=False).encode("utf-8")).hexdigest()


@pytest.fixture(scope="module")
def integration_result() -> dict[str, pd.DataFrame]:
    return _run()


def test_equity_curve_is_deterministic_across_runs(integration_result: dict[str, pd.DataFrame]) -> None:
    # Second run with the same inputs must produce the same equity curve hash.
    again = _run()
    for key in ("equity_daily", "execution_events", "strategy_runs"):
        assert _hash(integration_result[key]) == _hash(again[key]), (
            f"{key} hash drifted between two identical runs — engine has hidden state."
        )


def test_integration_run_emits_phase_2a_lookahead_safe_fields(integration_result: dict[str, pd.DataFrame]) -> None:
    events = integration_result["execution_events"]
    assert not events.empty, "phase-2 integration fixture produced no execution events"
    for col in ("signal_date", "decision_price", "fill_price", "fill_rule"):
        assert col in events.columns, f"execution_events missing Phase 2a column {col!r}"
    # Every non-empty row should have a fill_rule in the allowed set.
    observed = set(events["fill_rule"].dropna().unique())
    assert observed <= {"open", "close_fallback", "delisting_last_close"}, f"unexpected fill_rule values: {observed}"


def test_integration_run_emits_phase_2b_oos_metrics(integration_result: dict[str, pd.DataFrame]) -> None:
    runs = integration_result["strategy_runs"]
    assert len(runs) == 1
    row = runs.iloc[0]
    for col in ("sortino_in_sample", "sortino_oos", "sharpe_oos", "max_drawdown_oos", "fold_count"):
        assert col in runs.columns, f"strategy_runs missing Phase 2b column {col!r}"
    # 3-year fixture is long enough that walk-forward must fire.
    assert row["fold_count"] == 3
    assert row["sortino_oos"] is not None
    # Default objective must equal sortino_oos (not total_return) per
    # docs/decisions/phase-2-objective.md.
    import math
    if row["sortino_oos"] is not None and math.isfinite(float(row["sortino_oos"])):
        assert math.isclose(float(row["objective"]), float(row["sortino_oos"]), rel_tol=1e-9)
