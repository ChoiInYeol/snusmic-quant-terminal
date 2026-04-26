"""Savings escalation schedule.

Pure functions only — given a :class:`SavingsPlan` and an ordered list of
trading dates, return the deposit cash-flow stream. The runner consumes the
stream as the input to every persona's brokerage account, so the escalation
math lives in exactly one place.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

from .contracts import SavingsPlan


@dataclass(frozen=True)
class CashFlowEvent:
    """One scheduled deposit. ``kind`` records why it landed."""

    date: date
    amount_krw: float
    kind: str  # "initial" | "monthly"


def first_trading_day_per_month(trading_dates: Iterable[date]) -> list[date]:
    """Pick the earliest trading date for each calendar month.

    Pre-condition: ``trading_dates`` is sorted ascending. The output preserves
    that order and contains exactly one entry per (year, month) seen.
    """
    seen: dict[tuple[int, int], date] = {}
    for d in trading_dates:
        key = (d.year, d.month)
        if key not in seen:
            seen[key] = d
    return [seen[k] for k in sorted(seen)]


def contribution_amount(
    deposit_index: int,
    plan: SavingsPlan,
) -> float:
    """Monthly contribution at deposit index ``i`` (0 = first monthly deposit).

    The escalation increments ``escalation_step_krw`` once every
    ``escalation_period_years`` years from the start. Beyond
    ``max_escalations`` ticks the amount is held flat.

    Example: defaults give 1.0M for months 0..23 (years 0-1), 1.5M for months
    24..47 (years 2-3), and so on, capped at ``1.0M + 10×0.5M = 6.0M``.
    """
    if deposit_index < 0:
        raise ValueError(f"deposit_index must be ≥ 0; got {deposit_index}")
    period_months = plan.escalation_period_years * 12
    step_count = min(deposit_index // period_months, plan.max_escalations)
    return plan.monthly_contribution_krw + step_count * plan.escalation_step_krw


def build_cash_flow_schedule(
    trading_dates: Iterable[date],
    plan: SavingsPlan,
) -> list[CashFlowEvent]:
    """Materialise the full deposit stream over ``trading_dates``.

    Behavior:

    1. Day 0 (the first trading date) gets ``initial_capital_krw`` of kind
       ``"initial"``.
    2. Every later month's first trading day gets one ``"monthly"`` deposit
       sized by :func:`contribution_amount` indexed against the start month.

    The returned list is in chronological order. An empty input yields an
    empty schedule.
    """
    sorted_dates = sorted(set(trading_dates))
    if not sorted_dates:
        return []

    monthly_firsts = first_trading_day_per_month(sorted_dates)
    if not monthly_firsts:
        return []

    events: list[CashFlowEvent] = []
    start_month = (monthly_firsts[0].year, monthly_firsts[0].month)
    if plan.initial_capital_krw > 0:
        events.append(
            CashFlowEvent(date=sorted_dates[0], amount_krw=plan.initial_capital_krw, kind="initial")
        )

    # Skip the first month's monthly deposit because the initial capital
    # already covers month 0. Months 1..N each contribute one deposit using
    # the index ``deposit_index = month - 1``.
    for first_day in monthly_firsts[1:]:
        offset = (first_day.year - start_month[0]) * 12 + (first_day.month - start_month[1])
        deposit_index = offset - 1  # month 1's first deposit is index 0.
        amount = contribution_amount(deposit_index, plan)
        if amount > 0:
            events.append(CashFlowEvent(date=first_day, amount_krw=amount, kind="monthly"))
    return events


def total_contributed(events: Iterable[CashFlowEvent]) -> float:
    """Sum of all deposit amounts (initial + monthly)."""
    return float(sum(event.amount_krw for event in events))
