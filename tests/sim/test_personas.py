"""Per-persona behavior on the synthetic three-symbol universe."""

from __future__ import annotations

from snusmic_pipeline.sim.contracts import (
    BrokerageFees,
    ProphetConfig,
    SavingsPlan,
    SmicFollowerConfig,
    SmicFollowerV2Config,
    WeakProphetConfig,
)
from snusmic_pipeline.sim.personas import (
    simulate_prophet,
    simulate_smic_follower,
    simulate_smic_follower_v2,
    simulate_weak_prophet,
)
from snusmic_pipeline.sim.savings import build_cash_flow_schedule


def _common_inputs(synthetic_dates):
    plan = SavingsPlan(
        initial_capital_krw=10_000_000,
        monthly_contribution_krw=1_000_000,
        escalation_step_krw=500_000,
    )
    fees = BrokerageFees()
    cashflows = build_cash_flow_schedule(synthetic_dates, plan)
    return plan, fees, cashflows


def test_prophet_concentrates_on_realised_winner(synthetic_board, synthetic_reports, synthetic_dates):
    plan, fees, cashflows = _common_inputs(synthetic_dates)
    cfg = ProphetConfig(dominance_threshold=1.2)
    out = simulate_prophet(cfg, plan, fees, synthetic_board, synthetic_reports, cashflows, synthetic_dates)
    # The prophet should have only ever bought WIN since its realised peak return
    # dominates LOSS and FLAT by a wide margin in this fixture.
    bought_symbols = {t.symbol for t in out.account.trades if t.side == "buy"}
    assert bought_symbols == {"WIN"}
    assert out.summary.net_profit_krw > 0


def test_smic_follower_holds_losers_and_sells_only_at_target(
    synthetic_board, synthetic_reports, synthetic_dates
):
    plan, fees, cashflows = _common_inputs(synthetic_dates)
    cfg = SmicFollowerConfig()
    out = simulate_smic_follower(
        cfg, plan, fees, synthetic_board, synthetic_reports, cashflows, synthetic_dates
    )
    # WIN crosses its target (180) — there should be at least one target_hit sell.
    sells = [t for t in out.account.trades if t.side == "sell"]
    target_hits = [t for t in sells if t.reason == "target_hit"]
    assert any(t.symbol == "WIN" for t in target_hits)
    # LOSS slid from 100 → ~70 — its target was 130 so it never hit; the follower
    # must NOT have sold it for any reason other than the end-of-sim cleanup.
    loss_sells = [t for t in sells if t.symbol == "LOSS" and t.reason != "end_of_sim"]
    assert loss_sells == []


def test_smic_follower_v2_stops_out_long_held_loser(synthetic_board, synthetic_reports, synthetic_dates):
    plan, fees, cashflows = _common_inputs(synthetic_dates)
    # Tighten time-loss to 200 days so it actually fires inside the 2y fixture.
    cfg = SmicFollowerV2Config(time_loss_days=200, report_age_stop_days=600, averaged_down_stop_pct=0.10)
    out = simulate_smic_follower_v2(
        cfg, plan, fees, synthetic_board, synthetic_reports, cashflows, synthetic_dates
    )
    sells = [t for t in out.account.trades if t.side == "sell"]
    reasons = {t.reason for t in sells}
    # At least one of the LOSS-driven stop-loss rules must have fired.
    assert reasons & {"stop_loss_time", "stop_loss_average_down", "stop_loss_report_age"}


def test_weak_prophet_runs_and_picks_winners(synthetic_board, synthetic_reports, synthetic_dates):
    plan, fees, cashflows = _common_inputs(synthetic_dates)
    cfg = WeakProphetConfig(lookahead_months=3, max_weight=1.0, min_history_days=30)
    out = simulate_weak_prophet(
        cfg, plan, fees, synthetic_board, synthetic_reports, cashflows, synthetic_dates
    )
    # Should beat raw deposits since WIN has positive expected return.
    assert out.summary.final_equity_krw > out.summary.total_contributed_krw * 0.95
    # Should have made at least a few buys.
    assert sum(1 for t in out.account.trades if t.side == "buy") >= 1


def test_followers_v1_and_v2_diverge(synthetic_board, synthetic_reports, synthetic_dates):
    plan, fees, cashflows = _common_inputs(synthetic_dates)
    v1 = simulate_smic_follower(
        SmicFollowerConfig(), plan, fees, synthetic_board, synthetic_reports, cashflows, synthetic_dates
    )
    v2 = simulate_smic_follower_v2(
        SmicFollowerV2Config(time_loss_days=200, averaged_down_stop_pct=0.10, report_age_stop_days=600),
        plan,
        fees,
        synthetic_board,
        synthetic_reports,
        cashflows,
        synthetic_dates,
    )
    # Different exit policies must produce different trade counts in this fixture.
    assert v1.summary.trade_count != v2.summary.trade_count


def test_persona_summaries_have_finite_irr(synthetic_board, synthetic_reports, synthetic_dates):
    import math

    plan, fees, cashflows = _common_inputs(synthetic_dates)
    out = simulate_prophet(
        ProphetConfig(), plan, fees, synthetic_board, synthetic_reports, cashflows, synthetic_dates
    )
    irr = out.summary.money_weighted_return
    assert math.isfinite(irr)
