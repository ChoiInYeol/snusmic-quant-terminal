"""End-to-end runner determinism."""

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
    SmicFollowerV2Config,
    WeakProphetConfig,
)
from snusmic_pipeline.sim.runner import run_simulation
from snusmic_pipeline.sim.warehouse import (
    apply_daily_price_krw_conversion,
    fill_report_publication_prices,
    refresh_price_history,
)


@pytest.fixture
def fake_warehouse(tmp_path: Path) -> Path:
    """Tiny warehouse: three KRW symbols and a matching reports CSV."""
    warehouse = tmp_path / "wh"
    warehouse.mkdir()
    dates = pd.bdate_range("2024-01-02", "2025-12-31")
    rng = np.random.default_rng(11)
    n = len(dates)
    paths = {
        "WIN.KS": np.linspace(100.0, 220.0, n) + rng.normal(0, 1.0, n),
        "MID.KS": np.linspace(100.0, 105.0, n) + rng.normal(0, 1.0, n),
        "LOW.KS": np.linspace(100.0, 70.0, n) + rng.normal(0, 1.0, n),
    }
    rows = []
    for sym, series in paths.items():
        for d, close in zip(dates, series, strict=True):
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
                "target_price": 200.0,
                "target_price_krw": 200.0,
            },
            {
                "report_id": "r-mid",
                "page": 1,
                "ordinal": 2,
                "publication_date": "2024-01-02",
                "title": "Mid",
                "company": "MID",
                "ticker": "MID",
                "exchange": "KRX",
                "symbol": "MID.KS",
                "target_price": 110.0,
                "target_price_krw": 110.0,
            },
            {
                "report_id": "r-low",
                "page": 1,
                "ordinal": 3,
                "publication_date": "2024-01-02",
                "title": "Low",
                "company": "LOW",
                "ticker": "LOW",
                "exchange": "KRX",
                "symbol": "LOW.KS",
                "target_price": 130.0,
                "target_price_krw": 130.0,
            },
        ]
    ).to_csv(warehouse / "reports.csv", index=False)
    return warehouse


def _config_without_all_weather() -> SimulationConfig:
    return SimulationConfig(
        start_date=date(2024, 1, 2),
        end_date=date(2025, 12, 31),
        savings_plan=SavingsPlan(),
        fees=BrokerageFees(),
        personas=(
            ProphetConfig(),
            WeakProphetConfig(lookahead_months=3, min_history_days=30),
            SmicFollowerConfig(),
            SmicFollowerV2Config(time_loss_days=200, report_age_stop_days=600),
        ),
    )


def test_runner_returns_one_summary_per_persona(fake_warehouse: Path):
    cfg = _config_without_all_weather()
    result = run_simulation(cfg, fake_warehouse)
    assert len(result.summaries) == 4
    by_name = {s.persona for s in result.summaries}
    assert by_name == {"oracle", "weak_oracle", "smic_follower", "smic_follower_v2"}


def test_runner_is_deterministic_across_repeated_runs(fake_warehouse: Path):
    cfg = _config_without_all_weather()
    a = run_simulation(cfg, fake_warehouse)
    b = run_simulation(cfg, fake_warehouse)
    a_summaries = sorted((s.model_dump() for s in a.summaries), key=lambda d: d["persona"])
    b_summaries = sorted((s.model_dump() for s in b.summaries), key=lambda d: d["persona"])
    assert a_summaries == b_summaries
    assert len(a.equity_points) == len(b.equity_points)
    assert len(a.trades) == len(b.trades)


def test_runner_serialises_to_json(fake_warehouse: Path):
    cfg = _config_without_all_weather()
    result = run_simulation(cfg, fake_warehouse)
    payload = result.model_dump_json()
    assert "oracle" in payload
    assert "smic_follower_v2" in payload


def test_prophet_beats_smic_follower_on_synthetic_universe(fake_warehouse: Path):
    cfg = _config_without_all_weather()
    result = run_simulation(cfg, fake_warehouse)
    by_name = {s.persona: s for s in result.summaries}
    assert by_name["oracle"].net_profit_krw >= by_name["smic_follower"].net_profit_krw


