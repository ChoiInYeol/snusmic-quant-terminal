from __future__ import annotations

from dataclasses import asdict

import pytest
from pydantic import ValidationError

from snusmic_pipeline.artifact_schemas import (
    PortfolioBacktestRow,
    validate_portfolio_backtest_rows,
)
from snusmic_pipeline.quant import PortfolioResult


def _portfolio_result(**overrides: object) -> PortfolioResult:
    values = {
        "cohort_month": "2026-01",
        "rebalance_date": "2026-01-16",
        "strategy": "1/N",
        "risk_free_rate": 0.03,
        "symbols": "000123.KS,AAPL",
        "display_symbols": "TestCo,Apple",
        "weights": "0.5000,0.5000",
        "expected_return": 0.12,
        "expected_volatility": 0.24,
        "expected_sharpe": 0.375,
        "realized_return": 0.08,
        "kospi_return": 0.02,
        "nasdaq_return": 0.05,
        "status": "ok",
    }
    values.update(overrides)
    return PortfolioResult(**values)


def test_portfolio_backtest_schema_matches_quant_dataclass_fields() -> None:
    assert set(PortfolioBacktestRow.model_fields) == set(PortfolioResult.__dataclass_fields__)


def test_portfolio_backtest_schema_validates_legacy_artifact_fields() -> None:
    row = validate_portfolio_backtest_rows([asdict(_portfolio_result(expected_sharpe=None))])[0]

    assert row["cohort_month"] == "2026-01"
    assert row["symbols"] == "000123.KS,AAPL"
    assert row["expected_sharpe"] is None
    assert row["realized_return"] == pytest.approx(0.08)


def test_portfolio_backtest_schema_rejects_unplanned_fields() -> None:
    row = asdict(_portfolio_result())
    row["unexpected_ai_slop"] = True

    with pytest.raises(ValidationError):
        validate_portfolio_backtest_rows([row])
