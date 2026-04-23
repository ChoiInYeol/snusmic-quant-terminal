from __future__ import annotations

from pathlib import Path

from .extract_pdf import extract_text_from_pdf
from .models import ExtractedReport
from .opendataloader_fallback import OpenDataLoaderUnavailable, convert_pdfs_to_markdown


def markdown_path_for_pdf(pdf_path: Path, output_dir: Path) -> Path:
    return output_dir / f"{pdf_path.stem}.md"


def fallback_markdown(report: ExtractedReport) -> str:
    if not report.pdf_path:
        return ""
    text = extract_text_from_pdf(report.pdf_path)
    title = report.meta.title or report.meta.company or report.pdf_path.stem
    return (
        f"# {title}\n\n"
        f"- Company: {report.meta.company}\n"
        f"- Report date: {report.meta.date}\n"
        f"- Ticker: {report.ticker}\n"
        f"- Source PDF: {report.meta.pdf_url}\n\n"
        "> 해당 .md 을 ChatGPT, Claude에게 입력하여 인사이트를 얻으세요.\n\n"
        "## Extracted PDF Text\n\n"
        f"{text.strip()}\n"
    )


def export_markdown(
    reports: list[ExtractedReport],
    output_dir: Path,
    use_opendataloader: bool = True,
    hybrid: str = "",
) -> list[str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    logs: list[str] = []
    pdf_reports = [report for report in reports if report.pdf_path and report.pdf_path.exists()]

    converted: dict[Path, str] = {}
    if use_opendataloader and pdf_reports:
        try:
            converted = convert_pdfs_to_markdown([report.pdf_path for report in pdf_reports if report.pdf_path], output_dir=output_dir, hybrid=hybrid)
        except OpenDataLoaderUnavailable as exc:
            logs.append(f"OpenDataLoader markdown export unavailable; falling back to pypdf text: {exc}")

    for report in pdf_reports:
        assert report.pdf_path is not None
        target = markdown_path_for_pdf(report.pdf_path, output_dir)
        if report.pdf_path in converted:
            body = converted[report.pdf_path]
            if "해당 .md 을 ChatGPT, Claude에게 입력하여 인사이트를 얻으세요." not in body:
                body = "> 해당 .md 을 ChatGPT, Claude에게 입력하여 인사이트를 얻으세요.\n\n" + body
            target.write_text(body, encoding="utf-8")
        elif not target.exists():
            target.write_text(fallback_markdown(report), encoding="utf-8")
    logs.append(f"Markdown files available: {len(list(output_dir.glob('*.md')))}")
    return logs
