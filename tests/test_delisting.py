"""Phase 2 AC #4 — delisted symbols must produce an explicit ``delisting``
exit_reason rather than being silently dropped from the portfolio. The test
constructs a synthetic price series that stops mid-run and asserts the
end-of-sim sweep emits a sell with ``reason='delisting'`` +
``fill_rule='delisting_last_close'``.
"""

from __future__ import annotations

import pandas as pd

from snusmic_pipeline.backtest.engine import run_walk_forward_backtest
from snusmic_pipeline.backtest.schemas import BacktestConfig


def _continuous_prices(symbol: str, start: str, periods: int, base: float) -> pd.DataFrame:
    dates = pd.bdate_range(start, periods=periods)
    close = pd.Series(range(periods), dtype=float) * 0.05 + base
    return pd.DataFrame(
        {
            "date": [d.date().isoformat() for d in dates],
            "symbol": symbol,
            "open": close.values * 0.997,
            "high": close.values * 1.01,
            "low": close.values * 0.99,
            "close": close.values,
            "volume": 1000,
        }
    )


def test_delisted_symbol_emits_explicit_exit() -> None:
    # Symbol A: full history (never delisted).
    # Symbol B: trades for the first 100 bars, then disappears from the data
    # for the remaining 200 bars — must be flagged as delisted.
    good = _continuous_prices("GOOD.KS", "2023-01-02", 300, base=100.0)
    bad = _continuous_prices("BAD.KS", "2023-01-02", 100, base=80.0)
    prices = pd.concat([good, bad], ignore_index=True)

    reports = pd.DataFrame(
        [
            {
                "report_id": "rG",
                "publication_date": "2023-01-10",
                "title": "Good",
                "company": "Good Co",
                "ticker": "GOOD",
                "exchange": "KRX",
                "symbol": "GOOD.KS",
                "target_price": 1000.0,
                "report_current_price": 100.0,
            },
            {
                "report_id": "rB",
                "publication_date": "2023-01-10",
                "title": "Bad",
                "company": "Bad Co",
                "ticker": "BAD",
                "exchange": "KRX",
                "symbol": "BAD.KS",
                "target_price": 1000.0,
                "report_current_price": 80.0,
            },
        ]
    )

    config = BacktestConfig(
        name="delisting",
        entry_rule="target_only",
        weighting="1/N",
        rebalance="daily",
        min_target_upside=0.0,
    )
    result = run_walk_forward_backtest(reports, prices, config)
    events = result["execution_events"]
    delistings = events[events["reason"] == "delisting"]
    assert len(delistings) == 1, (
        f"expected exactly 1 delisting event for BAD.KS, got {len(delistings)}:\n{delistings}"
    )
    row = delistings.iloc[0]
    assert row["symbol"] == "BAD.KS"
    assert row["fill_rule"] == "delisting_last_close"
    assert row["event_type"] == "sell"
