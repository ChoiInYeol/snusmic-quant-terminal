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


def test_extended_web_artifacts_support_insights_and_downloads(tmp_path: Path) -> None:
    out = tmp_path / "web"
    export_web_artifacts(
        ExportInputs(
            warehouse=Path("data/warehouse"),
            sim=Path("data/sim"),
            out=out,
            extraction_quality=Path("data/extraction_quality.json"),
        )
    )

    insights = json.loads((out / "insights.json").read_text(encoding="utf-8"))
    detail_metrics = json.loads((out / "report-detail-metrics.json").read_text(encoding="utf-8"))
    return_windows = json.loads((out / "return-windows.json").read_text(encoding="utf-8"))
    target_distribution = json.loads((out / "target-hit-distribution.json").read_text(encoding="utf-8"))
    rankings = json.loads((out / "report-rankings.json").read_text(encoding="utf-8"))

    assert len(insights) >= 6
    assert "6615fd1894ed9c54" in detail_metrics
    assert detail_metrics["6615fd1894ed9c54"]["markers"]
    assert len(return_windows) == 216
    assert {"return_30d", "return_60d", "return_90d", "return_180d"} <= set(return_windows[0])
    assert target_distribution["summary"]["total_reports"] == 216
    assert rankings["fastest_hits"]
    assert rankings["best_current_returns"]
    assert (out / "table-download-reports.csv").read_text(encoding="utf-8").startswith("report_id,date")
    assert (out / "table-download-strategies.csv").read_text(encoding="utf-8").startswith("run_id")
    assert (out / "data-quality-download.csv").read_text(encoding="utf-8").startswith("section,metric,value")


def test_reports_artifact_uses_adjusted_target_price_when_price_scale_changed(tmp_path: Path) -> None:
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
    ezbio = next(row for row in reports if row["symbol"] == "353810.KQ")
    assert ezbio["company"] == "이지바이오"
    assert ezbio["entry_price_krw"] == 5379.95
    assert ezbio["target_price_krw"] == 7231.49
    assert ezbio["target_price"] == 7231.49
    assert ezbio["target_upside_at_pub"] == 0.34
    assert "price_scale_adjusted_target" in ezbio["caveat_flags"]

    csv_text = (out / "table-download-reports.csv").read_text(encoding="utf-8")
    assert "7e687ca6a743eff4" in csv_text
    assert "7231.49" in csv_text
    assert "103500" not in next(line for line in csv_text.splitlines() if "7e687ca6a743eff4" in line)


def test_reports_artifact_marks_target_below_entry_as_non_actionable(tmp_path: Path) -> None:
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
    rznomics = next(row for row in reports if row["symbol"] == "476830.KQ")
    assert rznomics["company"] == "알지노믹스"
    assert rznomics["target_upside_at_pub"] == -0.1
    assert rznomics["target_hit"] is False
    assert rznomics["target_hit_date"] is None
    assert rznomics["days_to_target"] is None
    assert "target_below_entry_price" in rznomics["caveat_flags"]
