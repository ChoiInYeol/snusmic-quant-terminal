from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from .change_detection import new_report_urls
from .download_pdfs import download_all
from .extract_pdf import extract_report, extract_text_from_pdf, parse_report_text
from .extraction_quality import analyze_extraction_quality
from .fetch_index import fetch_reports, parse_pages
from .markdown_export import export_markdown
from .models import DownloadedPdf, ExtractedReport, ReportMeta
from .opendataloader_fallback import OpenDataLoaderUnavailable, convert_pdfs_to_markdown
from .sim.warehouse import build_warehouse, refresh_price_history
from .web_artifacts import ExportInputs, check_web_artifacts, export_web_artifacts

REPORT_HEADERS = [
    "페이지",
    "순번",
    "게시일",
    "리포트명",
    "종목명",
    "티커",
    "거래소",
    "투자의견",
    "PDF URL",
    "PDF 파일명",
    "리포트 현재주가",
    "Bear 목표가",
    "Base 목표가",
    "Bull 목표가",
    "목표가 통화",
    "목표가 세부",
    "투자포인트",
    "추출 상태",
    "비고",
]

REPO_ROOT = Path(__file__).resolve().parents[2]
PERSONA_SIM_SCRIPT = REPO_ROOT / "scripts" / "run_persona_sim.py"


def _json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    return value


def write_manifest(downloads: list[DownloadedPdf], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = []
    for download in downloads:
        item = download.meta.model_dump(mode="json")
        item.update(
            {
                "pdf_path": str(download.path) if download.path else "",
                "sha256": download.sha256,
                "download_status": download.status,
                "download_note": download.note,
            }
        )
        data.append(item)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, default=_json_default) + "\n", encoding="utf-8"
    )


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, default=_json_default) + "\n", encoding="utf-8"
    )


def _number_or_blank(value: float | None) -> float | str:
    return "" if value is None else value


def build_report_rows(reports: list[ExtractedReport]) -> list[list[Any]]:
    rows: list[list[Any]] = [REPORT_HEADERS]
    for report in reports:
        rows.append(
            [
                report.meta.page,
                report.meta.ordinal,
                report.meta.date,
                report.meta.title,
                report.meta.company,
                report.ticker,
                report.exchange,
                report.rating,
                report.meta.pdf_url,
                report.pdf_filename,
                _number_or_blank(report.report_current_price),
                _number_or_blank(report.bear_target),
                _number_or_blank(report.base_target),
                _number_or_blank(report.bull_target),
                report.target_currency,
                report.target_price_detail,
                report.investment_points,
                report.extraction_status,
                report.note,
            ]
        )
    return rows


