"""SMIC follower v1 — 1/N true believer.

Buys whatever the report says, equally weighted across active reports.
Sells **only** when the close hits the target price; in the absence of a
target hit, holds (and contributes more on the next deposit, rebalancing
back to 1/N).

Per the user spec: "1/n씩 사고, 현금이 생기면 비중 재조정.
목표가에 매도 후 다시 비중조정." Losers are never sold.
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from ..brokerage import Account
from ..contracts import BrokerageFees, SavingsPlan, SmicFollowerConfig
from ..market import PriceBoard
from ..savings import CashFlowEvent
from .base import (
    PersonaRunOutput,
    build_summary,
    cumulative_contributions,
    record_equity_point,
)


def simulate_smic_follower(
    config: SmicFollowerConfig,
    plan: SavingsPlan,
    fees: BrokerageFees,
    board: PriceBoard,
    reports: pd.DataFrame,
    cashflows: list[CashFlowEvent],
    trading_dates: list[date],
) -> PersonaRunOutput:
    return _simulate_follower(
        persona=config.persona_name,
        label=config.label,
        rebalance_cadence=config.rebalance,
        target_hit_multiplier=config.target_hit_multiplier,
        plan=plan,
        fees=fees,
        board=board,
        reports=reports,
        cashflows=cashflows,
        trading_dates=trading_dates,
        stop_loss_hook=None,
    )


# ---------------------------------------------------------------------------
# Shared with smic_follower_v2 — only the stop-loss hook differs.
# ---------------------------------------------------------------------------


def _simulate_follower(
    *,
    persona: str,
    label: str,
    rebalance_cadence: str,
    target_hit_multiplier: float,
    plan: SavingsPlan,
    fees: BrokerageFees,
    board: PriceBoard,
    reports: pd.DataFrame,
    cashflows: list[CashFlowEvent],
    trading_dates: list[date],
    stop_loss_hook,
) -> PersonaRunOutput:
    """Engine shared by SMIC followers v1 and v2.

    ``stop_loss_hook`` is ``None`` for the true believer; v2 supplies a
    callable taking ``(account, day, board, reports, follower_state)`` that
    sells positions matching its rules and updates state.
    """
    account = Account(persona=persona, fees=fees)
    cashflow_by_date: dict[date, float] = {e.date: e.amount_krw for e in cashflows}

    if not trading_dates:
        return PersonaRunOutput(
            account=account,
            equity_points=[],
            summary=build_summary(persona, label, account, [], cashflows, plan.initial_capital_krw),
        )

    daily_closes = {d: board.close_on(d) for d in trading_dates}
    contributions = cumulative_contributions(cashflows, trading_dates)
    rebalance_days = _rebalance_days(trading_dates, rebalance_cadence)

    pub = pd.to_datetime(reports["publication_date"]).dt.date
    reports = reports.assign(_pub=pub).sort_values("_pub").reset_index(drop=True)

    state = FollowerState()
    equity_points: list = []

    for day in trading_dates:
        state.absorb_reports(reports, day, board)
        deposit_today = cashflow_by_date.get(day, 0.0)
        if deposit_today > 0:
            account.deposit(day, deposit_today)
        if stop_loss_hook is not None:
            stop_loss_hook(account, day, board, reports, state)
        _check_target_hits(account, day, board, target_hit_multiplier, state)
        if deposit_today > 0 or day in rebalance_days:
            _rebalance_to_one_n(account, day, board, daily_closes[day], state)
        equity_points.append(
            record_equity_point(account, persona, day, daily_closes[day], contributions[day], board=board)
        )
    summary = build_summary(persona, label, account, equity_points, cashflows, plan.initial_capital_krw)
    return PersonaRunOutput(account=account, equity_points=equity_points, summary=summary)


class FollowerState:
    """Per-symbol report and target tracking for the follower personas.

    ``open_reports[symbol]`` lists every (report_id, target_price, pub_date)
    that has not been resolved yet. ``stopped_out`` tracks symbols permanently
    excluded by stop-loss rules until a *strictly newer* report arrives.
    """

    def __init__(self) -> None:
        self.open_reports: dict[str, list[tuple[str, float, date]]] = {}
        self.stopped_out: dict[str, date] = {}  # symbol → last stop-out date
        self._absorbed_ids: set[str] = set()

    def absorb_reports(self, reports: pd.DataFrame, day: date, board: PriceBoard) -> None:
        if reports.empty:
            return
        cohort = reports[(reports["_pub"] <= day)]
        for record in cohort.to_dict("records"):
            report_id = str(record.get("report_id") or "")
            if not report_id or report_id in self._absorbed_ids:
                continue
            target = (
                record.get("target_price") or record.get("target_price_krw") or record.get("base_target_krw")
            )
            try:
                target_value = float(target) if target is not None else None
            except (TypeError, ValueError):
                target_value = None
            symbol = str(record["symbol"])
            close = board.asof(day, symbol)
            if target_value is None or target_value <= 0 or (close is not None and target_value <= close):
                self._absorbed_ids.add(report_id)
                continue
            pub_date = record["_pub"]
            # If a previous stop-out was earlier than this report's publication,
            # the new report restores eligibility.
            stopped_when = self.stopped_out.get(symbol)
            if stopped_when is not None and pub_date > stopped_when:
                self.stopped_out.pop(symbol, None)
            self.open_reports.setdefault(symbol, []).append((report_id, target_value, pub_date))
            self._absorbed_ids.add(report_id)

    def active_symbols(self) -> list[str]:
        return sorted(
            sym for sym, items in self.open_reports.items() if items and sym not in self.stopped_out
        )

    def aggregate_target(self, symbol: str) -> float | None:
        items = self.open_reports.get(symbol)
        if not items:
            return None
        return max(t for _, t, _ in items)

    def earliest_publication(self, symbol: str) -> date | None:
        items = self.open_reports.get(symbol)
        if not items:
            return None
        return min(p for _, _, p in items)

    def close_reports(self, symbol: str) -> None:
        self.open_reports.pop(symbol, None)


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
    raise ValueError(f"unknown follower cadence: {cadence}")


def _check_target_hits(
    account: Account,
    day: date,
    board: PriceBoard,
    multiplier: float,
    state: FollowerState,
) -> None:
    for symbol in list(account.holdings):
        lot = account.holdings[symbol]
        if lot.qty <= 0:
            continue
        target = state.aggregate_target(symbol)
        if target is None:
            continue
        close = board.asof(day, symbol)
        if close is None:
            continue
        if close >= target * multiplier:
            account.sell_all(day, symbol, close, "target_hit")
            state.close_reports(symbol)


def _rebalance_to_one_n(
    account: Account,
    day: date,
    board: PriceBoard,
    prices_today: dict[str, float],
    state: FollowerState,
) -> None:
    """Allocate the entire book equally across currently-active reports.

    True 1/N: every symbol the follower would still buy gets the same
    target weight. Symbols held as legacy positions but no longer active
    (e.g. only the v2 persona stops them out) are NOT rebalanced — they
    keep their share count until a target hit or stop-loss closes them
    out separately.
    """
    active = [s for s in state.active_symbols() if s in prices_today and prices_today[s] > 0]
    if not active:
        return
    n = len(active)
    weights = {sym: 1.0 / n for sym in active}
    # Build the price view used by the brokerage. Include held symbols too so
    # rebalance_to_weights knows their current value when computing equity.
    prices = dict(prices_today)
    for sym, lot in account.holdings.items():
        if lot.qty > 0 and sym not in prices:
            mid = board.asof(day, sym)
            if mid is not None:
                prices[sym] = mid
    account.rebalance_to_weights(day, weights, prices)
