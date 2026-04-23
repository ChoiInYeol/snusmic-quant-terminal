from pathlib import Path

from snusmic_pipeline.markdown_export import markdown_path_for_pdf


def test_markdown_path_for_pdf_uses_pdf_stem(tmp_path: Path):
    assert markdown_path_for_pdf(Path("data/pdfs/report.pdf"), tmp_path) == tmp_path / "report.md"
