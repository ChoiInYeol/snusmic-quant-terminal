from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from snusmic_pipeline.artifact_schemas import (
    PortfolioBacktestRow,
    validate_portfolio_backtest_rows,
)
from snusmic_pipeline.quant import RISK_FREE_RATES, PortfolioResult

PORTFOLIO_BACKTESTS_PATH = Path("data/portfolio_backtests.json")
EXPECTED_STRATEGIES = {"1/N", "momentum", "max_sharpe", "sortino", "max_return", "min_var", "calmar"}
EXPECTED_RISK_FREE_RATES = set(RISK_FREE_RATES)


def _committed_portfolio_backtest_rows() -> list[dict[str, Any]]:
    return validate_portfolio_backtest_rows(json.loads(PORTFOLIO_BACKTESTS_PATH.read_text(encoding="utf-8")))


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


def test_committed_portfolio_backtests_preserve_strategy_grid() -> None:
    rows = _committed_portfolio_backtest_rows()
    by_month: dict[str, set[tuple[str, float]]] = defaultdict(set)

    assert rows
    assert {row["status"] for row in rows} == {"ok"}
    for row in rows:
        assert row["strategy"] in EXPECTED_STRATEGIES
        assert row["risk_free_rate"] in EXPECTED_RISK_FREE_RATES
        assert (
            row["cohort_month"] == row["rebalance_date"][:7]
            or row["cohort_month"] < row["rebalance_date"][:7]
        )
        by_month[row["cohort_month"]].add((row["strategy"], row["risk_free_rate"]))

    expected_grid = {
        (strategy, risk_free_rate)
        for strategy in EXPECTED_STRATEGIES
        for risk_free_rate in EXPECTED_RISK_FREE_RATES
    }
    for cohort_month, observed_grid in by_month.items():
        assert observed_grid == expected_grid, cohort_month


def test_committed_portfolio_backtests_weights_match_symbols() -> None:
    rows = _committed_portfolio_backtest_rows()

    assert rows
    for row in rows:
        symbols = row["symbols"].split(",")
        weights = [float(weight) for weight in row["weights"].split(",")]

        assert symbols
        assert row["display_symbols"]
        assert len(weights) == len(symbols)
        assert all(symbol for symbol in symbols)
        assert all(weight >= -1e-12 for weight in weights)
        assert sum(weights) == pytest.approx(1.0, abs=5e-4)


def test_committed_portfolio_backtests_keep_metric_relationships() -> None:
    rows = _committed_portfolio_backtest_rows()

    assert rows
    for row in rows:
        assert row["expected_return"] is not None
        assert row["expected_volatility"] is not None
        assert row["realized_return"] is not None
        assert row["kospi_return"] is not None
        assert row["nasdaq_return"] is not None
        assert row["expected_volatility"] >= 0
        if row["expected_volatility"] == 0:
            assert row["expected_sharpe"] is None
        else:
            assert row["expected_sharpe"] == pytest.approx(
                (row["expected_return"] - row["risk_free_rate"]) / row["expected_volatility"]
            )
