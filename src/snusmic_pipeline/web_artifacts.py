from __future__ import annotations

import json
import math
import shutil
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import pandas as pd

REQUIRED_ARTIFACTS = [
    "overview.json",
    "personas.json",
    "reports.json",
    "report-rankings.json",
    "current-holdings.json",
    "monthly-holdings.json",
    "missing-symbols.json",
    "data-quality.json",
]


@dataclass(frozen=True)
class ExportInputs:
    warehouse: Path = Path("data/warehouse")
    sim: Path = Path("data/sim")
    out: Path = Path("data/web")
    extraction_quality: Path = Path("data/extraction_quality.json")


def export_web_artifacts(inputs: ExportInputs) -> dict[str, Any]:
    """Export deterministic JSON artifacts for the static web showcase."""

    reports = _read_csv(inputs.warehouse / "reports.csv")
    prices = _read_csv(inputs.warehouse / "daily_prices.csv")
    summary = _read_csv(inputs.sim / "summary.csv")
    current_holdings = _read_csv(inputs.sim / "current_holdings.csv")
    monthly_holdings = _read_optional_csv(inputs.sim / "monthly_holdings.csv")
    report_performance = _read_csv(inputs.sim / "report_performance.csv")
    report_stats = _read_json(inputs.sim / "report_stats.json")
    extraction_quality = _read_json(inputs.extraction_quality) if inputs.extraction_quality.exists() else {}

    out = inputs.out
    prices_out = out / "prices"
    if out.exists():
        shutil.rmtree(out)
    prices_out.mkdir(parents=True, exist_ok=True)

    price_symbols = set(prices["symbol"].dropna().astype(str)) if not prices.empty else set()
    report_symbols = set(reports["symbol"].dropna().astype(str)) if not reports.empty else set()
    report_symbols.discard("")
    missing_symbols = sorted(report_symbols - price_symbols)

    report_rows = _build_report_rows(reports, report_performance, extraction_quality, missing_symbols)
    overview = _build_overview(reports, prices, summary, report_stats, missing_symbols, report_rows)
    rankings = _build_rankings(report_stats)
    data_quality = _build_data_quality(extraction_quality, missing_symbols, reports, report_performance)

    _write_json(out / "overview.json", overview)
    _write_json(out / "personas.json", _records(summary))
    _write_json(out / "reports.json", report_rows)
    _write_json(out / "report-rankings.json", rankings)
    _write_json(out / "current-holdings.json", _records(current_holdings))
    _write_json(out / "monthly-holdings.json", _records(monthly_holdings))
    _write_json(out / "missing-symbols.json", [{"symbol": symbol} for symbol in missing_symbols])
    _write_json(out / "data-quality.json", data_quality)
    _write_price_artifacts(prices, report_symbols - set(missing_symbols), prices_out)

    written = sorted(str(path.relative_to(out)) for path in out.rglob("*.json"))
    return {
        "out": str(out),
        "artifact_count": len(written),
        "artifacts": written,
        "overview": overview,
        "missing_symbols": missing_symbols,
    }


def check_web_artifacts(inputs: ExportInputs) -> dict[str, Any]:
    """Export and verify required artifacts plus deterministic repeated output."""

    first = export_web_artifacts(inputs)
    missing = [name for name in REQUIRED_ARTIFACTS if not (inputs.out / name).exists()]
    if missing:
        raise RuntimeError(f"Missing required web artifacts: {', '.join(missing)}")

    first_bytes = _snapshot_json_bytes(inputs.out)
    with TemporaryDirectory() as tmpdir:
        second_inputs = ExportInputs(
            warehouse=inputs.warehouse,
            sim=inputs.sim,
            out=Path(tmpdir) / "web",
            extraction_quality=inputs.extraction_quality,
        )
        export_web_artifacts(second_inputs)
        second_bytes = _snapshot_json_bytes(second_inputs.out)
    if first_bytes != second_bytes:
        raise RuntimeError("Web artifact export is not deterministic under repeated export")
    return first


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing required CSV: {path}")
    return pd.read_csv(path, keep_default_na=False)


