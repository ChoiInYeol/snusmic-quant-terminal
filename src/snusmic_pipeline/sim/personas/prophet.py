"""Prophet (rolling-interval lookahead oracle).

Strict upper bound on the SMIC report universe. At every rebalance date
the prophet looks at the **next rebalance interval** (one month by
default), computes each candidate symbol's realised return over that
interval, and reallocates the entire book to the top performer(s).

This is intentionally different from a "buy at start, hold to peak"
prophet. With monthly rebalances:

* if symbol A is the best performer in month 1, the prophet holds A
  through month 1 and then re-checks for month 2,
* if A also wins month 2 the rebalance is a no-op,
* if a different symbol B wins month 2, the prophet swaps the entire
  book into B,

so capital compounds month-over-month rather than sitting idle after a
single lifetime-peak exit. This makes the prophet a strict superset of
the weak-prophet (whose 6-month max-Sharpe portfolio cannot beat
foreseeable monthly winners with concentration ≤ ``max_weight``).

``dominance_threshold`` and ``max_weight`` still control concentration:
if the top symbol's interval return ≥ ``dominance_threshold`` ×
runner-up, weight 100%; otherwise spread proportional to realised
return capped at ``max_weight`` per name.
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

    pub_dates = pd.to_datetime(reports["publication_date"]).dt.date
    reports = reports.assign(_pub=pub_dates)
    daily_closes: dict[date, dict[str, float]] = {d: board.close_on(d) for d in trading_dates}
    rebalance_days = _rebalance_days(trading_dates, config.rebalance)
    next_rebalance = _next_rebalance_lookup(trading_dates, rebalance_days)
    contributions = cumulative_contributions(cashflows, trading_dates)
    equity_points: list = []

    for day in trading_dates:
        deposit = cashflow_by_date.get(day, 0.0)
        if deposit > 0:
            account.deposit(day, deposit)
        if day in rebalance_days:
            interval_end = next_rebalance.get(day, trading_dates[-1])
            weights = _interval_winner_weights(config, board, reports, day, interval_end)
            prices = dict(daily_closes[day])
            for sym, lot in account.holdings.items():
                if lot.qty > 0 and sym not in prices:
                    mid = board.asof(day, sym)
                    if mid is not None:
                        prices[sym] = mid
            tradable = {s: w for s, w in weights.items() if s in prices and prices[s] > 0}
            if tradable:
                s = sum(tradable.values())
                if s > 0:
                    tradable = {sym: w / s for sym, w in tradable.items()}
            # Always rebalance — empty ``tradable`` means "no winners this
            # interval, sit in cash" and rebalance_to_weights will sell every
            # currently-held symbol to bring its weight to zero.
            account.rebalance_to_weights(day, tradable, prices)
        equity_points.append(
            record_equity_point(account, persona, day, daily_closes[day], contributions[day], board=board)
        )

    summary = build_summary(
        persona, config.label, account, equity_points, cashflows, plan.initial_capital_krw
    )
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
    raise ValueError(f"unknown prophet cadence: {cadence}")


def _next_rebalance_lookup(trading_dates: list[date], rebalance_days: set[date]) -> dict[date, date]:
    """``day → the next rebalance day strictly after day``. Last interval ends at ``trading_dates[-1]``."""
    sorted_rebalances = sorted(rebalance_days)
    out: dict[date, date] = {}
    for rebalance in sorted_rebalances:
        next_one = next((r for r in sorted_rebalances if r > rebalance), trading_dates[-1])
        out[rebalance] = next_one
    return out


def _interval_winner_weights(
    config: ProphetConfig,
    board: PriceBoard,
    reports: pd.DataFrame,
    day: date,
    interval_end: date,
) -> dict[str, float]:
    """Pick target weights for the upcoming rebalance interval.

    For every active SMIC report symbol with a close on ``day``, compute
    the realised cumulative return over ``(day, interval_end]`` and treat
    it as the prophet's score. Return a long-only weight dict that sums
    to 1.0 (or empty when the universe is empty).
    """
    active = reports[reports["_pub"] <= day]
    if active.empty or interval_end <= day:
        return {}
    candidates: list[tuple[str, float]] = []
    seen: set[str] = set()
    for record in active.to_dict("records"):
        symbol = str(record["symbol"])
        if symbol in seen:
            continue
        seen.add(symbol)
        ret = board.cumulative_return(day, interval_end, symbol)
        if ret is None or ret <= 0:
            continue
        candidates.append((symbol, ret))
    if not candidates:
        return {}
    candidates.sort(key=lambda x: x[1], reverse=True)
    top_symbol, top_return = candidates[0]
    runner_up_return = candidates[1][1] if len(candidates) > 1 else 0.0

    if runner_up_return <= 0 or top_return >= runner_up_return * config.dominance_threshold:
        return {top_symbol: 1.0}

    weights = _proportional_weights([c[1] for c in candidates], config.max_weight)
    return {symbol: w for (symbol, _ret), w in zip(candidates, weights, strict=True) if w > 1e-4}


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
