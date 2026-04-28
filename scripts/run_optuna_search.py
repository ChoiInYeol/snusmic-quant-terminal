"""Run local-only strategy search for SNUSMIC follower variants.

Optuna is optional. If unavailable, this script uses a deterministic random
fallback so tests and lightweight local smoke runs still pass without making the
web runtime depend on Optuna.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd  # noqa: E402

from snusmic_pipeline.strategy_search.configs import ParametricSmicFollowerConfig  # noqa: E402
from snusmic_pipeline.strategy_search.strategy import evaluate_strategy, run_random_search  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study", default="smic-follower-v1")
    parser.add_argument("--trials", type=int, default=20)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--warehouse", type=Path, default=ROOT / "data" / "warehouse", help="Reserved for future full-engine strategy runs.")
    parser.add_argument("--sim-dir", type=Path, default=ROOT / "data" / "sim")
    parser.add_argument("--out", type=Path, default=ROOT / "data" / "optuna")
    parser.add_argument("--prefer-optuna", action="store_true", help="Use Optuna if installed; otherwise fallback remains deterministic.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report_performance = pd.read_csv(args.sim_dir / "report_performance.csv")
    summary_path = args.sim_dir / "summary.csv"
    baseline_summary = pd.read_csv(summary_path) if summary_path.exists() else None
    rows = _run_search(args, report_performance, baseline_summary)
    exports = args.out / "exports"
    studies = args.out / "studies"
    exports.mkdir(parents=True, exist_ok=True)
    studies.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(exports / "trials.csv", index=False)
    # Fallback/stub study marker documents whether a real Optuna DB was produced.
    marker = studies / f"{args.study.replace('-', '_')}.json"
    marker.write_text(
        '{\n  "study": "' + args.study + '",\n  "trials": ' + str(len(rows)) + ',\n  "local_only": true\n}\n',
        encoding="utf-8",
    )
    print(f"Trials: {len(rows)}")
    print(f"Best score: {rows[0]['score']:.6f}")
    print(f"Artifacts written to {exports}")
    return 0


def _run_search(args: argparse.Namespace, report_performance: pd.DataFrame, baseline_summary: pd.DataFrame | None) -> list[dict[str, Any]]:
    if not args.prefer_optuna:
        return run_random_search(report_performance, baseline_summary=baseline_summary, trials=args.trials, seed=args.seed)
    try:
        import optuna  # type: ignore[import-not-found]
    except Exception as exc:  # pragma: no cover - depends on local optional package
        print(f"Optuna unavailable ({exc}); using deterministic random fallback.")
        return run_random_search(report_performance, baseline_summary=baseline_summary, trials=args.trials, seed=args.seed)

    sampler = optuna.samplers.TPESampler(seed=args.seed)
    study = optuna.create_study(direction="maximize", sampler=sampler, study_name=args.study)

    def objective(trial: Any) -> float:
        min_upside = trial.suggest_float("min_target_upside_at_pub", 0.05, 1.5, step=0.01)
        config = ParametricSmicFollowerConfig(
            target_hit_multiplier=trial.suggest_float("target_hit_multiplier", 0.7, 1.2, step=0.01),
            min_target_upside_at_pub=min_upside,
            max_target_upside_at_pub=trial.suggest_float("max_target_upside_at_pub", round(max(0.2, min_upside), 2), 5.0, step=0.01),
            max_report_age_days=trial.suggest_int("max_report_age_days", 90, 1500),
            time_loss_days=trial.suggest_int("time_loss_days", 60, 1000),
            stop_loss_pct=trial.suggest_float("stop_loss_pct", 0.05, 0.50, step=0.01),
            take_profit_pct=trial.suggest_float("take_profit_pct", 0.05, 3.0, step=0.01),
            rebalance=trial.suggest_categorical("rebalance", ["monthly", "quarterly"]),
            max_positions=trial.suggest_int("max_positions", 5, 80),
            weighting=trial.suggest_categorical("weighting", ["equal", "target_upside", "inverse_volatility", "capped_target_upside"]),
            universe=trial.suggest_categorical("universe", ["all", "domestic", "overseas"]),
            exclude_missing_confidence_rows=trial.suggest_categorical("exclude_missing_confidence_rows", [False, True]),
            require_publication_price=trial.suggest_categorical("require_publication_price", [False, True]),
        )
        metrics = evaluate_strategy(config, report_performance, baseline_summary=baseline_summary)
        for key, value in {**config.model_dump(mode="json"), **metrics.model_dump(mode="json")}.items():
            trial.set_user_attr(key, value)
        return metrics.score

    study.optimize(objective, n_trials=args.trials)
    rows = []
    for t in study.trials:
        rows.append({"trial_number": t.number, "sampler": "optuna-tpe", "scope": "in-sample", **t.user_attrs})
    return sorted(rows, key=lambda row: float(row["score"]), reverse=True)


if __name__ == "__main__":
    raise SystemExit(main())
