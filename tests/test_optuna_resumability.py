"""Phase 3a — Optuna SQLite study must resume after a process kill.

Plan AC #3: "kill after trial 3, restart, reach trial 10 without replay
(SQLite single-writer property holds)." We simulate the kill by calling
``optimize_strategies`` twice with increasing ``trials`` budgets against
the same ``study_name`` + ``storage_path``; the second call must NOT redo
the trials the first call already completed.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from snusmic_pipeline.backtest.warehouse import optimize_strategies

optuna = pytest.importorskip("optuna")


def _seed_warehouse(data_dir: Path) -> Path:
    warehouse = data_dir / "warehouse"
    warehouse.mkdir(parents=True, exist_ok=True)
    reports = pd.DataFrame(
        [
            {
                "report_id": f"r{i:02d}",
                "publication_date": "2023-06-01",
                "title": f"Sentinel {i}",
                "company": f"Co {i}",
                "ticker": f"S{i:02d}",
                "exchange": "KRX",
                "symbol": f"S{i:02d}.KS",
                "target_price": 200.0 + i * 5,
                "report_current_price": 100.0,
            }
            for i in range(3)
        ]
    )
    reports.to_csv(warehouse / "reports.csv", index=False)
    return warehouse


def test_optuna_resume_after_partial_run(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    warehouse = _seed_warehouse(data_dir)
    storage = tmp_path / "study.sqlite"
    study_name = "phase3a-resume"

    # Round 1 — run 3 trials.
    df_1 = optimize_strategies(
        data_dir,
        warehouse,
        trials=3,
        seed=42,
        dry_run=True,
        study_name=study_name,
        storage_path=storage,
    )
    assert len(df_1) == 3

    # Snapshot Round-1 trial state BEFORE Round 2 runs. ``study.trials`` is
    # live-bound to the SQLite store, so re-reading it after Round 2 would
    # reflect the post-Round-2 cumulative state.
    storage_url = f"sqlite:///{storage}"
    persisted = optuna.load_study(study_name=study_name, storage=storage_url)
    round1_snapshot = [(t.number, t.value, dict(t.params)) for t in persisted.trials]
    assert len(round1_snapshot) == 3

    # Round 2 — same study_name, ask for 10 trials total. Must NOT replay 0-2.
    df_2 = optimize_strategies(
        data_dir,
        warehouse,
        trials=10,
        seed=42,
        dry_run=True,
        study_name=study_name,
        storage_path=storage,
    )
    persisted_after = optuna.load_study(study_name=study_name, storage=storage_url)
    assert len(persisted_after.trials) == 10, (
        f"expected 10 cumulative trials after resume, got {len(persisted_after.trials)} — "
        "study did not actually persist or resumability regressed."
    )
    assert len(df_2) == 10
    round2_first_three = [(t.number, t.value, dict(t.params)) for t in persisted_after.trials[:3]]
    assert round1_snapshot == round2_first_three, (
        "round-1 trials mutated on resume — Optuna replayed the warmup trials instead of preserving them."
    )


def test_optuna_resume_is_idempotent_when_budget_already_met(tmp_path: Path) -> None:
    """Calling ``optimize_strategies`` with ``trials=N`` after N trials are
    already complete must be a no-op (no extra trials added)."""
    data_dir = tmp_path / "data"
    warehouse = _seed_warehouse(data_dir)
    storage = tmp_path / "study.sqlite"
    study_name = "phase3a-noop"

    optimize_strategies(
        data_dir, warehouse, trials=4, seed=42, dry_run=True, study_name=study_name, storage_path=storage
    )
    optimize_strategies(
        data_dir, warehouse, trials=4, seed=42, dry_run=True, study_name=study_name, storage_path=storage
    )
    persisted = optuna.load_study(study_name=study_name, storage=f"sqlite:///{storage}")
    assert len(persisted.trials) == 4
