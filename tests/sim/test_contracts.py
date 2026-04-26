"""SSOT contract guarantees: roundtrip, frozen-ness, validators."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from snusmic_pipeline.sim.contracts import (
    AllWeatherConfig,
    BenchmarkAsset,
    BrokerageFees,
    EquityPoint,
    ProphetConfig,
    SavingsPlan,
    SimulationConfig,
    SmicFollowerConfig,
    Trade,
)


def test_savings_plan_defaults_match_brief():
    plan = SavingsPlan()
    assert plan.initial_capital_krw == 10_000_000
    assert plan.monthly_contribution_krw == 1_000_000
    assert plan.escalation_step_krw == 500_000
    assert plan.escalation_period_years == 2


def test_brokerage_fees_validate_bps_range():
    fees = BrokerageFees()
    assert 0 <= fees.commission_bps <= 200
    with pytest.raises(ValidationError):
        BrokerageFees(commission_bps=-1.0)
    with pytest.raises(ValidationError):
        BrokerageFees(sell_tax_bps=10_000.0)


def test_simulation_config_roundtrip():
    cfg = SimulationConfig(start_date=date(2021, 1, 4), end_date=date(2026, 4, 1))
    rebuilt = SimulationConfig.model_validate_json(cfg.model_dump_json())
    assert rebuilt == cfg


def test_simulation_config_rejects_inverted_dates():
    with pytest.raises(ValidationError):
        SimulationConfig(start_date=date(2026, 1, 1), end_date=date(2025, 1, 1))


def test_simulation_config_rejects_duplicate_persona_names():
    with pytest.raises(ValidationError):
        SimulationConfig(
            start_date=date(2021, 1, 4),
            end_date=date(2026, 4, 1),
            personas=(ProphetConfig(), ProphetConfig()),
        )


def test_all_weather_weights_must_sum_to_one():
    with pytest.raises(ValidationError):
        AllWeatherConfig(
            assets=(
                BenchmarkAsset(name="Gold", symbol="GLD", weight=0.4),
                BenchmarkAsset(name="QQQ", symbol="QQQ", weight=0.3),
            )
        )


def test_all_weather_rejects_duplicate_symbols():
    with pytest.raises(ValidationError):
        AllWeatherConfig(
            assets=(
                BenchmarkAsset(name="Gold", symbol="GLD", weight=0.5),
                BenchmarkAsset(name="Gold copy", symbol="GLD", weight=0.5),
            )
        )


def test_persona_configs_are_frozen():
    cfg = SmicFollowerConfig()
    with pytest.raises(ValidationError):
        cfg.target_hit_multiplier = 1.5  # type: ignore[misc]


def test_trade_record_rejects_negative_qty():
    with pytest.raises(ValidationError):
        Trade(
            persona="x",
            date=date(2024, 1, 1),
            symbol="A",
            side="buy",
            qty=-1,
            fill_price_krw=100.0,
            gross_krw=0.0,
            commission_krw=0.0,
            tax_krw=0.0,
            cash_after_krw=0.0,
            reason="deposit_buy",
        )


def test_equity_point_serializes_to_json():
    p = EquityPoint(
        persona="oracle",
        date=date(2024, 1, 1),
        cash_krw=1.0,
        holdings_value_krw=2.0,
        equity_krw=3.0,
        contributed_capital_krw=10.0,
        net_profit_krw=-7.0,
        open_positions=0,
    )
    js = p.model_dump_json()
    rebuilt = EquityPoint.model_validate_json(js)
    assert rebuilt == p


def test_simulation_config_extras_forbidden():
    with pytest.raises(ValidationError):
        SimulationConfig.model_validate({"start_date": "2021-01-04", "end_date": "2026-04-01", "unknown": 1})
