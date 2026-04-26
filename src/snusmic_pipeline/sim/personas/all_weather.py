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

    target_weights = {asset.symbol: asset.weight for asset in config.assets}
    daily_closes = {d: benchmark_board.close_on(d) for d in trading_dates}
    contributions = cumulative_contributions(cashflows, trading_dates)
    rebalance_days = _rebalance_days(trading_dates, config.rebalance)
    equity_points: list = []

    for day in trading_dates:
        deposit = cashflow_by_date.get(day, 0.0)
        if deposit > 0:
            account.deposit(day, deposit)
        if deposit > 0 or day in rebalance_days:
            prices_today = daily_closes.get(day, {})
            tradable = {
                sym: w for sym, w in target_weights.items() if sym in prices_today and prices_today[sym] > 0
            }
            if tradable:
                s = sum(tradable.values())
                if s > 0:
                    tradable = {sym: w / s for sym, w in tradable.items()}
                prices = {**prices_today}
                for sym, lot in account.holdings.items():
                    if lot.qty > 0 and sym not in prices:
                        mid = benchmark_board.asof(day, sym)
                        if mid is not None:
                            prices[sym] = mid
                account.rebalance_to_weights(day, tradable, prices)
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
