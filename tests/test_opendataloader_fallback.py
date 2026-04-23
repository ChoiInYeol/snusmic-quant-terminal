from pathlib import Path

from snusmic_pipeline.opendataloader_fallback import _find_markdown_for_pdf


def test_find_markdown_for_pdf_matches_stem(tmp_path: Path):
    pdf = tmp_path / "sample.pdf"
    pdf.write_bytes(b"%PDF")
    out = tmp_path / "out"
    out.mkdir()
    markdown = out / "sample.md"
    markdown.write_text("content", encoding="utf-8")

    assert _find_markdown_for_pdf(out, pdf) == markdown