def test_split_scaled_report_target_is_aligned_to_market_price_units(tmp_path: Path):
    warehouse = tmp_path / "wh"
    warehouse.mkdir()
    pd.DataFrame(
        [
            {
                "date": "2024-01-02",
                "symbol": "SPLIT.KS",
                "open": 100.0,
                "high": 100.0,
                "low": 100.0,
                "close": 100.0,
                "volume": 1,
                "source_currency": "KRW",
                "display_currency": "KRW",
                "krw_per_unit": 1.0,
            },
            {
                "date": "2024-01-03",
                "symbol": "SPLIT.KS",
                "open": 160.0,
                "high": 160.0,
                "low": 160.0,
                "close": 160.0,
                "volume": 1,
                "source_currency": "KRW",
                "display_currency": "KRW",
                "krw_per_unit": 1.0,
            },
        ]
    ).to_csv(warehouse / "daily_prices.csv", index=False)
    pd.DataFrame(
        [
            {
                "report_id": "r-split",
                "page": 1,
                "ordinal": 1,
                "publication_date": "2024-01-02",
                "title": "Split scale",
                "company": "SplitCo",
                "ticker": "SPLIT",
                "exchange": "KRX",
                "symbol": "SPLIT.KS",
                "report_current_price_krw": 1000.0,
                "target_price": 1500.0,
                "target_price_krw": 1500.0,
            }
        ]
    ).to_csv(warehouse / "reports.csv", index=False)

    result = run_simulation(
        SimulationConfig(
            start_date=date(2024, 1, 2),
            end_date=date(2024, 1, 3),
            savings_plan=SavingsPlan(initial_capital_krw=1_000_000, monthly_contribution_krw=0),
            fees=BrokerageFees(commission_bps=0, sell_tax_bps=0, slippage_bps=0),
            personas=(SmicFollowerConfig(),),
        ),
        warehouse,
    )

    perf = result.report_performance[0]
    assert perf.target_price_krw == pytest.approx(150.0)
    assert perf.target_upside_at_pub == pytest.approx(0.5)
    assert perf.target_hit is True
    assert perf.target_hit_date == date(2024, 1, 3)
    assert any(trade.reason == "target_hit" for trade in result.trades)


def test_current_price_scale_mismatch_does_not_expand_plausible_target(tmp_path: Path):
    warehouse = tmp_path / "wh"
    warehouse.mkdir()
    pd.DataFrame(
        [
            {
                "date": "2024-01-02",
                "symbol": "UNIT.KQ",
                "open": 9210.0,
                "high": 9210.0,
                "low": 9210.0,
                "close": 9210.0,
                "volume": 1,
                "source_currency": "KRW",
                "display_currency": "KRW",
                "krw_per_unit": 1.0,
            },
            {
                "date": "2024-01-03",
                "symbol": "UNIT.KQ",
                "open": 10000.0,
                "high": 10000.0,
                "low": 10000.0,
                "close": 10000.0,
                "volume": 1,
                "source_currency": "KRW",
                "display_currency": "KRW",
                "krw_per_unit": 1.0,
            },
        ]
    ).to_csv(warehouse / "daily_prices.csv", index=False)
    pd.DataFrame(
        [
            {
                "report_id": "r-unit",
                "page": 1,
                "ordinal": 1,
                "publication_date": "2024-01-02",
                "title": "Unit mismatch",
                "company": "UnitCo",
                "ticker": "UNIT",
                "exchange": "KRX",
                "symbol": "UNIT.KQ",
                "report_current_price_krw": 9.6,
                "target_price": 18600.0,
                "target_price_krw": 18600.0,
            }
        ]
    ).to_csv(warehouse / "reports.csv", index=False)

    result = run_simulation(
        SimulationConfig(
            start_date=date(2024, 1, 2),
            end_date=date(2024, 1, 3),
            savings_plan=SavingsPlan(initial_capital_krw=1_000_000, monthly_contribution_krw=0),
            fees=BrokerageFees(commission_bps=0, sell_tax_bps=0, slippage_bps=0),
            personas=(SmicFollowerConfig(),),
        ),
        warehouse,
    )

    perf = result.report_performance[0]
    assert perf.target_price_krw == pytest.approx(18600.0)
    assert perf.target_upside_at_pub == pytest.approx(18600.0 / 9210.0 - 1.0)
    assert perf.target_hit is False


