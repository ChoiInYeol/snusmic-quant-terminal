"""SMIC follower v2 — same as v1 plus three stop-loss escape hatches.

Rules (all evaluated **before** the daily target-hit check, so a stop-loss
exits a paper-loss name even if it happens to also touch the target on
the same day):

* ``time_loss``: held ≥ ``time_loss_days`` AND unrealized return < 0.
* ``averaged_down_stop``: more than one buy fill AND unrealized return
  < ``-averaged_down_stop_pct``.
* ``report_age_stop``: ≥ ``report_age_stop_days`` since the earliest
  open report on this symbol AND the target has not been hit.

Once stopped out, the symbol is excluded from the active set until a
*strictly newer* report is published — the FollowerState absorbs that
upgrade automatically in the shared engine.
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from ..brokerage import Account
from ..contracts import BrokerageFees, SavingsPlan, SmicFollowerV2Config
from ..market import PriceBoard
from ..savings import CashFlowEvent
from .base import PersonaRunOutput
from .smic_follower import FollowerState, _simulate_follower


def simulate_smic_follower_v2(
    config: SmicFollowerV2Config,
    plan: SavingsPlan,
    fees: BrokerageFees,
    board: PriceBoard,
    reports: pd.DataFrame,
    cashflows: list[CashFlowEvent],
    trading_dates: list[date],
) -> PersonaRunOutput:
    def stop_loss_hook(
        account: Account,
        day: date,
        board: PriceBoard,
        _reports: pd.DataFrame,
        state: FollowerState,
    ) -> None:
        for symbol in list(account.holdings):
            lot = account.holdings[symbol]
            if lot.qty <= 0:
                continue
            close = board.asof(day, symbol)
            if close is None:
                continue
            unrealised_return = close / lot.avg_cost_krw - 1.0 if lot.avg_cost_krw > 0 else 0.0
            holding_days = (day - lot.first_buy_date).days if lot.first_buy_date else 0

            # Rule (a): time-based loss exit.
            if holding_days >= config.time_loss_days and unrealised_return < 0:
                account.sell_all(day, symbol, close, "stop_loss_time")
                state.close_reports(symbol)
                state.stopped_out[symbol] = day
                continue

            # Rule (b): averaged-down stop. Only fires when there were multiple
            # buy fills (i.e. the follower added on the way down).
            if lot.buy_count >= 2 and unrealised_return < -float(config.averaged_down_stop_pct):
                account.sell_all(day, symbol, close, "stop_loss_average_down")
                state.close_reports(symbol)
                state.stopped_out[symbol] = day
                continue

            # Rule (c): the report itself is too old without a target hit.
            earliest_pub = state.earliest_publication(symbol)
            if earliest_pub is None:
                continue
            age = (day - earliest_pub).days
            if age >= config.report_age_stop_days:
                account.sell_all(day, symbol, close, "stop_loss_report_age")
                state.close_reports(symbol)
                state.stopped_out[symbol] = day

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
        stop_loss_hook=stop_loss_hook,
    )
