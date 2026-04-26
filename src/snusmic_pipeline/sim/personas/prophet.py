"""Prophet — full-lookahead max-Sharpe oracle.

Same long-only max-Sharpe optimisation as Weak Prophet, but the
realised-return window spans the entire remaining simulation horizon
instead of the next ``lookahead_months``. Concentration is bounded by
``max_weight`` so the prophet picks a diversified basket of names that
will perform well rather than blowing all capital into a single illiquid
winner. This makes the upper bound large but tractable — no
158-billion-share fills.
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
from .sharpe import solve_max_sharpe_weights


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
            weights = _full_horizon_weights(config, board, reports, day, end_date)
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


def _full_horizon_weights(
    config: ProphetConfig,
    board: PriceBoard,
    reports: pd.DataFrame,
    day: date,
    end_date: date,
) -> dict[str, float]:
    """Solve max-Sharpe over realised returns across ``[day, end_date]``."""
    if end_date <= day:
        return {}
    active = reports[reports["_pub"] <= day]
    if active.empty:
        return {}
    candidates = sorted({str(s) for s in active["symbol"].dropna()})
    rets = board.returns_window(day, end_date, candidates)
    return solve_max_sharpe_weights(
        rets,
        risk_free_rate=config.risk_free_rate,
        max_weight=config.max_weight,
        min_history_days=config.min_history_days,
    )