def test_downside_target_uses_first_close_at_or_below_target(tmp_path: Path):
    warehouse = tmp_path / "wh"
    warehouse.mkdir()
    pd.DataFrame(
        [
            {
                "date": "2024-01-05",
                "symbol": "IPO.KQ",
                "open": 117000.0,
                "high": 117000.0,
                "low": 117000.0,
                "close": 117000.0,
                "volume": 1,
                "source_currency": "KRW",
                "display_currency": "KRW",
                "krw_per_unit": 1.0,
            },
            {
                "date": "2024-01-08",
                "symbol": "IPO.KQ",
                "open": 152100.0,
                "high": 152100.0,
                "low": 152100.0,
                "close": 152100.0,
                "volume": 1,
                "source_currency": "KRW",
                "display_currency": "KRW",
                "krw_per_unit": 1.0,
            },
        ]
    ).to_csv(warehouse / "daily_prices.csv", index=False)
    pd.DataFrame(
        [
            {
                "report_id": "r-ipo",
                "page": 1,
                "ordinal": 1,
                "publication_date": "2024-01-02",
                "title": "Already above target",
                "company": "IpoCo",
                "ticker": "IPO",
                "exchange": "KRX",
                "symbol": "IPO.KQ",
                "target_price": 105000.0,
                "target_price_krw": 105000.0,
            }
        ]
    ).to_csv(warehouse / "reports.csv", index=False)

    result = run_simulation(
        SimulationConfig(
            start_date=date(2024, 1, 2),
            end_date=date(2024, 1, 8),
            savings_plan=SavingsPlan(initial_capital_krw=1_000_000, monthly_contribution_krw=0),
            fees=BrokerageFees(commission_bps=0, sell_tax_bps=0, slippage_bps=0),
            personas=(SmicFollowerConfig(),),
        ),
        warehouse,
    )

    perf = result.report_performance[0]
    assert perf.entry_price_krw == pytest.approx(117000.0)
    assert perf.target_upside_at_pub == pytest.approx(105000.0 / 117000.0 - 1.0)
    assert perf.target_hit is False
    assert perf.target_hit_date is None
    assert perf.days_to_target is None
    assert perf.target_gap_pct == pytest.approx(105000.0 / 152100.0 - 1.0)
    assert not result.trades


def test_downside_target_is_hit_when_close_falls_to_bearish_target(tmp_path: Path):
    warehouse = tmp_path / "wh"
    warehouse.mkdir()
    pd.DataFrame(
        [
            {
                "date": "2024-01-02",
                "symbol": "SELL.KQ",
                "open": 100.0,
                "high": 100.0,
                "low": 100.0,
                "close": 100.0,
                "volume": 1,
                "source_currency": "KRW",
                "display_currency": "KRW",
                "krw_per_unit": 1.0,
            },
            {
                "date": "2024-01-03",
                "symbol": "SELL.KQ",
                "open": 75.0,
                "high": 75.0,
                "low": 75.0,
                "close": 75.0,
                "volume": 1,
                "source_currency": "KRW",
                "display_currency": "KRW",
                "krw_per_unit": 1.0,
            },
        ]
    ).to_csv(warehouse / "daily_prices.csv", index=False)
    pd.DataFrame(
        [
            {
                "report_id": "r-sell",
                "page": 1,
                "ordinal": 1,
                "publication_date": "2024-01-02",
                "title": "Bearish target",
                "company": "SellCo",
                "ticker": "SELL",
                "exchange": "KRX",
                "symbol": "SELL.KQ",
                "target_price": 80.0,
                "target_price_krw": 80.0,
            }
        ]
    ).to_csv(warehouse / "reports.csv", index=False)

    result = run_simulation(
        SimulationConfig(
            start_date=date(2024, 1, 2),
            end_date=date(2024, 1, 3),
            savings_plan=SavingsPlan(initial_capital_krw=1_000_000, monthly_contribution_krw=0),
            fees=BrokerageFees(commission_bps=0, sell_tax_bps=0, slippage_bps=0),
            personas=(SmicFollowerConfig(),),
        ),
        warehouse,
    )

    perf = result.report_performance[0]
    assert perf.target_price_krw == pytest.approx(80.0)
    assert perf.target_upside_at_pub == pytest.approx(-0.2)
    assert perf.target_hit is True
    assert perf.target_hit_date == date(2024, 1, 3)
    assert perf.target_gap_pct == pytest.approx(80.0 / 75.0 - 1.0)
    assert not result.trades


