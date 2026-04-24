from __future__ import annotations

from pathlib import Path


class OpenDataLoaderUnavailable(RuntimeError):
    pass


def _find_markdown_for_pdf(output_dir: Path, pdf_path: Path) -> Path | None:
    stem = pdf_path.stem
    candidates = list(output_dir.rglob(f"{stem}.md"))
    if candidates:
        return candidates[0]
    loose = [path for path in output_dir.rglob("*.md") if stem in path.stem]
    return loose[0] if loose else None


def convert_pdfs_to_markdown(
    pdf_paths: list[Path],
    output_dir: Path,
    hybrid: str = "",
) -> dict[Path, str]:
    if not pdf_paths:
        return {}
    try:
        import opendataloader_pdf
    except ImportError as exc:
        raise OpenDataLoaderUnavailable("opendataloader-pdf is not installed") from exc

    output_dir.mkdir(parents=True, exist_ok=True)
    kwargs = {
        "input_path": [str(path) for path in pdf_paths],
        "output_dir": str(output_dir),
        "format": "markdown",
        "image_output": "off",
        "quiet": True,
    }
    if hybrid:
        kwargs["hybrid"] = hybrid

    try:
        opendataloader_pdf.convert(**kwargs)
    except Exception as exc:  # noqa: BLE001 - surface Java/backend/OCR setup failures as one fallback error
        raise OpenDataLoaderUnavailable(str(exc)) from exc

    extracted: dict[Path, str] = {}
    for pdf_path in pdf_paths:
        markdown_path = _find_markdown_for_pdf(output_dir, pdf_path)
        if markdown_path and markdown_path.exists():
            extracted[pdf_path] = markdown_path.read_text(encoding="utf-8", errors="replace")
    return extracted
