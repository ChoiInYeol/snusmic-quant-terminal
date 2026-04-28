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
    "report-detail-metrics.json",
    "return-windows.json",
    "target-hit-distribution.json",
    "insights.json",
    "current-holdings.json",
    "monthly-holdings.json",
    "missing-symbols.json",
    "data-quality.json",
    "table-download-reports.csv",
    "table-download-strategies.csv",
    "data-quality-download.csv",
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
    return_windows = _build_return_windows(report_rows, prices)
    detail_metrics = _build_detail_metrics(report_rows, prices, return_windows)
    target_distribution = _build_target_hit_distribution(report_rows)
    rankings = _build_rankings(report_stats, report_rows)
    data_quality = _build_data_quality(extraction_quality, missing_symbols, reports, report_performance)
    insights = _build_insights(overview, rankings, target_distribution, return_windows, data_quality)

    _write_json(out / "overview.json", overview)
    _write_json(out / "personas.json", _records(summary))
    _write_json(out / "reports.json", report_rows)
    _write_json(out / "report-rankings.json", rankings)
    _write_json(out / "report-detail-metrics.json", detail_metrics)
    _write_json(out / "return-windows.json", return_windows)
    _write_json(out / "target-hit-distribution.json", target_distribution)
    _write_json(out / "insights.json", insights)
    _write_json(out / "current-holdings.json", _records(current_holdings))
    _write_json(out / "monthly-holdings.json", _records(monthly_holdings))
    _write_json(out / "missing-symbols.json", [{"symbol": symbol} for symbol in missing_symbols])
    _write_json(out / "data-quality.json", data_quality)
    _write_download_csvs(out, report_rows, data_quality)
    _write_price_artifacts(prices, report_symbols - set(missing_symbols), prices_out)

    written = sorted(str(path.relative_to(out)) for path in out.rglob("*") if path.suffix in {".json", ".csv"})
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
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.suffix in {".json", ".csv"}
    }


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
        raw_target_price_krw = _number(row.get("target_price_krw"))
        perf_target_price_krw = _number(perf.get("target_price_krw"))
        target_price_krw = perf_target_price_krw if perf_target_price_krw is not None else raw_target_price_krw
        raw_target_price = _number(row.get("target_price"))
        target_price = target_price_krw if target_price_krw is not None else raw_target_price
        if (
            raw_target_price_krw is not None
            and target_price_krw is not None
            and not math.isclose(raw_target_price_krw, target_price_krw, rel_tol=1e-9, abs_tol=0.01)
        ):
            caveats.append("price_scale_adjusted_target")
        target_upside_at_pub = _number(perf.get("target_upside_at_pub"))
        if target_upside_at_pub is not None and target_upside_at_pub <= 0:
            caveats.append("target_below_entry_price")
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
                "target_price": target_price,
                "target_price_krw": target_price_krw,
                "publication_price_krw": _number(row.get("report_current_price_krw")),
                "entry_price_krw": _number(perf.get("entry_price_krw")),
                "target_upside_at_pub": target_upside_at_pub,
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


