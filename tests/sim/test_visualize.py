"""Smoke tests for the matplotlib renderers."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from snusmic_pipeline.sim.contracts import (
    BrokerageFees,
    ProphetConfig,
    SavingsPlan,
    SimulationConfig,
    SmicFollowerConfig,
)
from snusmic_pipeline.sim.runner import run_simulation
from snusmic_pipeline.sim.visualize import (
    plot_drawdowns,
    plot_equity_curves,
    plot_net_profit_bars,
)


@pytest.fixture
def viz_warehouse(tmp_path: Path) -> Path:
    warehouse = tmp_path / "wh"
    warehouse.mkdir()
    dates = pd.bdate_range("2024-01-02", "2024-12-31")
    rng = np.random.default_rng(99)
    rows = []
    for sym, drift in [("WIN.KS", 0.001), ("LOW.KS", -0.0005)]:
        path = np.cumprod(1.0 + drift + rng.normal(0, 0.01, len(dates))) * 100
        for d, close in zip(dates, path, strict=True):
            v = max(1.0, float(close))
            rows.append(
                {
                    "date": d.date().isoformat(),
                    "symbol": sym,
                    "open": v,
                    "high": v,
                    "low": v,
                    "close": v,
                    "volume": 0,
                    "source_currency": "KRW",
                    "display_currency": "KRW",
                    "krw_per_unit": 1.0,
                }
            )
    pd.DataFrame(rows).to_csv(warehouse / "daily_prices.csv", index=False)
    pd.DataFrame(
        [
            {
                "report_id": "r-win",
                "page": 1,
                "ordinal": 1,
                "publication_date": "2024-01-02",
                "title": "Winners",
                "company": "WIN",
                "ticker": "WIN",
                "exchange": "KRX",
                "symbol": "WIN.KS",
                "target_price": 130.0,
                "target_price_krw": 130.0,
            },
            {
                "report_id": "r-low",
                "page": 1,
                "ordinal": 2,
                "publication_date": "2024-01-02",
                "title": "Low",
                "company": "LOW",
                "ticker": "LOW.KS",
                "exchange": "KRX",
                "symbol": "LOW.KS",
                "target_price": 120.0,
                "target_price_krw": 120.0,
            },
        ]
    ).to_csv(warehouse / "reports.csv", index=False)
    return warehouse


def test_renderers_emit_nonempty_pngs(tmp_path: Path, viz_warehouse: Path):
    cfg = SimulationConfig(
        start_date=date(2024, 1, 2),
        end_date=date(2024, 12, 31),
        savings_plan=SavingsPlan(monthly_contribution_krw=500_000),
        fees=BrokerageFees(),
        personas=(ProphetConfig(), SmicFollowerConfig()),
    )
    result = run_simulation(cfg, viz_warehouse)
    eq = plot_equity_curves(result, tmp_path / "eq.png")
    np_ = plot_net_profit_bars(result, tmp_path / "np.png")
    dd = plot_drawdowns(result, tmp_path / "dd.png")
    for path in (eq, np_, dd):
        assert path.exists()
        assert path.stat().st_size > 1000  # actual PNG data, not an empty file
