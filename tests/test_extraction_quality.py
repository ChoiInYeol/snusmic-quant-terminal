from pathlib import Path

from snusmic_pipeline.extraction_quality import analyze_extraction_quality
from snusmic_pipeline.models import ExtractedReport, ReportMeta


def report(**kwargs):
    defaults = dict(
        meta=ReportMeta(
            page=1,
            ordinal=1,
            date="2026-01-01T00:00:00",
            title="Equity Research, Sample",
            company="Sample",
            slug="sample",
            post_url="",
            pdf_url="",
        ),
        pdf_path=Path("data/pdfs/sample.pdf"),
        ticker="123456",
        exchange="KRX",
        rating="Buy",
        base_target=10000,
        target_currency="KRW",
        extraction_status="ok",
    )
    defaults.update(kwargs)
    return ExtractedReport(**defaults)


def test_extraction_quality_counts_missing_and_non_buy_rows():
    audit = analyze_extraction_quality(
        [
            report(),
            report(rating="Attention", target_price_detail="rating=Attention; case_1=8000; case_2=10000", note="Case target prices parsed"),
            report(ticker="", base_target=None, extraction_status="needs_review", note="Target price not found"),
        ]
    )

    assert audit["summary"]["ok"] == 2
    assert audit["summary"]["status_needs_review"] == 1
    assert audit["summary"]["review_flagged_rows"] == 2
    assert audit["summary"]["missing_base_target"] == 1
    assert audit["summary"]["non_buy_rating"] == 1
    assert audit["summary"]["case_target_without_explicit_base"] == 1
