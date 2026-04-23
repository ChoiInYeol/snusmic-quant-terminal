from __future__ import annotations

import argparse
import csv
import json
import os
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .download_pdfs import download_all
from .extract_pdf import extract_report
from .fetch_index import fetch_reports, parse_pages
from .models import DownloadedPdf, ExtractedReport
from .opendataloader_fallback import OpenDataLoaderUnavailable, convert_pdfs_to_markdown
from .sheet_sync import build_payload, sync_google_sheet


def _json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    return value


def write_manifest(downloads: list[DownloadedPdf], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = []
    for download in downloads:
        item = asdict(download.meta)
        item.update({"pdf_path": str(download.path) if download.path else "", "sha256": download.sha256, "download_status": download.status, "download_note": download.note})
        data.append(item)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=_json_default) + "\n", encoding="utf-8")


def write_csv(reports: list[ExtractedReport], path: Path) -> None:
    from .sheet_sync import build_report_rows

    path.parent.mkdir(parents=True, exist_ok=True)
    rows = build_report_rows(reports)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerows(rows)


def page_counts(reports: list[ExtractedReport]) -> dict[int, int]:
    counts: dict[int, int] = {}
    for report in reports:
        counts[report.meta.page] = counts.get(report.meta.page, 0) + 1
    return counts


def apply_opendataloader_fallback(
    reports: list[ExtractedReport],
    output_dir: Path,
    hybrid: str = "",
) -> list[str]:
    from .extract_pdf import parse_report_text

    candidates = [report for report in reports if report.pdf_path and report.extraction_status != "ok"]
    if not candidates:
        return []
    try:
        markdown_by_path = convert_pdfs_to_markdown([report.pdf_path for report in candidates if report.pdf_path], output_dir=output_dir, hybrid=hybrid)
    except OpenDataLoaderUnavailable as exc:
        return [f"OpenDataLoader fallback unavailable: {exc}"]

    logs: list[str] = []
    for report in candidates:
        if not report.pdf_path:
            continue
        markdown = markdown_by_path.get(report.pdf_path)
        if not markdown:
            logs.append(f"OpenDataLoader produced no markdown for {report.pdf_filename}")
            continue
        parsed = parse_report_text(markdown, fallback_company=report.meta.company)
        if parsed["status"] == "ok" or (not report.ticker and parsed["ticker"]):
            report.ticker = str(parsed["ticker"])
            report.exchange = str(parsed["exchange"])
            report.googlefinance_symbol = str(parsed["googlefinance_symbol"])
            report.report_current_price = parsed["report_current_price"]  # type: ignore[assignment]
            report.bear_target = parsed["bear_target"]  # type: ignore[assignment]
            report.base_target = parsed["base_target"]  # type: ignore[assignment]
            report.bull_target = parsed["bull_target"]  # type: ignore[assignment]
            report.target_currency = str(parsed["target_currency"])
            report.extraction_status = str(parsed["status"])
            note = str(parsed["note"])
            report.note = f"OpenDataLoader fallback; {note}".strip("; ")
            report.raw_matches = parsed["raw_matches"]  # type: ignore[assignment]
    return logs


def run_sync(args: argparse.Namespace) -> int:
    data_dir = Path(args.data_dir)
    pdf_dir = data_dir / "pdfs"
    pages = parse_pages(args.pages)
    logs: list[str] = []

    metas = fetch_reports(pages)
    downloads = download_all(metas, pdf_dir=pdf_dir, force=args.force)
    extracted = [extract_report(download, max_pages=args.max_pages) for download in downloads]
    if args.opendataloader_fallback:
        logs.extend(
            apply_opendataloader_fallback(
                extracted,
                output_dir=Path(args.opendataloader_output_dir),
                hybrid=args.opendataloader_hybrid,
            )
        )

    write_manifest(downloads, data_dir / "manifest.json")
    write_csv(extracted, data_dir / "extracted_reports.csv")

    payload = build_payload(extracted, page_counts(extracted), logs)
    sheet_id = args.sheet_id or os.environ.get("GOOGLE_SHEET_ID", "")
    if args.skip_sheet:
        logs.append("Sheet sync skipped by --skip-sheet")
    elif sheet_id:
        sync_google_sheet(sheet_id, payload)
    else:
        logs.append("Sheet sync skipped because no --sheet-id or GOOGLE_SHEET_ID was provided")

    print(f"Reports fetched: {len(metas)}")
    print(f"PDFs available: {sum(1 for item in downloads if item.path)}")
    print(f"Extracted OK: {sum(1 for item in extracted if item.extraction_status == 'ok')}")
    print(f"Needs review: {sum(1 for item in extracted if item.extraction_status != 'ok')}")
    for message in logs:
        print(message)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Collect SNUSMIC PDFs and sync Google Sheets.")
    subparsers = parser.add_subparsers(dest="command")

    sync = subparsers.add_parser("sync", help="Fetch reports, download PDFs, extract rows, and optionally sync Sheets.")
    sync.add_argument("--pages", default="1-5", help="Page range/list, for example 1-5 or 1,3,5.")
    sync.add_argument("--data-dir", default="data", help="Output data directory.")
    sync.add_argument("--sheet-id", default="", help="Google Sheets spreadsheet id. Defaults to GOOGLE_SHEET_ID.")
    sync.add_argument("--skip-sheet", action="store_true", help="Only write local PDF/CSV/manifest outputs.")
    sync.add_argument("--force", action="store_true", help="Re-download PDFs even when a local copy exists.")
    sync.add_argument("--max-pages", type=int, default=4, help="Maximum PDF pages to parse for target-price extraction.")
    sync.add_argument("--opendataloader-fallback", action=argparse.BooleanOptionalAction, default=True, help="Use opendataloader-pdf for reports that pypdf cannot parse cleanly.")
    sync.add_argument("--opendataloader-output-dir", default="data/opendataloader", help="OpenDataLoader markdown output directory.")
    sync.add_argument("--opendataloader-hybrid", default=os.environ.get("OPENDATALOADER_HYBRID", ""), help="Optional OpenDataLoader hybrid mode, for example docling-fast.")
    sync.set_defaults(func=run_sync)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return 2
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
