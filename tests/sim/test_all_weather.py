"""All-Weather benchmark behavior."""

from __future__ import annotations

import numpy as np
import pandas as pd

from snusmic_pipeline.sim.contracts import (
    AllWeatherConfig,
    BenchmarkAsset,
    BrokerageFees,
    SavingsPlan,
)
from snusmic_pipeline.sim.market import PriceBoard
from snusmic_pipeline.sim.personas import simulate_all_weather
from snusmic_pipeline.sim.savings import build_cash_flow_schedule


def _bench_board() -> PriceBoard:
    """Synthetic 2y daily board for the four All-Weather slots."""
    dates = pd.bdate_range("2024-01-02", "2025-12-31")
    rng = np.random.default_rng(7)
    n = len(dates)
    price_paths = {
        "GLD": np.cumprod(1.0 + rng.normal(0.0003, 0.008, n)) * 200_000,
        "QQQ": np.cumprod(1.0 + rng.normal(0.0006, 0.012, n)) * 500_000,
        "SPY": np.cumprod(1.0 + rng.normal(0.0005, 0.010, n)) * 600_000,
        "069500.KS": np.cumprod(1.0 + rng.normal(0.0002, 0.011, n)) * 50_000,
    }
    rows = []
    for sym, series in price_paths.items():
        for d, close in zip(dates, series, strict=True):
            rows.append({"date": d, "symbol": sym, "close": float(close), "open": float(close)})
    df = pd.DataFrame(rows)
    close = df.pivot_table(index="date", columns="symbol", values="close", aggfunc="last").sort_index()
    return PriceBoard(close=close, open=close.copy())


def test_all_weather_holds_all_four_buckets():
    plan = SavingsPlan()
    fees = BrokerageFees()
    board = _bench_board()
    trading_dates = [d.date() for d in board.close.index]
    cashflows = build_cash_flow_schedule(trading_dates, plan)
    cfg = AllWeatherConfig()
    out = simulate_all_weather(cfg, plan, fees, board, cashflows, trading_dates)
    bought_symbols = {t.symbol for t in out.account.trades if t.side == "buy"}
    assert bought_symbols >= {"GLD", "QQQ", "SPY", "069500.KS"}


def test_all_weather_balanced_within_a_few_percent_at_rebalance(synthetic_dates):
    plan = SavingsPlan(initial_capital_krw=10_000_000, monthly_contribution_krw=1_000_000)
    fees = BrokerageFees(commission_bps=0, sell_tax_bps=0, slippage_bps=0)
    board = _bench_board()
    trading_dates = [d.date() for d in board.close.index]
    cashflows = build_cash_flow_schedule(trading_dates, plan)
    cfg = AllWeatherConfig()
    out = simulate_all_weather(cfg, plan, fees, board, cashflows, trading_dates)
    # The rebalance happens monthly, so even at the worst intramonth drift
    # weights should hover in a tight band around 25%. Use the final-day prices
    # since holdings reflect the end-of-sim share book.
    last_day = trading_dates[-1]
    prices = board.close_on(last_day)
    equity = out.account.equity(prices)
    weights = {
        sym: lot.qty * prices[sym] / equity
        for sym, lot in out.account.holdings.items()
        if lot.qty > 0 and sym in prices
    }
    assert len(weights) == 4
    for w in weights.values():
        assert 0.15 <= w <= 0.40


def test_all_weather_handles_partial_basket_when_one_symbol_missing():
    """If one ETF is missing for the date, the persona must still rebalance the rest."""
    plan = SavingsPlan(initial_capital_krw=10_000_000, monthly_contribution_krw=0)
    fees = BrokerageFees()
    board = _bench_board()
    # Drop the GLD column entirely.
    board.close.drop(columns=["GLD"], inplace=True)
    board.open.drop(columns=["GLD"], inplace=True)
    trading_dates = [d.date() for d in board.close.index]
    cashflows = build_cash_flow_schedule(trading_dates, plan)
    cfg = AllWeatherConfig(
        assets=(
            BenchmarkAsset(name="Gold", symbol="GLD", weight=0.25),
            BenchmarkAsset(name="QQQ", symbol="QQQ", weight=0.25),
            BenchmarkAsset(name="SPY", symbol="SPY", weight=0.25),
            BenchmarkAsset(name="KOSPI", symbol="069500.KS", weight=0.25),
        )
    )
    out = simulate_all_weather(cfg, plan, fees, board, cashflows, trading_dates)
    bought = {t.symbol for t in out.account.trades if t.side == "buy"}
    assert "GLD" not in bought
    assert {"QQQ", "SPY", "069500.KS"} <= bought


def test_all_weather_skips_rebalance_on_us_holiday_korean_trading_day():
    """Korean trading day + US holiday must NOT cause a 100% KOSPI rebalance.

    Reproduces the historical bug where on dates that the SNUSMIC universe
    treated as trading days but the US ETFs had no close (e.g. Thanksgiving,
    July 4), the per-day weight renormalization concentrated the entire book
    into 069500.KS.

    Per-asset cadence fix: each ETF rebalances toward its target weight on
    the first trading day of the month *on its own exchange*. When US is
    closed and KR is open, KOSPI fires on its KR-first-of-month and the
    US ETFs skip that day, firing on the next day they have a close. No
    100% concentration ever happens because each asset only ever moves
    toward its own 25% slot.
    """
    plan = SavingsPlan(initial_capital_krw=10_000_000, monthly_contribution_krw=0)
    fees = BrokerageFees(commission_bps=0, sell_tax_bps=0, slippage_bps=0)
    board = _bench_board()
    trading_dates = [d.date() for d in board.close.index]
    # Punch NaN holes into the US ETFs on the FIRST trading day of every
    # month — without per-asset cadence this is the worst-case "100% KOSPI"
    # trigger; with it, those days only trigger KOSPI's own rebalance.
    first_of_month: dict[tuple[int, int], pd.Timestamp] = {}
    for ts in board.close.index:
        first_of_month.setdefault((ts.year, ts.month), ts)
    holiday_ts = list(first_of_month.values())
    for ts in holiday_ts:
        for sym in ("GLD", "QQQ", "SPY"):
            board.close.at[ts, sym] = float("nan")
    cashflows = build_cash_flow_schedule(trading_dates, plan)
    cfg = AllWeatherConfig()
    out = simulate_all_weather(cfg, plan, fees, board, cashflows, trading_dates)
    # Final composition should still hold all four buckets near 25/25/25/25.
    last_day = trading_dates[-1]
    prices = board.close_on(last_day)
    equity = out.account.equity(prices)
    weights = {
        sym: lot.qty * prices[sym] / equity
        for sym, lot in out.account.holdings.items()
        if lot.qty > 0 and sym in prices
    }
    assert len(weights) == 4
    for w in weights.values():
        assert 0.15 <= w <= 0.40
    # No US-ETF trade should land on a punched holiday date — each ETF
    # waits for the next day its own market is open. KOSPI may (and
    # should) trade on those dates because they are KR's first-of-month.
    holiday_dates = {ts.date() for ts in holiday_ts}
    us_holiday_trades = [
        t for t in out.account.trades
        if t.date in holiday_dates and t.symbol in {"GLD", "QQQ", "SPY"}
    ]
    assert not us_holiday_trades
