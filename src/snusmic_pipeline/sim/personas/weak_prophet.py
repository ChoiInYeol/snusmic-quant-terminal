"""Weak prophet — 6-month forward look-ahead, max-Sharpe portfolio.

The persona "knows" only the next ``lookahead_months`` of returns. At each
rebalance date it computes realised daily returns over that window for the
candidate universe, then solves a long-only max-Sharpe problem (sum to 1,
optionally capped per name) and rebalances the book.

Solved with ``scipy.optimize.minimize`` (SLSQP). When the optimiser fails
or the universe is empty we fall back to equal-weight on the survivors.
"""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from ..brokerage import Account
from ..contracts import BrokerageFees, SavingsPlan, WeakProphetConfig
from ..market import PriceBoard
from ..savings import CashFlowEvent
from .base import (
    PersonaRunOutput,
    build_summary,
    cumulative_contributions,
    record_equity_point,
)


def simulate_weak_prophet(
    config: WeakProphetConfig,
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

    if not trading_dates:
        return _empty_output(persona, config.label, account, cashflows, plan.initial_capital_krw)

    daily_closes = {d: board.close_on(d) for d in trading_dates}
    rebalance_days = _rebalance_days(trading_dates, config.rebalance)
    contributions = cumulative_contributions(cashflows, trading_dates)
    pub_dates = pd.to_datetime(reports["publication_date"]).dt.date
    reports = reports.assign(_pub=pub_dates)
    equity_points: list = []

    for day in trading_dates:
        deposit = cashflow_by_date.get(day, 0.0)
        if deposit > 0:
            account.deposit(day, deposit)
        if day in rebalance_days:
            weights = _solve_target_weights(
                config=config, board=board, reports=reports, day=day, end_date=trading_dates[-1]
            )
            if weights:
                prices = daily_closes[day]
                tradable = {sym: w for sym, w in weights.items() if sym in prices and prices[sym] > 0}
                if tradable:
                    s = sum(tradable.values())
                    if s > 0:
                        tradable = {sym: w / s for sym, w in tradable.items()}
                    account.rebalance_to_weights(day, tradable, prices)
        equity_points.append(
            record_equity_point(account, persona, day, daily_closes[day], contributions[day])
        )
    summary = build_summary(
        persona, config.label, account, equity_points, cashflows, plan.initial_capital_krw
    )
    return PersonaRunOutput(account=account, equity_points=equity_points, summary=summary)


def _rebalance_days(trading_dates: list[date], cadence: str) -> set[date]:
    if not trading_dates:
        return set()
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
    raise ValueError(f"unknown weak-prophet cadence: {cadence}")


def _solve_target_weights(
    *,
    config: WeakProphetConfig,
    board: PriceBoard,
    reports: pd.DataFrame,
    day: date,
    end_date: date,
) -> dict[str, float]:
    horizon_end = min(day + timedelta(days=int(config.lookahead_months * 30.5)), end_date)
    if horizon_end <= day:
        return {}
    active = reports[reports["_pub"] <= day]
    if active.empty:
        return {}
    candidates = sorted({str(s) for s in active["symbol"].dropna()})
    rets = board.returns_window(day, horizon_end, candidates)
    if rets.empty:
        return {}
    rets = rets.dropna(axis=1, thresh=config.min_history_days)
    if rets.shape[1] == 0:
        return {}
    rets = rets.fillna(0.0)
    mu = rets.mean().to_numpy() * 252.0
    cov = rets.cov().to_numpy() * 252.0
    n = mu.size
    if n == 1:
        return {str(rets.columns[0]): 1.0}
    cap = float(min(1.0, max(config.max_weight, 1.0 / n)))

    def neg_sharpe(weights: np.ndarray) -> float:
        port_return = float(np.dot(weights, mu))
        port_var = float(np.dot(weights, cov @ weights))
        if port_var <= 1e-12:
            return -port_return
        port_vol = float(np.sqrt(port_var))
        return -(port_return - config.risk_free_rate) / port_vol

    constraints = ({"type": "eq", "fun": lambda w: float(np.sum(w) - 1.0)},)
    bounds = [(0.0, cap)] * n
    x0 = np.full(n, 1.0 / n)
    try:
        result = minimize(
            neg_sharpe,
            x0,
            method="SLSQP",
            bounds=bounds,
            constraints=constraints,
            options={"ftol": 1e-9, "maxiter": 200, "disp": False},
        )
        if not result.success:
            return _equal_weights(rets.columns)
        weights = np.clip(result.x, 0.0, cap)
        s = weights.sum()
        if s <= 0:
            return _equal_weights(rets.columns)
        weights = weights / s
    except Exception:
        return _equal_weights(rets.columns)
    return {str(sym): float(w) for sym, w in zip(rets.columns, weights, strict=True) if w > 1e-4}


def _equal_weights(columns) -> dict[str, float]:
    n = len(columns)
    if n == 0:
        return {}
    return {str(c): 1.0 / n for c in columns}


def _empty_output(persona, label, account, cashflows, initial_capital):
    summary = build_summary(persona, label, account, [], cashflows, initial_capital)
    return PersonaRunOutput(account=account, equity_points=[], summary=summary)
