import math

import pandas as pd

from snusmic_pipeline.backtest.engine import run_walk_forward_backtest
from snusmic_pipeline.backtest.optimizers import optimize_execution_weights
from snusmic_pipeline.backtest.schemas import BacktestConfig
from snusmic_pipeline.backtest.signals import compute_signals_daily
from snusmic_pipeline.backtest.warehouse import apply_report_krw_targets, export_dashboard_data, run_default_backtests, write_table


def report_frame(publication_date="2024-01-10", target_price=140.0):
    return pd.DataFrame(
        [
            {
                "report_id": "r1",
                "publication_date": publication_date,
                "title": "Equity Research, Alpha",
                "company": "Alpha",
                "ticker": "000001",
                "exchange": "KRX",
                "symbol": "000001.KS",
                "target_price": target_price,
                "report_current_price": 100.0,
            }
        ]
    )


def price_frame(symbols=("000001.KS",), start="2023-01-02", periods=340):
    dates = pd.bdate_range(start, periods=periods)
    rows = []
    for i, symbol in enumerate(symbols):
        base = 80 + i * 10
        close = pd.Series(range(periods), dtype=float) * (0.12 + i * 0.02) + base
        for date, price in zip(dates, close, strict=True):
            rows.append({"date": date.date().isoformat(), "symbol": symbol, "open": price, "high": price, "low": price, "close": price, "volume": 1000})
    return pd.DataFrame(rows)


def test_mtt_signal_and_candidate_rs_do_not_include_future_candidates():
    reports = pd.DataFrame(
        [
            {"report_id": "r1", "publication_date": "2023-06-01", "symbol": "000001.KS"},
            {"report_id": "r2", "publication_date": "2024-03-01", "symbol": "000002.KS"},
        ]
    )
    prices = price_frame(("000001.KS", "000002.KS"), periods=360)

    signals = compute_signals_daily(prices, reports, mtt_slope_months=1)

    alpha_late = signals[(signals["symbol"] == "000001.KS") & (signals["date"] > pd.Timestamp("2024-02-01"))]
    assert alpha_late["mtt_pass"].any()
    beta_before_publication = signals[(signals["symbol"] == "000002.KS") & (signals["date"] < pd.Timestamp("2024-03-01"))]
    assert beta_before_publication["candidate_universe_active"].eq(False).all()
    assert beta_before_publication["rs_score"].isna().all()


def test_candidate_starts_after_publication_and_strategy_buys_from_pool():
    reports = report_frame("2024-01-10", target_price=200.0)
    prices = price_frame(periods=320)
    config = BacktestConfig(name="target", entry_rule="target_only", weighting="1/N", rebalance="daily", min_target_upside=0.0)

    result = run_walk_forward_backtest(reports, prices, config)
    candidate_events = result["candidate_pool_events"]
    execution_events = result["execution_events"]

    assert candidate_events.iloc[0]["event_type"] == "candidate_add"
    assert pd.Timestamp(candidate_events.iloc[0]["date"]) > pd.Timestamp("2024-01-10")
    assert "buy" in set(execution_events["event_type"])
    assert result["strategy_runs"].iloc[0]["status"] == "ok"


def test_stop_loss_sell_event_realizes_arithmetic_return():
    reports = report_frame("2024-01-10", target_price=300.0)
    prices = price_frame(periods=280)
    after_publication = prices["date"] > "2024-01-15"
    prices.loc[after_publication, "close"] = prices.loc[after_publication, "close"] * 0.85
    prices[["open", "high", "low"]] = prices[["close", "close", "close"]].to_numpy()
    config = BacktestConfig(name="stop", entry_rule="target_only", weighting="1/N", rebalance="daily", stop_loss_pct=0.08)

    result = run_walk_forward_backtest(reports, prices, config)
    sells = result["execution_events"][result["execution_events"]["event_type"] == "sell"]

    assert "stop_loss" in set(sells["reason"])
    assert sells["realized_return"].notna().any()


def test_cvar_optimizer_returns_no_short_normalized_weights():
    returns = pd.DataFrame({"A": [0.01, -0.03, 0.02, 0.01], "B": [0.0, -0.01, 0.01, 0.02]})

    weights = optimize_execution_weights(returns, ["A", "B"], "cvar", 0.03)

    assert set(weights) == {"A", "B"}
    assert all(value >= 0 for value in weights.values())
    assert math.isclose(sum(weights.values()), 1.0)


def test_dashboard_export_from_warehouse_tables(tmp_path):
    data_dir = tmp_path / "data"
    warehouse = data_dir / "warehouse"
    reports = report_frame("2024-01-10", target_price=200.0)
    prices = price_frame(periods=320)
    write_table(warehouse, "reports", reports)
    write_table(warehouse, "daily_prices", prices)

    counts = run_default_backtests(data_dir, warehouse)
    exports = export_dashboard_data(data_dir, warehouse, data_dir / "quant_v3")

    assert counts["strategy_runs"] > 0
    assert exports["strategy_runs.json"] > 0
    assert (data_dir / "quant_v3" / "pool_timeline.json").exists()
    assert exports["chart_series/index.json"] > 0
    assert (data_dir / "quant_v3" / "chart_series" / "index.json").exists()


def test_report_targets_are_converted_to_krw_for_backtest_comparison():
    reports = report_frame("2024-01-10", target_price=100.0)
    reports["exchange"] = "NASDAQ"
    reports["symbol"] = "IRMD"
    reports["target_currency"] = "USD"
    reports["target_price_local"] = 100.0
    fx = pd.DataFrame({"date": ["2024-01-10"], "currency": ["USD"], "fx_symbol": ["KRW=X"], "krw_per_unit": [1300.0]})

    converted = apply_report_krw_targets(reports, fx)

    assert converted.iloc[0]["target_price"] == 130000.0
    assert converted.iloc[0]["target_price_krw"] == 130000.0
    assert converted.iloc[0]["display_currency"] == "KRW"
