"""All-Weather benchmark.

Constant-weight DCA across the basket declared in
:class:`AllWeatherConfig`. On every cash event the deposit is rebalanced
back to the configured weights; an optional ``rebalance`` cadence forces
a rebalance on every month-start (or quarter / year start) even when no
deposit lands that day.

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
    DividendIndex,
    PersonaRunOutput,
    build_summary,
    credit_dividends_due,
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
    *,
    dividends_by_date: DividendIndex | None = None,
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

    contributions = cumulative_contributions(cashflows, trading_dates)
    rebalance_days = _rebalance_days(trading_dates, config.rebalance)
    equity_points: list = []
    pending_rebalance = False

    for day in trading_dates:
        credit_dividends_due(account, day, dividends_by_date)
        deposit = cashflow_by_date.get(day, 0.0)
        if deposit > 0:
            account.deposit(day, deposit)
            pending_rebalance = True
        if day in rebalance_days:
            pending_rebalance = True
        prices_today = daily_closes.get(day, {})
        # Only execute when EVERY surviving target market has a close today.
        # If a deposit or cadence trigger landed on a partial-market day
        # (typically a US holiday that is also a Korean trading day), the
        # rebalance is deferred to the next fully-open trading date — the
        # cash sits as cash until then. This prevents the historical bug
        # where the basket flipped to 100% KOSPI on those dates.
        if pending_rebalance and target_symbols and target_symbols.issubset(prices_today):
            prices = {**prices_today}
            for sym, lot in account.holdings.items():
                if lot.qty > 0 and sym not in prices:
                    mid = benchmark_board.asof(day, sym)
                    if mid is not None:
                        prices[sym] = mid
            account.rebalance_to_weights(day, target_weights, prices)
            pending_rebalance = False
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


def _rebalance_days(trading_dates: list[date], cadence: str) -> set[date]:
    if cadence == "monthly":
        seen: dict[tuple[int, int], date] = {}
        for d in trading_dates:
            seen.setdefault((d.year, d.month), d)
        return set(seen.values())
    if cadence == "quarterly":
        seen_q: dict[tuple[int, int], date] = {}
        for d in trading_dates:
            seen_q.setdefault((d.year, (d.month - 1) // 3), d)
        return set(seen_q.values())
    if cadence == "yearly":
        seen_y: dict[int, date] = {}
        for d in trading_dates:
            seen_y.setdefault(d.year, d)
        return set(seen_y.values())
    raise ValueError(f"unknown all-weather cadence: {cadence}")