def write_csv(reports: list[ExtractedReport], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = build_report_rows(reports)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerows(rows)


def read_extracted_reports_csv(path: Path) -> list[ExtractedReport]:
    if not path.exists():
        raise FileNotFoundError(f"Missing extracted reports CSV: {path}")
    reports: list[ExtractedReport] = []
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            meta = ReportMeta(
                page=int(row.get("페이지") or 0),
                ordinal=int(row.get("순번") or 0),
                date=row.get("게시일", ""),
                title=row.get("리포트명", ""),
                company=row.get("종목명", ""),
                slug="",
                post_url="",
                pdf_url=row.get("PDF URL", ""),
            )
            pdf_name = row.get("PDF 파일명", "")
            report = ExtractedReport(
                meta=meta,
                pdf_path=Path("data/pdfs") / pdf_name if pdf_name else None,
                report_current_price=_float_or_none(row.get("리포트 현재주가")),
                ticker=row.get("티커", ""),
                exchange=row.get("거래소", ""),
                rating=row.get("투자의견", ""),
                bear_target=_float_or_none(row.get("Bear 목표가")),
                base_target=_float_or_none(row.get("Base 목표가")),
                bull_target=_float_or_none(row.get("Bull 목표가")),
                target_currency=row.get("목표가 통화", ""),
                target_price_detail=row.get("목표가 세부", ""),
                investment_points=row.get("투자포인트", ""),
                extraction_status=row.get("추출 상태", ""),
                note=row.get("비고", ""),
            )
            reports.append(report)
    return reports


def _float_or_none(value: str | None) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def apply_opendataloader_fallback(
    reports: list[ExtractedReport],
    output_dir: Path,
    hybrid: str = "",
    force_all: bool = False,
) -> list[str]:
    candidates = [
        report for report in reports if report.pdf_path and (force_all or report.extraction_status != "ok")
    ]
    if not candidates:
        return []
    try:
        markdown_by_path = convert_pdfs_to_markdown(
            [report.pdf_path for report in candidates if report.pdf_path],
            output_dir=output_dir,
            hybrid=hybrid,
        )
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
            apply_parsed_report(report, parsed, source="OpenDataLoader fallback")
    return logs


def apply_parsed_report(report: ExtractedReport, parsed: dict[str, object], source: str = "") -> None:
    report.ticker = str(parsed["ticker"])
    report.exchange = str(parsed["exchange"])
    report.rating = str(parsed.get("rating", ""))
    report.report_current_price = parsed["report_current_price"]  # type: ignore[assignment]
    report.bear_target = parsed["bear_target"]  # type: ignore[assignment]
    report.base_target = parsed["base_target"]  # type: ignore[assignment]
    report.bull_target = parsed["bull_target"]  # type: ignore[assignment]
    report.target_currency = str(parsed["target_currency"])
    report.target_price_detail = str(parsed.get("target_price_detail", ""))
    report.investment_points = str(parsed["investment_points"])
    report.extraction_status = str(parsed["status"])
    note = str(parsed["note"])
    report.note = f"{source}; {note}".strip("; ") if source else note
    report.raw_matches = parsed["raw_matches"]  # type: ignore[assignment]


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
                force_all=args.opendataloader_force_all,
            )
        )

    write_manifest(downloads, data_dir / "manifest.json")
    write_csv(extracted, data_dir / "extracted_reports.csv")
    if args.markdown:
        logs.extend(
            export_markdown(
                extracted,
                data_dir / "markdown",
                use_opendataloader=args.markdown_opendataloader,
                hybrid=args.opendataloader_hybrid,
                force=args.force_markdown,
            )
        )

    print(f"Reports fetched: {len(metas)}")
    print(f"PDFs available: {sum(1 for item in downloads if item.path)}")
    print(f"Extracted OK: {sum(1 for item in extracted if item.extraction_status == 'ok')}")
    print(f"Needs review: {sum(1 for item in extracted if item.extraction_status != 'ok')}")
    for message in logs:
        print(message)
    return 0


