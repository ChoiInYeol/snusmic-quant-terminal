from __future__ import annotations

from dataclasses import asdict

import pytest
from pydantic import ValidationError

from snusmic_pipeline.artifact_schemas import PriceMetricRow, validate_price_metric_rows
from snusmic_pipeline.quant import PriceMetric


def _empty_metric(**overrides: object) -> PriceMetric:
    values = {
        "title": "Equity Research, Test",
        "company": "TestCo",
        "display_name": "TestCo",
        "ticker": "000123",
        "yfinance_symbol": "000123.KS",
        "price_currency": "KRW",
        "target_currency": "KRW",
        "display_currency": "KRW",
        "publication_date": "2026-01-01",
        "publication_buy_price": 100.0,
        "current_price": 110.0,
        "target_price": 120.0,
        "buy_at_publication_return": 0.1,
        "publication_to_target_return": 0.2,
        "oracle_entry_price": 80.0,
        "oracle_exit_price": 150.0,
        "oracle_return": 0.875,
        "oracle_buy_lag_days": 1,
        "oracle_holding_days": 2,
        "smic_follower_entry_price": 100.0,
        "smic_follower_exit_price": 120.0,
        "smic_follower_return": 0.2,
        "smic_follower_holding_days": 2,
        "smic_follower_status": "target_hit",
        "lowest_price_since_publication": 80.0,
        "lowest_price_current_return": 0.375,
        "low_to_high_return": 0.875,
        "low_to_high_holding_days": 2,
        "q25_price_since_publication": 95.0,
        "q25_price_current_return": 0.1578947368,
        "highest_price_since_publication": 150.0,
        "highest_price_realized_return": 0.5,
        "q75_price_since_publication": 127.5,
        "q75_price_realized_return": 0.275,
        "q75_price_current_return": -0.137254902,
        "current_price_percentile": 0.5,
        "target_upside_remaining": 0.0909090909,
        "optimal_buy_lag_days": 1,
        "optimal_holding_days_net_10pct": 2,
        "optimal_net_return_10pct": 0.87445,
        "target_hit": True,
        "first_target_hit_date": "2026-01-03",
        "target_hit_holding_days": 2,
        "status": "ok",
        "note": "",
    }
    values.update(overrides)
    return PriceMetric(**values)


def test_price_metric_schema_matches_quant_dataclass_fields() -> None:
    assert set(PriceMetricRow.model_fields) == set(PriceMetric.__dataclass_fields__)


def test_price_metric_schema_validates_baseline_band_fields() -> None:
    row = validate_price_metric_rows([asdict(_empty_metric())])[0]

    assert row["ticker"] == "000123"
    assert row["smic_follower_return"] == pytest.approx(0.2)
    assert row["oracle_return"] == pytest.approx(0.875)
    assert row["smic_follower_return"] <= row["oracle_return"]


def test_price_metric_schema_rejects_unplanned_fields() -> None:
    row = asdict(_empty_metric())
    row["unexpected_ai_slop"] = True

    with pytest.raises(ValidationError):
        validate_price_metric_rows([row])