def test_krw_price_conversion_is_idempotent_for_cached_rows():
    prices = pd.DataFrame(
        [
            {
                "date": "2024-01-02",
                "symbol": "USD",
                "close": 1300.0,
                "display_currency": "KRW",
                "krw_per_unit": 1300.0,
            },
            {"date": "2024-01-02", "symbol": "RAW", "close": 10.0},
        ]
    )
    reports = pd.DataFrame(
        [
            {"symbol": "USD", "exchange": "NYSE"},
            {"symbol": "RAW", "exchange": "NYSE"},
        ]
    )
    fx = pd.DataFrame(
        [{"date": "2024-01-02", "currency": "USD", "fx_symbol": "KRW=X", "krw_per_unit": 1300.0}]
    )

    converted = apply_daily_price_krw_conversion(prices, reports, fx)

    assert converted.loc[converted["symbol"] == "USD", "close"].iloc[0] == 1300.0
    assert converted.loc[converted["symbol"] == "RAW", "close"].iloc[0] == 13000.0


def test_publication_price_keeps_report_quote_when_market_price_is_split_scaled():
    reports = pd.DataFrame(
        [
            {
                "symbol": "EAF",
                "publication_date": "2022-05-25",
                "report_current_price_krw": 10395.0,
            }
        ]
    )
    prices = pd.DataFrame([{"symbol": "EAF", "date": "2022-05-25", "close": 107184.0}])

    filled = fill_report_publication_prices(reports, prices)

    assert filled.loc[0, "report_current_price_krw"] == 10395.0


def test_partial_price_refresh_preserves_existing_symbol_history(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    warehouse = tmp_path / "warehouse"
    warehouse.mkdir()
    pd.DataFrame(
        [
            {
                "report_id": "r-aaa",
                "page": 1,
                "ordinal": 1,
                "publication_date": "2024-01-02",
                "title": "AAA",
                "company": "AAA",
                "ticker": "AAA",
                "exchange": "KRX",
                "symbol": "AAA.KS",
                "target_price": 120.0,
                "target_price_krw": 120.0,
                "target_currency": "KRW",
            }
        ]
    ).to_csv(warehouse / "reports.csv", index=False)
    pd.DataFrame(
        [
            {
                "date": "2024-01-02",
                "symbol": "AAA.KS",
                "open": 100.0,
                "high": 100.0,
                "low": 100.0,
                "close": 100.0,
                "volume": 1,
                "source_currency": "KRW",
                "display_currency": "KRW",
                "krw_per_unit": 1.0,
            }
        ]
    ).to_csv(warehouse / "daily_prices.csv", index=False)

    monkeypatch.setattr(
        "snusmic_pipeline.sim.warehouse.download_fx_rates", lambda *args, **kwargs: pd.DataFrame()
    )

    def downloader(symbol, start, end):
        assert symbol == "AAA.KS"
        return pd.DataFrame(
            [{"date": "2024-01-03", "open": 101.0, "high": 101.0, "low": 101.0, "close": 101.0, "volume": 2}]
        )

    refreshed = refresh_price_history(tmp_path, warehouse, downloader=downloader, symbols=["AAA.KS"])

    assert refreshed[refreshed["symbol"] == "AAA.KS"]["date"].tolist() == ["2024-01-02", "2024-01-03"]
