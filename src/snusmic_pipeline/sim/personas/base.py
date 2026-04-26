"""Common helpers shared by every persona implementation.

The job here is to keep the persona modules narrow: each one declares what
to buy and when to sell, while ledger bookkeeping, deposit handling, IRR /
drawdown statistics, and equity-point construction live in this single
shared place.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date

import numpy as np

from ..brokerage import Account
from ..contracts import EquityPoint, PersonaSummary, Trade
from ..savings import CashFlowEvent


@dataclass
class PersonaRunOutput:
    """One persona's full simulation product."""

    account: Account
    equity_points: list[EquityPoint]
    summary: PersonaSummary


def deposits_indexed_by_date(events: list[CashFlowEvent]) -> dict[date, float]:
    """Collapse cash-flow events into ``date → amount`` (sums duplicates)."""
    out: dict[date, float] = {}
    for event in events:
        out[event.date] = out.get(event.date, 0.0) + event.amount_krw
    return out


def record_equity_point(
    account: Account,
    persona: str,
    day: date,
    prices_today: dict[str, float],
    contributed_today: float,
) -> EquityPoint:
    """Snapshot the account RIGHT NOW.

    Must be called inside the persona's daily loop, after that day's deposit
    and trading have already executed — the snapshot reads the live account
    state, so calling it after the loop produces a single bogus end-state
    repeated across all dates (this was the original bug).

    ``prices_today`` should be the close map for ``day``; symbols held
    without a close today fall back to weighted-average cost so a halted
    name doesn't appear as a synthetic loss.
    """
    holdings_value = sum(
        lot.qty * prices_today.get(sym, lot.avg_cost_krw)
        for sym, lot in account.holdings.items()
        if lot.qty > 0
    )
    equity = account.cash_krw + holdings_value
    return EquityPoint(
        persona=persona,
        date=day,
        cash_krw=account.cash_krw,
        holdings_value_krw=holdings_value,
        equity_krw=equity,
        contributed_capital_krw=contributed_today,
        net_profit_krw=equity - contributed_today,
        open_positions=sum(1 for lot in account.holdings.values() if lot.qty > 0),
    )


def cumulative_contributions(events: list[CashFlowEvent], trading_dates: list[date]) -> dict[date, float]:
    """``date → cumulative deposited KRW up to and including that date``."""
    out: dict[date, float] = {}
    schedule = sorted(events, key=lambda e: e.date)
    cursor = 0
    running = 0.0
    for d in trading_dates:
        while cursor < len(schedule) and schedule[cursor].date <= d:
            running += schedule[cursor].amount_krw
            cursor += 1
        out[d] = running
    return out


# ---------------------------------------------------------------------------
# Performance statistics.
# ---------------------------------------------------------------------------


def money_weighted_return(events: list[CashFlowEvent], final_equity: float, end_date: date) -> float:
    """Internal rate of return on the cash-flow stream.

    Cash flows are negative (deposits leaving the user's wallet) on each
    deposit date and the single positive flow is ``final_equity`` at
    ``end_date``. Solved via a Newton-bounded bisection on annualised IRR.
    """
    if not events or final_equity <= 0:
        return 0.0
    cashflows: list[tuple[date, float]] = [(e.date, -e.amount_krw) for e in events]
    cashflows.append((end_date, float(final_equity)))
    cashflows.sort(key=lambda x: x[0])
    base = cashflows[0][0]

    def npv(rate: float) -> float:
        total = 0.0
        for d, amt in cashflows:
            years = max(0.0, (d - base).days / 365.25)
            total += amt / ((1.0 + rate) ** years)
        return total

    # Bisection between -0.99 and +5.00 (annualised). Most retail outcomes
    # land safely inside that bracket.
    low, high = -0.99, 5.0
    f_low, f_high = npv(low), npv(high)
    if f_low * f_high > 0:
        # No sign change — return a coarse approximation from total cash flow ratio.
        deposited = sum(-amt for _, amt in cashflows if amt < 0)
        if deposited <= 0:
            return 0.0
        years = max(1 / 365.25, (cashflows[-1][0] - cashflows[0][0]).days / 365.25)
        return (final_equity / deposited) ** (1 / years) - 1.0
    for _ in range(100):
        mid = 0.5 * (low + high)
        f_mid = npv(mid)
        if abs(f_mid) < 1e-2:
            return mid
        if f_low * f_mid < 0:
            high, f_high = mid, f_mid
        else:
            low, f_low = mid, f_mid
    return 0.5 * (low + high)


