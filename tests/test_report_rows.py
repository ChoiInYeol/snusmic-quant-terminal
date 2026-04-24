from pathlib import Path

from snusmic_pipeline.cli import build_report_rows
from snusmic_pipeline.models import ExtractedReport, ReportMeta


def sample_report() -> ExtractedReport:
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
        base_target=41600,
        target_currency="KRW",
        extraction_status="ok",
    )


def test_report_rows_are_local_archive_rows_without_sheet_formulas():
    rows = build_report_rows([sample_report()])

    assert rows[0] == [
        "페이지",
        "순번",
        "게시일",
        "리포트명",
        "종목명",
        "티커",
        "거래소",
        "PDF URL",
        "PDF 파일명",
        "리포트 현재주가",
        "Bear 목표가",
        "Base 목표가",
        "Bull 목표가",
        "목표가 통화",
        "투자포인트",
        "추출 상태",
        "비고",
    ]
    assert all(not str(cell).startswith("=") for row in rows for cell in row)
