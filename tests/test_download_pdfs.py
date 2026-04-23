from snusmic_pipeline.download_pdfs import safe_pdf_filename
from snusmic_pipeline.models import ReportMeta


def test_safe_pdf_filename_decodes_korean_slug():
    meta = ReportMeta(
        page=1,
        ordinal=1,
        date="2025-11-11T04:41:17",
        title="Equity Research, 지투지바이오",
        company="지투지바이오",
        slug="equity-research-%ec%a7%80%ed%88%ac%ec%a7%80%eb%b0%94%ec%9d%b4%ec%98%a4",
        post_url="http://snusmic.com/equity-research/",
        pdf_url="http://snusmic.com/file.pdf",
    )

    assert safe_pdf_filename(meta) == "2025-11-11_equity-research-지투지바이오.pdf"
