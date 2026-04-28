from __future__ import annotations

import json
from pathlib import Path

from snusmic_pipeline.web_artifacts import ExportInputs, check_web_artifacts, export_web_artifacts


def test_export_web_artifacts_matches_baseline_counts(tmp_path: Path) -> None:
    out = tmp_path / "web"
    result = export_web_artifacts(
        ExportInputs(
            warehouse=Path("data/warehouse"),
            sim=Path("data/sim"),
            out=out,
            extraction_quality=Path("data/extraction_quality.json"),
        )
    )

    overview = json.loads((out / "overview.json").read_text(encoding="utf-8"))
    assert overview["report_counts"] == {
        "extracted_reports": 216,
        "missing_price_symbols": 5,
        "price_matched_reports": 206,
        "report_stat_rows": 211,
        "web_report_rows": 216,
    }
    assert result["missing_symbols"] == ["003410.KS", "010620.KS", "287410.KQ", "NETI", "VTNR"]


def test_reports_artifact_contains_be_h_symbol_fix(tmp_path: Path) -> None:
    out = tmp_path / "web"
    export_web_artifacts(
        ExportInputs(
            warehouse=Path("data/warehouse"),
            sim=Path("data/sim"),
            out=out,
            extraction_quality=Path("data/extraction_quality.json"),
        )
    )

    reports = json.loads((out / "reports.json").read_text(encoding="utf-8"))
    be_h = [row for row in reports if row["company"] == "비에이치"]
    assert len(be_h) == 1
    assert be_h[0]["symbol"] == "090460.KS"
    assert be_h[0]["report_id"] == "6615fd1894ed9c54"


def test_check_web_artifacts_requires_deterministic_json(tmp_path: Path) -> None:
    out = tmp_path / "web"
    result = check_web_artifacts(
        ExportInputs(
            warehouse=Path("data/warehouse"),
            sim=Path("data/sim"),
            out=out,
            extraction_quality=Path("data/extraction_quality.json"),
        )
    )

    assert (out / "overview.json").exists()
    assert (out / "prices" / "090460.KS.json").exists()
    assert result["artifact_count"] > 8