def _build_rankings(report_stats: dict[str, Any], report_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Build table-ready rankings with compatibility aliases for older stats keys."""

    rows_with_current = [row for row in report_rows if row.get("current_return") is not None]
    rows_with_gap = [row for row in report_rows if row.get("target_gap_pct") is not None]
    rows_with_upside = [row for row in report_rows if row.get("target_upside_at_pub") is not None]
    hit_rows = [row for row in report_rows if row.get("target_hit") and row.get("days_to_target") is not None]
    return {
        "top_winners": report_stats.get("top_winners") or _rank(rows_with_current, "current_return", True),
        "top_losers": report_stats.get("top_losers") or _rank(rows_with_current, "current_return", False),
        "fastest_hits": report_stats.get("fastest_hits")
        or report_stats.get("fastest_target_hits")
        or _rank(hit_rows, "days_to_target", False),
        "slowest_hits": report_stats.get("slowest_target_hits") or _rank(hit_rows, "days_to_target", True),
        "biggest_open_target_gaps": report_stats.get("biggest_open_target_gaps")
        or report_stats.get("biggest_target_gaps_below")
        or _rank(rows_with_gap, "target_gap_pct", True),
        "biggest_target_overshoots": report_stats.get("biggest_target_overshoots")
        or _rank(rows_with_gap, "target_gap_pct", False),
        "most_aggressive_targets": report_stats.get("most_aggressive_targets")
        or _rank(rows_with_upside, "target_upside_at_pub", True),
        "best_current_returns": _rank(rows_with_current, "current_return", True),
        "worst_current_returns": _rank(rows_with_current, "current_return", False),
    }


def _rank(rows: list[dict[str, Any]], metric: str, descending: bool, limit: int = 10) -> list[dict[str, Any]]:
    ranked = sorted(rows, key=lambda row: _number(row.get(metric)) or 0, reverse=descending)
    return [
        {
            "report_id": row.get("report_id"),
            "date": row.get("date"),
            "company": row.get("company"),
            "symbol": row.get("symbol"),
            "metric": metric,
            "value": _number(row.get(metric)),
            "current_return": _number(row.get("current_return")),
            "target_hit": _bool(row.get("target_hit")),
            "days_to_target": _number(row.get("days_to_target")),
            "target_gap_pct": _number(row.get("target_gap_pct")),
        }
        for row in ranked[:limit]
    ]


def _build_return_windows(
    report_rows: list[dict[str, Any]], prices: pd.DataFrame, windows: tuple[int, ...] = (30, 60, 90, 180)
) -> list[dict[str, Any]]:
    if prices.empty:
        return []
    priced = prices.copy()
    priced["date"] = pd.to_datetime(priced["date"], errors="coerce")
    priced["close_krw"] = priced.apply(
        lambda row: (_number(row.get("close")) or 0) * (_number(row.get("krw_per_unit")) or 1.0), axis=1
    )
    by_symbol = {str(symbol): group.sort_values("date") for symbol, group in priced.groupby("symbol", sort=True)}
    results: list[dict[str, Any]] = []
    for report in sorted(report_rows, key=lambda row: str(row.get("report_id"))):
        symbol = str(report.get("symbol") or "")
        group = by_symbol.get(symbol)
        entry_price = _number(report.get("entry_price_krw")) or _number(report.get("publication_price_krw"))
        publication_date = pd.to_datetime(report.get("date"), errors="coerce")
        if group is None or entry_price in (None, 0) or pd.isna(publication_date):
            window_values = {f"return_{days}d": None for days in windows}
            window_values.update({f"price_{days}d_krw": None for days in windows})
            window_values.update({f"date_{days}d": None for days in windows})
        else:
            window_values = {}
            for days in windows:
                target_date = publication_date + pd.Timedelta(days=days)
                candidates = group[group["date"] >= target_date]
                if candidates.empty:
                    window_values[f"return_{days}d"] = None
                    window_values[f"price_{days}d_krw"] = None
                    window_values[f"date_{days}d"] = None
                    continue
                price_row = candidates.iloc[0]
                price = _number(price_row.get("close_krw"))
                window_values[f"return_{days}d"] = round((price / entry_price) - 1, 6) if price else None
                window_values[f"price_{days}d_krw"] = round(price, 4) if price is not None else None
                window_values[f"date_{days}d"] = price_row["date"].date().isoformat()
        results.append(
            {
                "report_id": report.get("report_id"),
                "company": report.get("company"),
                "symbol": symbol,
                "date": report.get("date"),
                "entry_price_krw": entry_price,
                **window_values,
            }
        )
    return results


def _build_detail_metrics(
    report_rows: list[dict[str, Any]],
    prices: pd.DataFrame,
    return_windows: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    windows_by_id = {str(row.get("report_id")): row for row in return_windows}
    if prices.empty:
        return {
            str(row["report_id"]): _detail_without_prices(row, windows_by_id.get(str(row["report_id"]), {}))
            for row in report_rows
        }
    priced = prices.copy()
    priced["date"] = pd.to_datetime(priced["date"], errors="coerce")
    priced["close_krw"] = priced.apply(
        lambda row: (_number(row.get("close")) or 0) * (_number(row.get("krw_per_unit")) or 1.0), axis=1
    )
    by_symbol = {str(symbol): group.sort_values("date") for symbol, group in priced.groupby("symbol", sort=True)}
    details: dict[str, dict[str, Any]] = {}
    for report in sorted(report_rows, key=lambda row: str(row.get("report_id"))):
        report_id = str(report["report_id"])
        publication_date = pd.to_datetime(report.get("date"), errors="coerce")
        history = by_symbol.get(str(report.get("symbol") or ""))
        after_publication = (
            history[history["date"] >= publication_date].copy()
            if history is not None and not pd.isna(publication_date)
            else pd.DataFrame()
        )
        entry_price = _number(report.get("entry_price_krw")) or _number(report.get("publication_price_krw"))
        target_price = _number(report.get("target_price_krw"))
        markers = [
            {"date": report.get("date"), "type": "publication", "label": "리포트 발간", "price_krw": entry_price}
        ]
        peak = trough = None
        if not after_publication.empty:
            peak_row = after_publication.loc[after_publication["close_krw"].idxmax()]
            trough_row = after_publication.loc[after_publication["close_krw"].idxmin()]
            last_row = after_publication.iloc[-1]
            peak = _price_marker(peak_row, "peak", "발간 후 고점")
            trough = _price_marker(trough_row, "trough", "발간 후 저점")
            markers.extend([peak, trough, _price_marker(last_row, "latest", "최근 종가")])
        if report.get("target_hit_date"):
            markers.append(
                {
                    "date": report.get("target_hit_date"),
                    "type": "target_hit",
                    "label": "목표가 도달",
                    "price_krw": target_price,
                }
            )
        details[report_id] = {
            "report_id": report_id,
            "company": report.get("company"),
            "symbol": report.get("symbol"),
            "target_price_krw": target_price,
            "entry_price_krw": entry_price,
            "current_return": _number(report.get("current_return")),
            "peak_return": _number(report.get("peak_return")),
            "trough_return": _number(report.get("trough_return")),
            "target_gap_pct": _number(report.get("target_gap_pct")),
            "target_hit": _bool(report.get("target_hit")),
            "days_to_target": _number(report.get("days_to_target")),
            "return_windows": windows_by_id.get(report_id, {}),
            "markers": sorted([marker for marker in markers if marker.get("date")], key=lambda marker: str(marker["date"])),
            "price_extremes": {"peak": peak, "trough": trough},
        }
    return details


def _detail_without_prices(report: dict[str, Any], windows: dict[str, Any]) -> dict[str, Any]:
    return {
        "report_id": report.get("report_id"),
        "company": report.get("company"),
        "symbol": report.get("symbol"),
        "return_windows": windows,
        "markers": [{"date": report.get("date"), "type": "publication", "label": "리포트 발간"}],
        "price_extremes": {"peak": None, "trough": None},
    }


def _price_marker(row: pd.Series, marker_type: str, label: str) -> dict[str, Any]:
    price = _number(row.get("close_krw"))
    return {
        "date": row["date"].date().isoformat(),
        "type": marker_type,
        "label": label,
        "price_krw": round(price, 4) if price is not None else None,
    }


def _build_target_hit_distribution(report_rows: list[dict[str, Any]]) -> dict[str, Any]:
    bins = [
        ("0-30일", 0, 30),
        ("31-60일", 31, 60),
        ("61-90일", 61, 90),
        ("91-180일", 91, 180),
        ("181-365일", 181, 365),
        ("365일+", 366, None),
    ]
    hit_rows = [row for row in report_rows if row.get("target_hit") and _number(row.get("days_to_target")) is not None]
    day_buckets = []
    for label, lower, upper in bins:
        count = sum(
            1
            for row in hit_rows
            if (days := _number(row.get("days_to_target"))) is not None
            and days >= lower
            and (upper is None or days <= upper)
        )
        day_buckets.append({"bucket": label, "count": count})

    upside_buckets = []
    for label, lower, upper in [
        ("0-25%", 0, 0.25),
        ("25-50%", 0.25, 0.5),
        ("50-100%", 0.5, 1.0),
        ("100-200%", 1.0, 2.0),
        ("200%+", 2.0, None),
    ]:
        bucket_rows = [
            row
            for row in report_rows
            if (upside := _number(row.get("target_upside_at_pub"))) is not None
            and upside >= lower
            and (upper is None or upside < upper)
        ]
        hit_count = sum(1 for row in bucket_rows if row.get("target_hit"))
        returns = [_number(row.get("current_return")) for row in bucket_rows if _number(row.get("current_return")) is not None]
        upside_buckets.append(
            {
                "bucket": label,
                "count": len(bucket_rows),
                "target_hit_count": hit_count,
                "target_hit_rate": round(hit_count / len(bucket_rows), 6) if bucket_rows else None,
                "avg_current_return": round(sum(returns) / len(returns), 6) if returns else None,
            }
        )

    return {
        "summary": {
            "total_reports": len(report_rows),
            "target_hit_count": len(hit_rows),
            "target_hit_rate": round(len(hit_rows) / len(report_rows), 6) if report_rows else None,
        },
        "days_to_target_buckets": day_buckets,
        "target_upside_buckets": upside_buckets,
    }


def _build_insights(
    overview: dict[str, Any],
    rankings: dict[str, Any],
    target_distribution: dict[str, Any],
    return_windows: list[dict[str, Any]],
    data_quality: dict[str, Any],
) -> list[dict[str, Any]]:
    counts = overview["report_counts"]
    stats = overview["target_stats"]
    hit_summary = target_distribution["summary"]
    valid_90d = [row for row in return_windows if _number(row.get("return_90d")) is not None]
    avg_90d = (
        round(sum(_number(row["return_90d"]) or 0 for row in valid_90d) / len(valid_90d), 6)
        if valid_90d
        else None
    )
    best = (rankings.get("best_current_returns") or [{}])[0]
    worst = (rankings.get("worst_current_returns") or [{}])[0]
    fastest = (rankings.get("fastest_hits") or [{}])[0]
    quality = data_quality["coverage"]
    return [
        {
            "id": "target-hit-rate",
            "title": "목표가 도달률",
            "sentence": f"가격 매칭 리포트 기준 목표가 도달률은 {hit_summary.get('target_hit_rate')}입니다.",
            "metric": hit_summary.get("target_hit_rate"),
            "related_report_ids": [],
        },
        {
            "id": "average-days-to-target",
            "title": "목표가 도달 속도",
            "sentence": f"목표가에 도달한 리포트의 평균 소요 기간은 {stats.get('avg_days_to_target')}일입니다.",
            "metric": stats.get("avg_days_to_target"),
            "related_report_ids": [fastest.get("report_id")] if fastest.get("report_id") else [],
        },
        {
            "id": "average-90d-return",
            "title": "발간 후 90일 성과",
            "sentence": f"90일 가격 데이터가 있는 리포트의 평균 90일 수익률은 {avg_90d}입니다.",
            "metric": avg_90d,
            "related_report_ids": [],
        },
        {
            "id": "best-current-return",
            "title": "현재 수익률 상위 리포트",
            "sentence": f"현재 수익률 최상위 리포트는 {best.get('company')} ({best.get('symbol')})입니다.",
            "metric": best.get("current_return"),
            "related_report_ids": [best.get("report_id")] if best.get("report_id") else [],
        },
        {
            "id": "worst-current-return",
            "title": "하방 리스크 리포트",
            "sentence": f"현재 수익률 최하위 리포트는 {worst.get('company')} ({worst.get('symbol')})입니다.",
            "metric": worst.get("current_return"),
            "related_report_ids": [worst.get("report_id")] if worst.get("report_id") else [],
        },
        {
            "id": "missing-price-coverage",
            "title": "가격 데이터 커버리지",
            "sentence": f"전체 {counts['extracted_reports']}개 리포트 중 가격 누락 심볼은 {counts['missing_price_symbols']}개입니다.",
            "metric": counts["missing_price_symbols"],
            "related_report_ids": [],
        },
        {
            "id": "performance-coverage",
            "title": "성과 산출 커버리지",
            "sentence": f"성과 산출 누락 리포트는 {quality['reports_without_performance']}개입니다.",
            "metric": quality["reports_without_performance"],
            "related_report_ids": [],
        },
    ]


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


def _write_download_csvs(out: Path, report_rows: list[dict[str, Any]], data_quality: dict[str, Any]) -> None:
    report_columns = [
        "report_id",
        "date",
        "company",
        "ticker",
        "exchange",
        "symbol",
        "title",
        "rating",
        "target_price_krw",
        "publication_price_krw",
        "entry_price_krw",
        "target_upside_at_pub",
        "target_hit",
        "target_hit_date",
        "days_to_target",
        "last_close_krw",
        "last_close_date",
        "current_return",
        "peak_return",
        "trough_return",
        "target_gap_pct",
        "caveat_flags",
        "pdf_url",
    ]
    report_download_rows = []
    for row in report_rows:
        csv_row = {column: row.get(column) for column in report_columns}
        csv_row["caveat_flags"] = "|".join(row.get("caveat_flags", []))
        report_download_rows.append(csv_row)
    _write_csv(out / "table-download-reports.csv", report_download_rows, report_columns)

    strategy_rows = _strategy_download_rows()
    strategy_columns = sorted({key for row in strategy_rows for key in row}) if strategy_rows else ["run_id"]
    preferred_strategy_columns = [
        "run_id",
        "trial_number",
        "label",
        "scope",
        "sampler",
        "score",
        "final_equity_krw",
        "net_profit_krw",
        "money_weighted_return",
        "cagr",
        "max_drawdown",
        "trade_count",
        "win_rate",
        "hit_rate",
        "open_positions",
    ]
    strategy_columns = [
        *[column for column in preferred_strategy_columns if column in strategy_columns],
        *[column for column in strategy_columns if column not in preferred_strategy_columns],
    ]
    _write_csv(out / "table-download-strategies.csv", strategy_rows, strategy_columns)

    quality_rows = [
        {"section": "coverage", "metric": metric, "value": value}
        for metric, value in data_quality.get("coverage", {}).items()
    ]
    quality_rows.extend(
        {"section": "missing_symbol", "metric": row.get("symbol"), "value": row.get("symbol")}
        for row in data_quality.get("missing_symbols", [])
    )
    _write_csv(out / "data-quality-download.csv", quality_rows, ["section", "metric", "value"])


def _strategy_download_rows() -> list[dict[str, Any]]:
    trials_csv = Path("data/optuna/exports/trials.csv")
    if trials_csv.exists():
        rows = _records(pd.read_csv(trials_csv, keep_default_na=False))
        return [
            {
                "run_id": f"smic-follower-v1-trial-{row.get('trial_number')}",
                "label": f"smic-follower-v1 trial {row.get('trial_number')}",
                **row,
            }
            for row in rows
        ]
    strategy_path = Path("data/web/strategy-runs.json")
    trials_path = Path("data/web/optuna-trials.json")
    if strategy_path.exists():
        data = _read_json(strategy_path)
        rows = []
        for run in data.get("runs", []) if isinstance(data, dict) else []:
            row = {
                "run_id": run.get("run_id"),
                "trial_number": run.get("trial_number"),
                "label": run.get("label"),
                "scope": run.get("scope"),
                "sampler": run.get("sampler"),
            }
            row.update(run.get("metrics", {}))
            row.update({f"param_{key}": value for key, value in run.get("params", {}).items()})
            rows.append(row)
        return rows
    if trials_path.exists():
        data = _read_json(trials_path)
        return data.get("trials", []) if isinstance(data, dict) else []
    return []


def _write_csv(path: Path, rows: list[dict[str, Any]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(rows, columns=columns)
    frame = frame.map(_csv_cell) if not frame.empty else frame
    frame.to_csv(path, index=False, encoding="utf-8")


def _csv_cell(value: Any) -> Any:
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(_clean(value), ensure_ascii=False, sort_keys=True)
    return _clean(value)


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
