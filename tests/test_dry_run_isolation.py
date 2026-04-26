"""Phase 2 AC #5 — dry-run path isolation.

When ``run_default_backtests(..., dry_run=True)`` runs, it must NOT touch the
real warehouse CSVs or the exported ``quant_v3/*.json`` dashboard bundle.
The test pre-seeds both locations with sentinel bytes and asserts they are
byte-identical after a dry_run executes.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from snusmic_pipeline.backtest.warehouse import run_default_backtests


def _write_sentinel(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_dry_run_does_not_overwrite_real_warehouse(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    warehouse = data_dir / "warehouse"
    quant_v3 = data_dir / "quant_v3"

    # Pre-seed reports.csv + daily_prices.csv + a quant_v3 snapshot with
    # sentinel bytes we can check for integrity post-dry_run.
    reports_frame = pd.DataFrame(
        [
            {
                "report_id": "r01",
                "publication_date": "2023-02-10",
                "title": "sentinel-report",
                "company": "Sentinel Co",
                "ticker": "SENT",
                "exchange": "KRX",
                "symbol": "SENT.KS",
                "target_price": 200.0,
                "report_current_price": 100.0,
            }
        ]
    )
    warehouse.mkdir(parents=True, exist_ok=True)
    reports_frame.to_csv(warehouse / "reports.csv", index=False)
    _write_sentinel(warehouse / "daily_prices.csv", "date,symbol,close\nSENTINEL,SENTINEL,0.0\n")
    _write_sentinel(quant_v3 / "strategy_runs.json", json.dumps([{"sentinel": True}]))

    real_prices_before = (warehouse / "daily_prices.csv").read_bytes()
    real_quant_before = (quant_v3 / "strategy_runs.json").read_bytes()

    run_default_backtests(data_dir, warehouse, dry_run=True)

    real_prices_after = (warehouse / "daily_prices.csv").read_bytes()
    real_quant_after = (quant_v3 / "strategy_runs.json").read_bytes()

    assert real_prices_before == real_prices_after, "dry_run overwrote warehouse/daily_prices.csv"
    assert real_quant_before == real_quant_after, "dry_run wrote into quant_v3/strategy_runs.json"
    assert (warehouse / "_dry_run").is_dir(), "dry_run did not isolate output to _dry_run subdirectory"
    assert (warehouse / "_dry_run" / "daily_prices.csv").exists(), (
        "dry_run did not write synthetic prices to its isolated dir"
    )