def run_ocr_reextract(args: argparse.Namespace) -> int:
    data_dir = Path(args.data_dir)
    markdown_dir = data_dir / "markdown"
    reports = read_extracted_reports_csv(data_dir / "extracted_reports.csv")
    logs: list[str] = []
    if args.force_opendataloader:
        logs.extend(
            export_markdown(
                reports,
                markdown_dir,
                use_opendataloader=True,
                hybrid=args.opendataloader_hybrid,
                force=True,
            )
        )

    updated = 0
    missing_markdown = 0
    for report in reports:
        previous = {
            "ticker": report.ticker,
            "exchange": report.exchange,
            "report_current_price": report.report_current_price,
            "bear_target": report.bear_target,
            "base_target": report.base_target,
            "bull_target": report.bull_target,
            "target_currency": report.target_currency,
            "target_price_detail": report.target_price_detail,
            "status": report.extraction_status,
            "note": report.note,
        }
        markdown_path = markdown_dir / f"{report.pdf_path.stem}.md" if report.pdf_path else None
        text = ""
        source = "markdown reextract"
        if markdown_path and markdown_path.exists():
            text = markdown_path.read_text(encoding="utf-8", errors="replace")
        elif args.allow_pypdf_fallback and report.pdf_path and report.pdf_path.exists():
            text = extract_text_from_pdf(report.pdf_path, max_pages=args.max_pages)
            source = "pypdf reextract"
        else:
            missing_markdown += 1
            continue
        parsed = parse_report_text(text, fallback_company=report.meta.company)
        apply_parsed_report(report, parsed, source=source)
        if (
            args.preserve_existing_targets
            and report.base_target is None
            and previous["base_target"] is not None
        ):
            report.report_current_price = previous["report_current_price"]  # type: ignore[assignment]
            report.bear_target = previous["bear_target"]  # type: ignore[assignment]
            report.base_target = previous["base_target"]  # type: ignore[assignment]
            report.bull_target = previous["bull_target"]  # type: ignore[assignment]
            report.target_currency = str(previous["target_currency"])
            existing_detail = str(previous["target_price_detail"])
            report.target_price_detail = existing_detail or f"base={report.base_target:g}"
            if not report.ticker and previous["ticker"]:
                report.ticker = str(previous["ticker"])
                report.exchange = str(previous["exchange"])
            if report.ticker:
                report.extraction_status = "ok"
            preserved_note = "OpenDataLoader target missing; preserved previous target fields"
            report.note = f"{report.note}; {preserved_note}".strip("; ")
        updated += 1

    write_csv(reports, data_dir / "extracted_reports.csv")
    if args.audit:
        audit = analyze_extraction_quality(reports)
        write_json(Path(args.audit_output), audit)
        print_quality_summary(audit)
    print(f"Reports loaded: {len(reports)}")
    print(f"Reports re-extracted: {updated}")
    print(f"Missing markdown/text: {missing_markdown}")
    for message in logs:
        print(message)
    return 0


def print_quality_summary(audit: dict[str, Any]) -> None:
    summary = audit.get("summary", {})
    print("Extraction quality summary")
    for key in [
        "ok",
        "status_needs_review",
        "review_flagged_rows",
        "missing_base_target",
        "current_equals_base_target",
        "missing_rating",
        "non_buy_rating",
        "case_target_without_explicit_base",
    ]:
        print(f"{key}: {summary.get(key, 0)}")


def run_audit_extraction(args: argparse.Namespace) -> int:
    reports = read_extracted_reports_csv(Path(args.data_dir) / "extracted_reports.csv")
    audit = analyze_extraction_quality(reports)
    if args.output:
        write_json(Path(args.output), audit)
    print_quality_summary(audit)
    if args.show_rows:
        for row in audit["review_rows"][: args.show_rows]:
            reasons = ", ".join(row["reasons"])
            print(f"{row['date']} | p{row['page']} #{row['ordinal']} | {row['company']} | {reasons}")
    return 0


def run_check_new(args: argparse.Namespace) -> int:
    urls = new_report_urls(Path(args.manifest))
    has_new = bool(urls)
    print("has_new=true" if has_new else "has_new=false")
    for url in urls:
        print(url)
    if args.github_output:
        with Path(args.github_output).open("a", encoding="utf-8") as handle:
            handle.write(f"has_new={'true' if has_new else 'false'}\n")
    return 0


def run_refresh_market(args: argparse.Namespace) -> int:
    data_dir = Path(args.data_dir)
    warehouse_dir = Path(args.warehouse_dir)
    counts = build_warehouse(data_dir, warehouse_dir)
    prices = refresh_price_history(data_dir, warehouse_dir)
    print(f"Reports loaded: {counts.get('reports', 0)}")
    print(f"Daily price rows: {len(prices)}")
    print(f"Symbols: {prices['symbol'].nunique() if not prices.empty else 0}")
    return 0


def run_export_markdown(args: argparse.Namespace) -> int:
    data_dir = Path(args.data_dir)
    reports = read_extracted_reports_csv(data_dir / "extracted_reports.csv")
    logs = export_markdown(
        reports,
        data_dir / "markdown",
        use_opendataloader=args.markdown_opendataloader,
        hybrid=args.opendataloader_hybrid,
        force=args.force,
    )
    for message in logs:
        print(message)
    return 0


def run_build_warehouse(args: argparse.Namespace) -> int:
    counts = build_warehouse(Path(args.data_dir), Path(args.warehouse_dir))
    for table, count in sorted(counts.items()):
        print(f"{table}: {count}")
    return 0


