from pathlib import Path

from snusmic_pipeline.models import ExtractedReport, ReportMeta
from snusmic_pipeline.sheet_sync import build_payload, build_report_rows


def sample_report():
    return ExtractedReport(
        meta=ReportMeta(
            page=1,
            ordinal=1,
            date="2026-04-16T02:37:54",
            title="Equity Research, SK오션플랜트",
            company="SK오션플랜트",
            slug="equity-research-sk",
            post_url="http://snusmic.com/post/",
            pdf_url="http://snusmic.com/file.pdf",
        ),
        pdf_path=Path("data/pdfs/sample.pdf"),
        ticker="100090",
        exchange="KRX",
        googlefinance_symbol="KRX:100090",
        base_target=41600,
        target_currency="KRW",
        extraction_status="ok",
    )


def test_build_report_rows_includes_googlefinance_formulas():
    rows = build_report_rows([sample_report()])

    assert rows[1][16] == '=IFERROR(GOOGLEFINANCE($H2,"price"),"")'
    assert rows[1][17] == '=IF(OR($M2="",$Q2=""),"",$M2/$Q2-1)'


def test_build_payload_has_three_tabs():
    payload = build_payload([sample_report()], {1: 1}, [])

    assert payload.report_values
    assert payload.summary_values
    assert payload.log_values