def time_weighted_return(equity_points: list[EquityPoint], events: list[CashFlowEvent]) -> float | None:
    """Geometric link of daily returns net of cash flows.

    Standard Modified Dietz approximation per day:
    ``r_d = (E_d − E_{d-1} − CF_d) / (E_{d-1} + CF_d)``.
    """
    if len(equity_points) < 2:
        return None
    deposits = deposits_indexed_by_date(events)
    log_growth = 0.0
    used = 0
    for prev, curr in zip(equity_points[:-1], equity_points[1:], strict=True):
        cf = deposits.get(curr.date, 0.0)
        denom = prev.equity_krw + cf
        if denom <= 0:
            continue
        ratio = (curr.equity_krw - cf) / prev.equity_krw if prev.equity_krw > 0 else None
        if ratio is None or ratio <= 0:
            continue
        log_growth += math.log(ratio)
        used += 1
    if used == 0:
        return None
    return math.exp(log_growth) - 1.0


def cagr(equity_points: list[EquityPoint], total_contributed: float) -> float | None:
    if len(equity_points) < 2 or total_contributed <= 0:
        return None
    final_equity = equity_points[-1].equity_krw
    if final_equity <= 0:
        return -1.0
    days = (equity_points[-1].date - equity_points[0].date).days
    if days <= 0:
        return None
    years = days / 365.25
    return (final_equity / total_contributed) ** (1 / years) - 1.0


def max_drawdown(equity_points: list[EquityPoint]) -> float:
    if not equity_points:
        return 0.0
    series = np.array([p.equity_krw for p in equity_points], dtype=float)
    if series.size < 2:
        return 0.0
    peaks = np.maximum.accumulate(series)
    drawdowns = (series - peaks) / np.where(peaks > 0, peaks, 1.0)
    return float(abs(drawdowns.min()))


def build_summary(
    persona: str,
    label: str,
    account: Account,
    equity_points: list[EquityPoint],
    events: list[CashFlowEvent],
    initial_capital_krw: float,
) -> PersonaSummary:
    final = equity_points[-1] if equity_points else None
    final_equity = final.equity_krw if final else account.cash_krw
    final_cash = final.cash_krw if final else account.cash_krw
    final_holdings = final.holdings_value_krw if final else 0.0
    total_contributed = sum(e.amount_krw for e in events)
    end_day = final.date if final else (events[-1].date if events else date.today())
    return PersonaSummary(
        persona=persona,
        label=label,
        initial_capital_krw=initial_capital_krw,
        total_contributed_krw=total_contributed,
        final_equity_krw=final_equity,
        final_cash_krw=final_cash,
        final_holdings_value_krw=final_holdings,
        net_profit_krw=final_equity - total_contributed,
        money_weighted_return=money_weighted_return(events, final_equity, end_day),
        time_weighted_return=time_weighted_return(equity_points, events),
        cagr=cagr(equity_points, total_contributed),
        max_drawdown=max_drawdown(equity_points),
        realized_pnl_krw=account.realized_pnl_krw,
        trade_count=len(account.trades),
        open_positions=account.open_position_count(),
    )


# ---------------------------------------------------------------------------
# Trade conveniences re-exported (so persona modules don't need ..contracts).
# ---------------------------------------------------------------------------

__all__ = [
    "PersonaRunOutput",
    "Trade",
    "build_summary",
    "cumulative_contributions",
    "deposits_indexed_by_date",
    "record_equity_point",
]
