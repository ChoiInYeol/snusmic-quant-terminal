from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
from pydantic import ValidationError

from snusmic_pipeline.strategy_search.configs import ParametricSmicFollowerConfig
from snusmic_pipeline.strategy_search.export import export_strategy_artifacts
from snusmic_pipeline.strategy_search.objective import score_metrics
from snusmic_pipeline.strategy_search.strategy import evaluate_strategy, run_random_search


def _reports() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "report_id": "r1",
                "symbol": "000001.KS",
                "publication_date": "2024-01-01",
                "entry_price_krw": 100.0,
                "target_upside_at_pub": 0.30,
                "target_hit": True,
                "days_to_target": 40,
                "current_return": 0.12,
                "trough_return": -0.08,
            },
            {
                "report_id": "r2",
                "symbol": "ABC",
                "publication_date": "2024-02-01",
                "entry_price_krw": 100.0,
                "target_upside_at_pub": 0.80,
                "target_hit": False,
                "days_to_target": None,
                "current_return": -0.22,
                "trough_return": -0.35,
            },
        ]
    )


def _summary() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"persona": "smic_follower", "money_weighted_return": -0.10},
            {"persona": "smic_follower_v2", "money_weighted_return": 0.05},
            {"persona": "all_weather", "money_weighted_return": 0.08},
        ]
    )


def test_config_rejects_inverted_target_upside_range() -> None:
    with pytest.raises(ValidationError):
        ParametricSmicFollowerConfig(min_target_upside_at_pub=1.0, max_target_upside_at_pub=0.5)


def test_objective_score_formula_matches_plan() -> None:
    assert score_metrics(
        money_weighted_return=0.30,
        max_drawdown=0.20,
        annual_turnover_penalty=0.50,
        concentration_penalty=0.10,
    ) == pytest.approx(0.30 - 0.75 * 0.20 - 0.10 * 0.50 - 0.10 * 0.10)


def test_evaluate_strategy_exports_raw_metrics_and_baseline_excess() -> None:
    config = ParametricSmicFollowerConfig(max_positions=10, weighting="equal")
    metrics = evaluate_strategy(config, _reports(), baseline_summary=_summary())
    assert metrics.trade_count == 4
    assert metrics.hit_rate == pytest.approx(0.5)
    assert metrics.excess_return_vs_smic_follower is not None
    assert metrics.max_single_position_weight == pytest.approx(0.5)


def test_random_search_is_deterministic() -> None:
    first = run_random_search(_reports(), baseline_summary=_summary(), trials=5, seed=7)
    second = run_random_search(_reports(), baseline_summary=_summary(), trials=5, seed=7)
    assert first == second
    assert first[0]["score"] >= first[-1]["score"]


def test_export_strategy_artifacts(tmp_path: Path) -> None:
    rows = run_random_search(_reports(), baseline_summary=_summary(), trials=3, seed=3)
    trials_csv = tmp_path / "trials.csv"
    pd.DataFrame(rows).to_csv(trials_csv, index=False)
    paths = export_strategy_artifacts(trials_csv, tmp_path / "web", study_name="demo", top_n=2)
    data = json.loads(paths["strategy_runs"].read_text(encoding="utf-8"))
    assert data["best_run_id"].startswith("demo-trial-")
    assert len(data["runs"]) == 2
    assert paths["optuna_trials"].exists()
    assert paths["parameter_importance"].exists()