def run_refresh_prices(args: argparse.Namespace) -> int:
    symbols = [item.strip() for item in args.symbols.split(",") if item.strip()] if args.symbols else None
    prices = refresh_price_history(
        Path(args.data_dir), Path(args.warehouse_dir), symbols=symbols, force_full=args.force_full
    )
    print(f"Daily price rows: {len(prices)}")
    print(f"Symbols: {prices['symbol'].nunique() if not prices.empty else 0}")
    return 0


def run_export_web(args: argparse.Namespace) -> int:
    inputs = ExportInputs(
        warehouse=Path(args.warehouse),
        sim=Path(args.sim),
        out=Path(args.out),
        extraction_quality=Path(args.extraction_quality),
    )
    result = check_web_artifacts(inputs) if args.check else export_web_artifacts(inputs)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def run_persona_sim(args: argparse.Namespace) -> int:
    """Thin wrapper around ``scripts/run_persona_sim.py``.

    Forwards the standard CLI arguments so ``python -m snusmic_pipeline run-sim``
    behaves identically to the standalone script callers already use.
    """
    forwarded: list[str] = [
        "--start",
        args.start,
        "--end",
        args.end,
        "--warehouse",
        str(args.warehouse),
        "--out",
        str(args.out),
    ]
    if args.refresh_benchmark:
        forwarded.append("--refresh-benchmark")
    completed = subprocess.run(
        [sys.executable, str(PERSONA_SIM_SCRIPT), *forwarded],
        check=False,
    )
    return completed.returncode


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Collect SNUSMIC PDFs, extract target prices, and run persona simulations."
    )
    subparsers = parser.add_subparsers(dest="command")

    sync = subparsers.add_parser("sync", help="Fetch reports, download PDFs, and extract local archive rows.")
    sync.add_argument("--pages", default="1-7", help="Page range/list, for example 1-7 or 1,3,5.")
    sync.add_argument("--data-dir", default="data", help="Output data directory.")
    sync.add_argument("--force", action="store_true", help="Re-download PDFs even when a local copy exists.")
    sync.add_argument(
        "--max-pages", type=int, default=4, help="Maximum PDF pages to parse for target-price extraction."
    )
    sync.add_argument(
        "--opendataloader-fallback",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Use opendataloader-pdf for reports that pypdf cannot parse cleanly.",
    )
    sync.add_argument(
        "--opendataloader-force-all",
        action="store_true",
        help="Run OpenDataLoader fallback over every report, not only needs-review rows.",
    )
    sync.add_argument(
        "--opendataloader-output-dir",
        default="data/opendataloader",
        help="OpenDataLoader markdown output directory.",
    )
    sync.add_argument(
        "--opendataloader-hybrid",
        default=os.environ.get("OPENDATALOADER_HYBRID", ""),
        help="Optional OpenDataLoader hybrid mode, for example docling-fast.",
    )
    sync.add_argument(
        "--markdown",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Export one markdown file per PDF.",
    )
    sync.add_argument(
        "--markdown-opendataloader",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Try opendataloader-pdf before falling back to pypdf text.",
    )
    sync.add_argument(
        "--force-markdown", action="store_true", help="Overwrite existing markdown during markdown export."
    )
    sync.set_defaults(func=run_sync)

    check_new = subparsers.add_parser(
        "check-new", help="Check page one for new reports before running a heavy sync."
    )
    check_new.add_argument("--manifest", default="data/manifest.json")
    check_new.add_argument("--github-output", default="")
    check_new.set_defaults(func=run_check_new)

    refresh_market = subparsers.add_parser(
        "refresh-market",
        help="Build the warehouse and refresh yfinance OHLCV market data.",
    )
    refresh_market.add_argument("--data-dir", default="data")
    refresh_market.add_argument("--warehouse-dir", default="data/warehouse")
    refresh_market.set_defaults(func=run_refresh_market)

    export_md = subparsers.add_parser(
        "export-markdown", help="Export one markdown file per committed PDF/report row."
    )
    export_md.add_argument("--data-dir", default="data")
    export_md.add_argument("--markdown-opendataloader", action=argparse.BooleanOptionalAction, default=True)
    export_md.add_argument("--opendataloader-hybrid", default=os.environ.get("OPENDATALOADER_HYBRID", ""))
    export_md.add_argument("--force", action="store_true", help="Overwrite existing markdown files.")
    export_md.set_defaults(func=run_export_markdown)

    ocr = subparsers.add_parser(
        "ocr-reextract", help="Force OpenDataLoader markdown export and re-extract committed report rows."
    )
    ocr.add_argument("--data-dir", default="data")
    ocr.add_argument(
        "--force-opendataloader",
        action="store_true",
        help="Regenerate markdown for every PDF with OpenDataLoader before parsing.",
    )
    ocr.add_argument("--opendataloader-hybrid", default=os.environ.get("OPENDATALOADER_HYBRID", ""))
    ocr.add_argument("--allow-pypdf-fallback", action=argparse.BooleanOptionalAction, default=True)
    ocr.add_argument("--preserve-existing-targets", action=argparse.BooleanOptionalAction, default=True)
    ocr.add_argument("--max-pages", type=int, default=4)
    ocr.add_argument("--audit", action=argparse.BooleanOptionalAction, default=True)
    ocr.add_argument("--audit-output", default="data/extraction_quality.json")
    ocr.set_defaults(func=run_ocr_reextract)

    audit = subparsers.add_parser(
        "audit-extraction", help="Create extraction quality statistics from extracted_reports.csv."
    )
    audit.add_argument("--data-dir", default="data")
    audit.add_argument("--output", default="data/extraction_quality.json")
    audit.add_argument("--show-rows", type=int, default=20)
    audit.set_defaults(func=run_audit_extraction)

    warehouse = subparsers.add_parser(
        "build-warehouse", help="Normalize report metadata into the sim warehouse."
    )
    warehouse.add_argument("--data-dir", default="data")
    warehouse.add_argument("--warehouse-dir", default="data/warehouse")
    warehouse.set_defaults(func=run_build_warehouse)

    refresh_prices = subparsers.add_parser(
        "refresh-prices", help="Download yfinance OHLCV history into the sim warehouse."
    )
    refresh_prices.add_argument("--data-dir", default="data")
    refresh_prices.add_argument("--warehouse-dir", default="data/warehouse")
    refresh_prices.add_argument(
        "--symbols", default="", help="Optional comma-separated yfinance symbols for a partial refresh."
    )
    refresh_prices.add_argument(
        "--force-full",
        action="store_true",
        help="Re-fetch the full available history for selected symbols instead of only new bars.",
    )
    refresh_prices.set_defaults(func=run_refresh_prices)

    export_web = subparsers.add_parser(
        "export-web", help="Export static JSON artifacts for the Next.js web showcase."
    )
    export_web.add_argument("--warehouse", default=str(REPO_ROOT / "data" / "warehouse"))
    export_web.add_argument("--sim", default=str(REPO_ROOT / "data" / "sim"))
    export_web.add_argument("--out", default=str(REPO_ROOT / "data" / "web"))
    export_web.add_argument(
        "--extraction-quality", default=str(REPO_ROOT / "data" / "extraction_quality.json")
    )
    export_web.add_argument("--check", action="store_true", help="Verify deterministic artifact output.")
    export_web.set_defaults(func=run_export_web)

    sim = subparsers.add_parser(
        "run-sim", help="Run the persona simulation (delegates to scripts/run_persona_sim.py)."
    )
    sim.add_argument("--start", default="2021-01-04")
    sim.add_argument("--end", default="2026-04-15")
    sim.add_argument("--warehouse", default=str(REPO_ROOT / "data" / "warehouse"))
    sim.add_argument("--out", default=str(REPO_ROOT / "data" / "sim"))
    sim.add_argument(
        "--refresh-benchmark",
        action="store_true",
        help="Force re-download of the All-Weather benchmark prices.",
    )
    sim.set_defaults(func=run_persona_sim)

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
