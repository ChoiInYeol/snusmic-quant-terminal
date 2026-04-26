"""Prophet (full-lookahead oracle).

The prophet sees the entire future price path and, on every cash event,
puts the new money into the report whose realised peak return after today
is the highest. If that top realised return is dominant (>= ``dominance_threshold``
× the runner-up) it concentrates 100%; otherwise it spreads proportional
to realised returns, capped per name.

Each opened position is scheduled to exit at its realised peak date — the
prophet never holds past a peak. This is the ceiling, not an executable
strategy.
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from ..brokerage import Account
from ..contracts import BrokerageFees, ProphetConfig, SavingsPlan
from ..market import PriceBoard
from ..savings import CashFlowEvent
from .base import (
    PersonaRunOutput,
    build_summary,
    cumulative_contributions,
    record_equity_point,
)


def simulate_prophet(
    config: ProphetConfig,
    plan: SavingsPlan,
    fees: BrokerageFees,
    board: PriceBoard,
    reports: pd.DataFrame,
    cashflows: list[CashFlowEvent],
    trading_dates: list[date],
) -> PersonaRunOutput:
    persona = config.persona_name
    account = Account(persona=persona, fees=fees)
    cashflow_by_date: dict[date, float] = {e.date: e.amount_krw for e in cashflows}

    if not trading_dates or not cashflows:
        summary = build_summary(persona, config.label, account, [], cashflows, plan.initial_capital_krw)
        return PersonaRunOutput(account=account, equity_points=[], summary=summary)

    end_date = trading_dates[-1]
    pub_dates = pd.to_datetime(reports["publication_date"]).dt.date
    reports = reports.assign(_pub=pub_dates)
    daily_closes: dict[date, dict[str, float]] = {d: board.close_on(d) for d in trading_dates}
    scheduled_sells: dict[date, list[str]] = {}
    contributions = cumulative_contributions(cashflows, trading_dates)
    equity_points: list = []

    for day in trading_dates:
        deposit = cashflow_by_date.get(day, 0.0)
        if deposit > 0:
            account.deposit(day, deposit)
            _allocate_prophet(account, config, board, reports, day, end_date, scheduled_sells)
        for sym in scheduled_sells.pop(day, []):
            mid = board.asof(day, sym)
            if mid is not None:
                account.sell_all(day, sym, mid, "target_hit")
        equity_points.append(
            record_equity_point(account, persona, day, daily_closes[day], contributions[day], board=board)
        )

    summary = build_summary(
        persona, config.label, account, equity_points, cashflows, plan.initial_capital_krw
    )
    return PersonaRunOutput(account=account, equity_points=equity_points, summary=summary)


def _allocate_prophet(
    account: Account,
    config: ProphetConfig,
    board: PriceBoard,
    reports: pd.DataFrame,
    day: date,
    end_date: date,
    scheduled_sells: dict[date, list[str]],
) -> None:
    """Buy with all available cash on ``day`` according to look-ahead returns.

    The candidate set is every report whose publication is on or before
    ``day`` and whose symbol has a close on ``day``."""
    active = reports[reports["_pub"] <= day]
    if active.empty:
        return
    candidates: list[tuple[str, float, date]] = []
    seen: set[str] = set()
    for record in active.to_dict("records"):
        symbol = str(record["symbol"])
        if symbol in seen:
            continue
        peak_return = board.peak_return_after(day, end_date, symbol)
        peak_day = board.peak_date_after(day, end_date, symbol)
        if peak_return is None or peak_day is None or peak_return <= 0:
            continue
        seen.add(symbol)
        candidates.append((symbol, peak_return, peak_day))
    if not candidates:
        return
    candidates.sort(key=lambda x: x[1], reverse=True)
    top_symbol, top_return, top_peak = candidates[0]
    runner_up_return = candidates[1][1] if len(candidates) > 1 else 0.0

    if runner_up_return <= 0 or top_return >= runner_up_return * config.dominance_threshold:
        # Concentrate 100% on the top name.
        mid = board.asof(day, top_symbol)
        if mid is None:
            return
        report_id = _report_id_for(reports, top_symbol)
        account.buy_value(
            day,
            top_symbol,
            mid,
            account.cash_krw,
            "deposit_buy",
            report_id=report_id,
        )
        scheduled_sells.setdefault(top_peak, []).append(top_symbol)
        return

    # Otherwise diversify proportional to realised return, capped per name.
    weights = _proportional_weights([c[1] for c in candidates], config.max_weight)
    cash = account.cash_krw
    for (symbol, _ret, peak_day), weight in zip(candidates, weights, strict=True):
        if weight <= 0:
            continue
        mid = board.asof(day, symbol)
        if mid is None:
            continue
        target_value = cash * weight
        report_id = _report_id_for(reports, symbol)
        account.buy_value(day, symbol, mid, target_value, "deposit_buy", report_id=report_id)
        scheduled_sells.setdefault(peak_day, []).append(symbol)


def _proportional_weights(returns: list[float], cap: float) -> list[float]:
    """Long-only weights proportional to ``returns``, capped at ``cap`` per name.

    Iterative water-filling: assign proportional weights, clamp to ``cap``,
    redistribute the excess until no weight exceeds the cap."""
    n = len(returns)
    if n == 0:
        return []
    if cap >= 1.0 - 1e-9:
        total = sum(returns)
        if total <= 0:
            return [1.0 / n] * n
        return [r / total for r in returns]
    weights = [0.0] * n
    free = list(range(n))
    remaining = 1.0
    for _ in range(n):
        free_returns = [returns[i] for i in free]
        s = sum(free_returns)
        if s <= 0:
            for i in free:
                weights[i] = remaining / len(free)
            break
        proposed = {i: remaining * returns[i] / s for i in free}
        clipped = [i for i in free if proposed[i] > cap]
        if not clipped:
            for i in free:
                weights[i] = proposed[i]
            break
        for i in clipped:
            weights[i] = cap
            remaining -= cap
            free.remove(i)
        if not free or remaining <= 1e-9:
            break
    return weights


def _report_id_for(reports: pd.DataFrame, symbol: str) -> str | None:
    matches = reports[reports["symbol"].astype(str) == symbol]
    if matches.empty:
        return None
    return str(matches.iloc[0].get("report_id", "") or None)
