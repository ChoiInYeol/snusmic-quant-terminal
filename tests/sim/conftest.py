"""Shared fixtures for the persona simulation tests.

Builds a small synthetic SNUSMIC-style universe with three symbols and a
two-year price window so the engine has something deterministic to chew
on without touching real warehouse files.
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

from snusmic_pipeline.sim.market import PriceBoard


@pytest.fixture
def synthetic_dates() -> list[date]:
    return [d.date() for d in pd.bdate_range("2024-01-02", "2025-12-31")]


@pytest.fixture
def synthetic_prices(synthetic_dates: list[date]) -> pd.DataFrame:
    """Three symbols:

    * ``WIN`` — steady linear uptrend +1× over the window (peak return ≥ 100%).
    * ``LOSS`` — slow downtrend by 30%.
    * ``FLAT`` — sideways with mild noise so the optimisers see something
      with non-zero covariance.
    """
    rng = np.random.default_rng(42)
    n = len(synthetic_dates)
    win = np.linspace(100.0, 200.0, n) + rng.normal(0, 0.5, n)
    loss = np.linspace(100.0, 70.0, n) + rng.normal(0, 0.4, n)
    flat = 100.0 + rng.normal(0, 0.6, n)
    rows = []
    for sym, series in (("WIN", win), ("LOSS", loss), ("FLAT", flat)):
        for d, close in zip(synthetic_dates, series, strict=True):
            close_v = max(0.5, float(close))
            rows.append(
                {
                    "date": pd.Timestamp(d),
                    "symbol": sym,
                    "open": close_v,
                    "high": close_v,
                    "low": close_v,
                    "close": close_v,
                    "volume": 0.0,
                    "source_currency": "KRW",
                    "display_currency": "KRW",
                    "krw_per_unit": 1.0,
                }
            )
    return pd.DataFrame(rows)


@pytest.fixture
def synthetic_board(synthetic_prices: pd.DataFrame) -> PriceBoard:
    close = synthetic_prices.pivot_table(
        index="date", columns="symbol", values="close", aggfunc="last"
    ).sort_index()
    open_ = close.copy()
    return PriceBoard(close=close, open=open_)


@pytest.fixture
def synthetic_reports() -> pd.DataFrame:
    """Three reports, one per synthetic symbol, all published on day 0."""
    return pd.DataFrame(
        [
            {
                "report_id": "r-win",
                "symbol": "WIN",
                "company": "Winners Co",
                "publication_date": pd.Timestamp("2024-01-02"),
                "target_price": 180.0,
                "_pub": date(2024, 1, 2),
            },
            {
                "report_id": "r-loss",
                "symbol": "LOSS",
                "company": "Losers Co",
                "publication_date": pd.Timestamp("2024-01-02"),
                "target_price": 130.0,
                "_pub": date(2024, 1, 2),
            },
            {
                "report_id": "r-flat",
                "symbol": "FLAT",
                "company": "Flat Co",
                "publication_date": pd.Timestamp("2024-01-02"),
                "target_price": 110.0,
                "_pub": date(2024, 1, 2),
            },
        ]
    )
