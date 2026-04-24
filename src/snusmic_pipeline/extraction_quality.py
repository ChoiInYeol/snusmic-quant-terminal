from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from .models import ExtractedReport

BUY_RATINGS = {"Buy", "Strong Buy"}


def row_reasons(report: ExtractedReport) -> list[str]:
    reasons: list[str] = []
    if report.extraction_status != "ok":
        reasons.append(f"status:{report.extraction_status}")
    if not report.ticker:
        reasons.append("missing_ticker")
    if not report.base_target:
        reasons.append("missing_base_target")
    if report.report_current_price and report.base_target and report.report_current_price == report.base_target:
        reasons.append("current_equals_base_target")
    if not report.rating:
        reasons.append("missing_rating")
    elif report.rating not in BUY_RATINGS:
        reasons.append(f"non_buy_rating:{report.rating}")
    detail = report.target_price_detail.lower()
    if "case_" in detail and "base=" not in detail:
        reasons.append("case_target_without_explicit_base")
    if report.note:
        note = report.note.lower()
        if "target price not found" in note and not report.base_target:
            reasons.append("note_target_not_found")
        if "exchange not mapped" in note:
            reasons.append("note_exchange_not_mapped")
        if "case target prices parsed" in note:
            reasons.append("note_case_target_ambiguous")
    return sorted(set(reasons))


def analyze_extraction_quality(reports: list[ExtractedReport]) -> dict[str, Any]:
    status_counts = Counter(report.extraction_status or "blank" for report in reports)
    rating_counts = Counter(report.rating or "missing" for report in reports)
    currency_counts = Counter(report.target_currency or "missing" for report in reports)
    reason_counts: Counter[str] = Counter()
    page_counts: dict[int, Counter[str]] = defaultdict(Counter)
    review_rows: list[dict[str, Any]] = []

    for report in reports:
        reasons = row_reasons(report)
        reason_counts.update(reasons)
        page_counts[int(report.meta.page)][report.extraction_status or "blank"] += 1
        if reasons:
            review_rows.append(
                {
                    "page": report.meta.page,
                    "ordinal": report.meta.ordinal,
                    "date": report.meta.date,
                    "company": report.meta.company,
                    "title": report.meta.title,
                    "ticker": report.ticker,
                    "rating": report.rating,
                    "base_target": report.base_target,
                    "target_detail": report.target_price_detail,
                    "status": report.extraction_status,
                    "note": report.note,
                    "reasons": reasons,
                }
            )

    return {
        "total_reports": len(reports),
        "status_counts": dict(sorted(status_counts.items())),
        "rating_counts": dict(sorted(rating_counts.items())),
        "currency_counts": dict(sorted(currency_counts.items())),
        "reason_counts": dict(sorted(reason_counts.items())),
        "review_rows": review_rows,
        "page_status_counts": {str(page): dict(sorted(counter.items())) for page, counter in sorted(page_counts.items())},
        "summary": {
            "ok": status_counts.get("ok", 0),
            "status_needs_review": status_counts.get("needs_review", 0),
            "review_flagged_rows": len(review_rows),
            "missing_base_target": reason_counts.get("missing_base_target", 0),
            "current_equals_base_target": reason_counts.get("current_equals_base_target", 0),
            "missing_rating": reason_counts.get("missing_rating", 0),
            "non_buy_rating": sum(count for reason, count in reason_counts.items() if reason.startswith("non_buy_rating:")),
            "case_target_without_explicit_base": reason_counts.get("case_target_without_explicit_base", 0),
        },
    }
