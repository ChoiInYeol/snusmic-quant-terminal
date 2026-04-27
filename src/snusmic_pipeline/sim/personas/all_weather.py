"""All-Weather benchmark.

Constant-weight DCA across the basket declared in
:class:`AllWeatherConfig`. Each ETF rebalances itself toward its target
weight on **the first trading day of the cadence period on its own
exchange** — KR ETFs on KR's first KR-trading-day of each month, US
ETFs on US's first US-trading-day of each month. The two firings do not
need to coincide: cash from deposits or dividends just sits until the
next per-asset trigger absorbs it.

This per-asset cadence is the realistic model — IRL you'd place each
order on its market's normal calendar — and avoids the historical
"100% KOSPI on US holidays" trap that the old whole-basket rebalance
fell into without an aggressive deferral hack.

This persona uses its own :class:`PriceBoard` (benchmark ETFs in KRW),
not the SNUSMIC report universe.
"""

from __future__ import annotations

import math
from datetime import date

from ..brokerage import Account
from ..contracts import AllWeatherConfig, BrokerageFees, SavingsPlan
from ..market import PriceBoard
from ..savings import CashFlowEvent
from .base import (
    PersonaRunOutput,
    build_summary,
    cumulative_contributions,
    record_equity_point,
)


def simulate_all_weather(
    config: AllWeatherConfig,
    plan: SavingsPlan,
    fees: BrokerageFees,
    benchmark_board: PriceBoard,
    cashflows: list[CashFlowEvent],
    trading_dates: list[date],
    label: str = "All-Weather (25/25/25/25)",
) -> PersonaRunOutput:
    persona = config.persona_name
    account = Account(persona=persona, fees=fees)
    cashflow_by_date: dict[date, float] = {e.date: e.amount_krw for e in cashflows}

    if not trading_dates or benchmark_board.is_empty:
        return PersonaRunOutput(
            account=account,
            equity_points=[],
            summary=build_summary(persona, label, account, [], cashflows, plan.initial_capital_krw),
        )

    target_weights_full = {asset.symbol: asset.weight for asset in config.assets}
    daily_closes = {d: benchmark_board.close_on(d) for d in trading_dates}

    # Drop targets that have NO close anywhere in the window (e.g. dataset
    # missing one ETF) and renormalize once. This is the only legitimate
    # reason to deviate from the configured weights — never per-day, since
    # per-day pruning concentrates the book into whatever subset of markets
    # happened to be open (e.g. Korea-open + US-closed → 100% KOSPI).
    seen: set[str] = set()
    for prices in daily_closes.values():
        seen.update(prices)
    target_weights = {sym: w for sym, w in target_weights_full.items() if sym in seen}
    weight_sum = sum(target_weights.values())
    if weight_sum > 0 and not math.isclose(weight_sum, 1.0):
        target_weights = {sym: w / weight_sum for sym, w in target_weights.items()}
    target_symbols = set(target_weights)

    # Per-asset cadence: each ETF triggers its own rebalance on the first
    # trading day of the cadence period AS OBSERVED ON THAT ETF'S EXCHANGE.
    # Two separate firings (KR vs. US) just absorb their share of any
    # accumulated cash; we never try to push KOSPI to 100% because US
    # markets happen to be closed today.
    asset_rebalance_days = _per_asset_rebalance_days(
        trading_dates, daily_closes, target_symbols, config.rebalance
    )

    contributions = cumulative_contributions(cashflows, trading_dates)
    equity_points: list = []

    for day in trading_dates:
        deposit = cashflow_by_date.get(day, 0.0)
        if deposit > 0:
            account.deposit(day, deposit)
        # Per-asset rebalance: each ETF whose own exchange is at its
        # first-of-period today rebalances itself toward
        # ``target_weight × current_equity``. Other ETFs' share counts are
        # untouched — their next firing on their own market will catch up.
        due_today = [sym for sym in target_weights if day in asset_rebalance_days.get(sym, frozenset())]
        if due_today:
            prices = _build_price_view(benchmark_board, daily_closes.get(day, {}), account, day)
            equity_now = account.equity(prices)
            for sym in due_today:
                target_value = equity_now * target_weights[sym]
                _rebalance_one_asset(account, day, sym, target_value, prices.get(sym))
        equity_points.append(
            record_equity_point(
                account,
                persona,
                day,
                daily_closes.get(day, {}),
                contributions[day],
                board=benchmark_board,
            )
        )

    summary = build_summary(persona, label, account, equity_points, cashflows, plan.initial_capital_krw)
    return PersonaRunOutput(account=account, equity_points=equity_points, summary=summary)


def _per_asset_rebalance_days(
    trading_dates: list[date],
    daily_closes: dict[date, dict[str, float]],
    target_symbols: set[str],
    cadence: str,
) -> dict[str, frozenset[date]]:
    """For each target symbol, the first trading date of every cadence
    period where the symbol has a valid close — i.e. the symbol's own
    exchange's first-of-period day, restricted to the dates we actually
    iterate."""
    out: dict[str, frozenset[date]] = {}
    for sym in target_symbols:
        sym_days = [
            d for d in trading_dates
            if sym in daily_closes.get(d, {}) and daily_closes[d][sym] > 0
        ]
        if cadence == "monthly":
            first: dict[tuple[int, int], date] = {}
            for d in sym_days:
                first.setdefault((d.year, d.month), d)
        elif cadence == "quarterly":
            first = {}
            for d in sym_days:
                first.setdefault((d.year, (d.month - 1) // 3), d)
        elif cadence == "yearly":
            first_y: dict[int, date] = {}
            for d in sym_days:
                first_y.setdefault(d.year, d)
            out[sym] = frozenset(first_y.values())
            continue
        else:
            raise ValueError(f"unknown all-weather cadence: {cadence}")
        out[sym] = frozenset(first.values())
    return out


def _build_price_view(
    benchmark_board: PriceBoard,
    prices_today: dict[str, float],
    account: Account,
    day: date,
) -> dict[str, float]:
    """Today's closes where available, asof for held-but-closed-market
    symbols. Used to mark equity for the per-asset rebalance math."""
    prices = dict(prices_today)
    for sym, lot in account.holdings.items():
        if lot.qty > 0 and sym not in prices:
            mid = benchmark_board.asof(day, sym)
            if mid is not None:
                prices[sym] = mid
    return prices


def _rebalance_one_asset(
    account: Account,
    day: date,
    symbol: str,
    target_value_krw: float,
    mid_price_krw: float | None,
) -> None:
    """Trade only ``symbol`` toward ``target_value_krw`` — the partial-
    rebalance primitive the per-asset cadence path relies on. Positions
    in other symbols are left exactly as they were."""
    if mid_price_krw is None or mid_price_krw <= 0:
        return
    lot = account.holdings.get(symbol)
    current_qty = lot.qty if lot is not None else 0
    current_value = current_qty * mid_price_krw
    if current_value > target_value_krw:
        excess = current_value - target_value_krw
        sell_qty = math.floor(excess / mid_price_krw)
        if sell_qty > 0:
            account.sell_qty(day, symbol, mid_price_krw, sell_qty, "rebalance_sell")
    elif current_value < target_value_krw:
        deficit = target_value_krw - current_value
        if deficit > 0:
            account.buy_value(day, symbol, mid_price_krw, deficit, "rebalance_buy")
