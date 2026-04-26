"""Savings escalation arithmetic."""

from __future__ import annotations

from datetime import date

import pandas as pd

from snusmic_pipeline.sim.contracts import SavingsPlan
from snusmic_pipeline.sim.savings import (
    build_cash_flow_schedule,
    contribution_amount,
    first_trading_day_per_month,
    total_contributed,
)


def _bdates(start: str, end: str) -> list[date]:
    return [d.date() for d in pd.bdate_range(start, end)]


def test_first_trading_day_per_month_picks_earliest():
    days = _bdates("2024-01-01", "2024-03-31")
    firsts = first_trading_day_per_month(days)
    assert firsts == [date(2024, 1, 1), date(2024, 2, 1), date(2024, 3, 1)]


def test_contribution_amount_step_up_every_two_years():
    plan = SavingsPlan()
    # Year 0-1 (deposit indexes 0..23) → 1.0M
    assert contribution_amount(0, plan) == 1_000_000
    assert contribution_amount(23, plan) == 1_000_000
    # Year 2-3 (deposit indexes 24..47) → 1.5M
    assert contribution_amount(24, plan) == 1_500_000
    assert contribution_amount(47, plan) == 1_500_000
    # Year 4-5 (deposit indexes 48..71) → 2.0M
    assert contribution_amount(48, plan) == 2_000_000


def test_contribution_amount_caps_at_max_escalations():
    plan = SavingsPlan(max_escalations=2)
    # After 2 escalations the amount should freeze.
    assert contribution_amount(48, plan) == 2_000_000
    assert contribution_amount(120, plan) == 2_000_000


def test_build_cash_flow_schedule_initial_then_monthly():
    plan = SavingsPlan()
    days = _bdates("2021-01-04", "2026-04-01")
    events = build_cash_flow_schedule(days, plan)
    assert events[0].kind == "initial"
    assert events[0].amount_krw == 10_000_000
    assert all(e.kind == "monthly" for e in events[1:])
    # Monthly contribution count = months in range minus the initial month.
    expected_months = len({(d.year, d.month) for d in days}) - 1
    assert len(events) - 1 == expected_months


def test_build_cash_flow_schedule_escalates_at_year_boundaries():
    plan = SavingsPlan()
    days = _bdates("2021-01-04", "2026-04-01")
    events = build_cash_flow_schedule(days, plan)
    # 25th deposit (index 25 in events list, deposit_index=24) — first 1.5M.
    assert events[25].amount_krw == 1_500_000
    # 49th deposit (index 49, deposit_index=48) — first 2.0M.
    assert events[49].amount_krw == 2_000_000


def test_total_contributed_matches_brief():
    plan = SavingsPlan()
    days = _bdates("2021-01-04", "2026-04-01")
    events = build_cash_flow_schedule(days, plan)
    total = total_contributed(events)
    # 5 calendar years + a few months. Should land near 100M KRW with default plan.
    assert 80_000_000 <= total <= 120_000_000


def test_empty_input_yields_empty_schedule():
    plan = SavingsPlan()
    assert build_cash_flow_schedule([], plan) == []
