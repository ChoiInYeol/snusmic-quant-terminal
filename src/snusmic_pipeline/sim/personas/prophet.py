"""Prophet — SMIC-constrained target-hit oracle.

The prophet is restricted to the SMIC report universe (no free-form
stock picking) but knows ahead of time which reports will actually
have their target hit. At each monthly rebalance:

1. Find every report published on or before today whose target
   ``target × target_hit_multiplier`` has *not* been reached by
   today's close.
2. Keep only the ones whose price will reach the (multiplied) target
   *within the next* ``lookahead_months``.
3. Equal-weight that basket. Empty → sit in cash.

This is the "if SMIC's research is decent, how good could you have
been with perfect entry-timing knowledge?" question. Naturally
bounded — the basket is at most the count of open SMIC reports, so
deployable AUM tracks universe depth instead of compounding to
quadrillions of KRW.
"""

from __future__ import annotations

from datetime import date, timedelta

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
    contributions = cumulative_contributions(cashflows, trading_dates)
    end_date = trading_dates[-1]
    equity_points: list = []

    for day in trading_dates:
        deposit = cashflow_by_date.get(day, 0.0)
        if deposit > 0:
            account.deposit(day, deposit)
        if day in rebalance_days:
            weights = _will_hit_target_basket(config, board, reports, day, end_date)
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


def _will_hit_target_basket(
    config: ProphetConfig,
    board: PriceBoard,
    reports: pd.DataFrame,
    day: date,
    end_date: date,
) -> dict[str, float]:
    """Equal-weight basket of SMIC reports whose target hits in the next window."""
    horizon_end = min(day + timedelta(days=int(config.lookahead_months * 30.5)), end_date)
    if horizon_end <= day:
        return {}
    active = reports[reports["_pub"] <= day]
    if active.empty:
        return {}
    eligible: list[str] = []
    seen: set[str] = set()
    multiplier = float(config.target_hit_multiplier)
    for record in active.to_dict("records"):
        symbol = str(record["symbol"])
        if symbol in seen:
            continue
        target = _target_price_krw(record)
        if target is None or target <= 0:
            continue
        threshold = target * multiplier
        # Skip if target was already crossed between publication and today —
        # the prophet treats it as already-resolved.
        if _close_reaches(board, record["_pub"], day, symbol, threshold):
            seen.add(symbol)
            continue
        # Eligible iff close hits threshold within the upcoming window.
        if _close_reaches(board, day, horizon_end, symbol, threshold):
            seen.add(symbol)
            eligible.append(symbol)
    if not eligible:
        return {}
    n = len(eligible)
    return {sym: 1.0 / n for sym in eligible}


def _target_price_krw(record: dict) -> float | None:
    for key in ("target_price_krw", "target_price", "base_target_krw"):
        value = record.get(key)
        if value is None or value == "":
            continue
        try:
            v = float(value)
        except (TypeError, ValueError):
            continue
        if v > 0 and v == v:  # exclude NaN
            return v
    return None


def _close_reaches(board: PriceBoard, start: date, end: date, symbol: str, threshold: float) -> bool:
    """True iff any close in ``(start, end]`` hits ``threshold`` for ``symbol``."""
    if board.is_empty or symbol not in board.close.columns:
        return False
    if end <= start:
        return False
    col = board.close[symbol]
    ts_start = pd.Timestamp(start)
    ts_end = pd.Timestamp(end)
    window = col.loc[(col.index > ts_start) & (col.index <= ts_end)].dropna()
    if window.empty:
        return False
    return bool((window >= threshold).any())