def _read_optional_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, keep_default_na=False)


def _read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_clean(data), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _snapshot_json_bytes(root: Path) -> dict[str, bytes]:
    return {str(path.relative_to(root)): path.read_bytes() for path in sorted(root.rglob("*.json"))}


def _records(df: pd.DataFrame) -> list[dict[str, Any]]:
    if df.empty:
        return []
    return [_clean(record) for record in df.to_dict(orient="records")]


def _clean(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _clean(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_clean(item) for item in value]
    if isinstance(value, tuple):
        return [_clean(item) for item in value]
    if pd.isna(value):
        return None
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    if hasattr(value, "item"):
        return _clean(value.item())
    return value


def _number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(parsed) or math.isinf(parsed):
        return None
    return parsed


def _bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value in ("True", "true", "1", 1):
        return True
    if value in ("False", "false", "0", 0):
        return False
    return None


def _build_report_rows(
    reports: pd.DataFrame,
    report_performance: pd.DataFrame,
    extraction_quality: dict[str, Any],
    missing_symbols: list[str],
) -> list[dict[str, Any]]:
    performance_by_id = {str(row["report_id"]): row for row in report_performance.to_dict(orient="records")}
    review_reasons = _review_reasons_by_report(reports, extraction_quality)
    missing = set(missing_symbols)
    rows: list[dict[str, Any]] = []
    for row in reports.sort_values(["publication_date", "page", "ordinal", "report_id"]).to_dict(
        orient="records"
    ):
        report_id = str(row["report_id"])
        perf = performance_by_id.get(report_id, {})
        symbol = str(row.get("symbol", ""))
        caveats = []
        if symbol in missing:
            caveats.append("missing_price_history")
        if not perf:
            caveats.append("missing_report_performance")
        caveats.extend(review_reasons.get(report_id, []))
        rows.append(
            {
                "report_id": report_id,
                "date": row.get("publication_date"),
                "company": row.get("company"),
                "ticker": row.get("ticker"),
                "exchange": row.get("exchange"),
                "symbol": symbol,
                "title": row.get("title"),
                "rating": row.get("rating"),
                "pdf_url": row.get("pdf_url"),
                "markdown_filename": row.get("markdown_filename"),
                "target_price": _number(row.get("target_price")),
                "target_price_krw": _number(row.get("target_price_krw")),
                "publication_price_krw": _number(row.get("report_current_price_krw")),
                "entry_price_krw": _number(perf.get("entry_price_krw")),
                "target_upside_at_pub": _number(perf.get("target_upside_at_pub")),
                "target_hit": _bool(perf.get("target_hit")),
                "target_hit_date": perf.get("target_hit_date") or None,
                "days_to_target": _number(perf.get("days_to_target")),
                "last_close_krw": _number(perf.get("last_close_krw")),
                "last_close_date": perf.get("last_close_date") or None,
                "current_return": _number(perf.get("current_return")),
                "peak_return": _number(perf.get("peak_return")),
                "trough_return": _number(perf.get("trough_return")),
                "target_gap_pct": _number(perf.get("target_gap_pct")),
                "caveat_flags": sorted(set(caveats)),
            }
        )
    return rows


def _review_reasons_by_report(
    reports: pd.DataFrame, extraction_quality: dict[str, Any]
) -> dict[str, list[str]]:
    if not extraction_quality.get("review_rows"):
        return {}
    ids_by_key = {
        (str(row.get("publication_date", ""))[:10], str(row.get("company", ""))): str(
            row.get("report_id", "")
        )
        for row in reports.to_dict(orient="records")
    }
    reasons: dict[str, list[str]] = {}
    for review in extraction_quality.get("review_rows", []):
        key = (str(review.get("date", ""))[:10], str(review.get("company", "")))
        report_id = ids_by_key.get(key)
        if not report_id:
            continue
        reasons[report_id] = [f"extraction_review:{reason}" for reason in review.get("reasons", [])]
    return reasons


def _build_overview(
    reports: pd.DataFrame,
    prices: pd.DataFrame,
    summary: pd.DataFrame,
    report_stats: dict[str, Any],
    missing_symbols: list[str],
    report_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    dates = [str(row["date"]) for row in report_rows if row.get("date")]
    price_dates = prices["date"].tolist() if "date" in prices else []
    return {
        "generated_from": {
            "warehouse_reports": "data/warehouse/reports.csv",
            "warehouse_daily_prices": "data/warehouse/daily_prices.csv",
            "sim_summary": "data/sim/summary.csv",
            "sim_report_stats": "data/sim/report_stats.json",
        },
        "report_counts": {
            "extracted_reports": int(len(reports)),
            "report_stat_rows": int(report_stats.get("total_reports", 0)),
            "price_matched_reports": int(report_stats.get("reports_with_prices", 0)),
            "missing_price_symbols": len(missing_symbols),
            "web_report_rows": len(report_rows),
        },
        "target_stats": {
            "target_hit_count": report_stats.get("target_hit_count"),
            "target_hit_rate": report_stats.get("target_hit_rate"),
            "avg_days_to_target": report_stats.get("avg_days_to_target"),
            "median_days_to_target": report_stats.get("median_days_to_target"),
            "avg_current_return": report_stats.get("avg_current_return"),
            "median_current_return": report_stats.get("median_current_return"),
        },
        "baseline_personas": _records(summary),
        "simulation_window": {
            "report_start": min(dates) if dates else None,
            "report_end": max(dates) if dates else None,
            "price_start": min(price_dates) if price_dates else None,
            "price_end": max(price_dates) if price_dates else None,
        },
    }


def _build_rankings(report_stats: dict[str, Any]) -> dict[str, Any]:
    return {
        "top_winners": report_stats.get("top_winners", []),
        "top_losers": report_stats.get("top_losers", []),
        "fastest_hits": report_stats.get("fastest_hits", []),
        "biggest_open_target_gaps": report_stats.get("biggest_open_target_gaps", []),
        "most_aggressive_targets": report_stats.get("most_aggressive_targets", []),
    }


def _build_data_quality(
    extraction_quality: dict[str, Any],
    missing_symbols: list[str],
    reports: pd.DataFrame,
    report_performance: pd.DataFrame,
) -> dict[str, Any]:
    performance_ids = (
        set(report_performance["report_id"].astype(str)) if not report_performance.empty else set()
    )
    report_ids = set(reports["report_id"].astype(str)) if not reports.empty else set()
    return {
        "extraction_quality": extraction_quality,
        "missing_symbols": [{"symbol": symbol} for symbol in missing_symbols],
        "coverage": {
            "warehouse_reports": len(report_ids),
            "report_performance_rows": len(performance_ids),
            "reports_without_performance": len(report_ids - performance_ids),
        },
    }


def _write_price_artifacts(prices: pd.DataFrame, symbols: set[str], prices_out: Path) -> None:
    if prices.empty:
        return
    filtered = prices[prices["symbol"].astype(str).isin(symbols)].copy()
    filtered.sort_values(["symbol", "date"], inplace=True)
    for symbol, group in filtered.groupby("symbol", sort=True):
        rows = []
        for row in group.to_dict(orient="records"):
            krw_per_unit = _number(row.get("krw_per_unit")) or 1.0
            close = _number(row.get("close"))
            rows.append(
                {
                    "date": row.get("date"),
                    "open": _number(row.get("open")),
                    "high": _number(row.get("high")),
                    "low": _number(row.get("low")),
                    "close": close,
                    "close_krw": round(close * krw_per_unit, 4) if close is not None else None,
                    "volume": _number(row.get("volume")),
                    "source_currency": row.get("source_currency"),
                    "display_currency": row.get("display_currency"),
                }
            )
        _write_json(prices_out / f"{symbol}.json", {"symbol": symbol, "prices": rows})
