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
from .models import DownloadedPdf, ExtractedReport, ReportMeta
from .markdown_export import export_markdown
from .opendataloader_fallback import OpenDataLoaderUnavailable, convert_pdfs_to_markdown
from .quant import compute_portfolio_backtests, compute_price_metrics, dataclass_rows
from .change_detection import new_report_urls
from .site_builder import build_site
from .backtest import build_warehouse, export_dashboard_data, refresh_price_history, run_default_backtests
from .backtest.warehouse import optimize_strategies

REPORT_HEADERS = [
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


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=_json_default) + "\n", encoding="utf-8")


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
                report.meta.pdf_url,
                report.pdf_filename,
                _number_or_blank(report.report_current_price),
                _number_or_blank(report.bear_target),
                _number_or_blank(report.base_target),
                _number_or_blank(report.bull_target),
                report.target_currency,
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
        writer = csv.writer(handle)
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
                bear_target=_float_or_none(row.get("Bear 목표가")),
                base_target=_float_or_none(row.get("Base 목표가")),
                bull_target=_float_or_none(row.get("Bull 목표가")),
                target_currency=row.get("목표가 통화", ""),
                investment_points=row.get("투자포인트", ""),
                extraction_status=row.get("추출 상태", ""),
                note=row.get("비고", ""),
            )
            reports.append(report)
    return reports


def _float_or_none(value: str | None) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except ValueError:
        return None


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
            report.report_current_price = parsed["report_current_price"]  # type: ignore[assignment]
            report.bear_target = parsed["bear_target"]  # type: ignore[assignment]
            report.base_target = parsed["base_target"]  # type: ignore[assignment]
            report.bull_target = parsed["bull_target"]  # type: ignore[assignment]
            report.target_currency = str(parsed["target_currency"])
            report.investment_points = str(parsed["investment_points"])
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
    if args.markdown:
        logs.extend(export_markdown(extracted, data_dir / "markdown", use_opendataloader=args.markdown_opendataloader, hybrid=args.opendataloader_hybrid))
    if args.market_data:
        price_metrics = compute_price_metrics(extracted)
        portfolio_backtests = compute_portfolio_backtests(extracted, price_metrics)
    else:
        price_metrics = []
        portfolio_backtests = []
        logs.append("Market data skipped by --no-market-data")
    write_json(data_dir / "price_metrics.json", dataclass_rows(price_metrics))
    write_json(data_dir / "portfolio_backtests.json", dataclass_rows(portfolio_backtests))

    print(f"Reports fetched: {len(metas)}")
    print(f"PDFs available: {sum(1 for item in downloads if item.path)}")
    print(f"Extracted OK: {sum(1 for item in extracted if item.extraction_status == 'ok')}")
    print(f"Needs review: {sum(1 for item in extracted if item.extraction_status != 'ok')}")
    for message in logs:
        print(message)
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


def run_build_site(args: argparse.Namespace) -> int:
    build_site(Path(args.data_dir), Path(args.public_dir))
    print(f"Built site at {args.public_dir}")
    return 0


def run_refresh_market(args: argparse.Namespace) -> int:
    data_dir = Path(args.data_dir)
    reports = read_extracted_reports_csv(data_dir / "extracted_reports.csv")
    price_metrics = compute_price_metrics(reports)
    portfolio_backtests = compute_portfolio_backtests(reports, price_metrics)
    write_json(data_dir / "price_metrics.json", dataclass_rows(price_metrics))
    write_json(data_dir / "portfolio_backtests.json", dataclass_rows(portfolio_backtests))
    if args.build_site:
        build_site(data_dir, Path(args.public_dir))
    print(f"Reports loaded: {len(reports)}")
    print(f"Price metrics OK: {sum(1 for item in price_metrics if item.status == 'ok')}")
    print(f"Portfolio backtests: {len(portfolio_backtests)}")
    return 0


def run_export_markdown(args: argparse.Namespace) -> int:
    data_dir = Path(args.data_dir)
    reports = read_extracted_reports_csv(data_dir / "extracted_reports.csv")
    logs = export_markdown(
        reports,
        data_dir / "markdown",
        use_opendataloader=args.markdown_opendataloader,
        hybrid=args.opendataloader_hybrid,
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
    prices = refresh_price_history(Path(args.data_dir), Path(args.warehouse_dir), symbols=symbols)
    print(f"Daily price rows: {len(prices)}")
    print(f"Symbols: {prices['symbol'].nunique() if not prices.empty else 0}")
    return 0


def run_backtest(args: argparse.Namespace) -> int:
    counts = run_default_backtests(Path(args.data_dir), Path(args.warehouse_dir), dry_run=args.dry_run)
    for table, count in sorted(counts.items()):
        print(f"{table}: {count}")
    if args.export_dashboard:
        exports = export_dashboard_data(Path(args.data_dir), Path(args.warehouse_dir), Path(args.output_dir))
        for name, count in sorted(exports.items()):
            print(f"{name}: {count}")
    return 0


def run_optimize(args: argparse.Namespace) -> int:
    trials = optimize_strategies(Path(args.data_dir), Path(args.warehouse_dir), trials=args.trials, seed=args.seed, dry_run=args.dry_run)
    print(f"Optuna trials: {len(trials)}")
    if not trials.empty and "objective" in trials:
        best = trials.sort_values("objective", ascending=False).iloc[0]
        print(f"Best objective: {best['objective']}")
        print(f"Best strategy: {best.get('strategy_name', best.get('name', ''))}")
    return 0


def run_export_dashboard(args: argparse.Namespace) -> int:
    exports = export_dashboard_data(Path(args.data_dir), Path(args.warehouse_dir), Path(args.output_dir))
    for name, count in sorted(exports.items()):
        print(f"{name}: {count}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Collect SNUSMIC PDFs, extract target prices, and build dashboard data.")
    subparsers = parser.add_subparsers(dest="command")

    sync = subparsers.add_parser("sync", help="Fetch reports, download PDFs, and extract local archive rows.")
    sync.add_argument("--pages", default="1-7", help="Page range/list, for example 1-7 or 1,3,5.")
    sync.add_argument("--data-dir", default="data", help="Output data directory.")
    sync.add_argument("--force", action="store_true", help="Re-download PDFs even when a local copy exists.")
    sync.add_argument("--max-pages", type=int, default=4, help="Maximum PDF pages to parse for target-price extraction.")
    sync.add_argument("--opendataloader-fallback", action=argparse.BooleanOptionalAction, default=True, help="Use opendataloader-pdf for reports that pypdf cannot parse cleanly.")
    sync.add_argument("--opendataloader-output-dir", default="data/opendataloader", help="OpenDataLoader markdown output directory.")
    sync.add_argument("--opendataloader-hybrid", default=os.environ.get("OPENDATALOADER_HYBRID", ""), help="Optional OpenDataLoader hybrid mode, for example docling-fast.")
    sync.add_argument("--market-data", action=argparse.BooleanOptionalAction, default=True, help="Fetch yfinance data and compute return/portfolio metrics.")
    sync.add_argument("--markdown", action=argparse.BooleanOptionalAction, default=True, help="Export one markdown file per PDF.")
    sync.add_argument("--markdown-opendataloader", action=argparse.BooleanOptionalAction, default=True, help="Try opendataloader-pdf before falling back to pypdf text.")
    sync.set_defaults(func=run_sync)

    check_new = subparsers.add_parser("check-new", help="Check page one for new reports before running a heavy sync.")
    check_new.add_argument("--manifest", default="data/manifest.json")
    check_new.add_argument("--github-output", default="")
    check_new.set_defaults(func=run_check_new)

    build_site_parser = subparsers.add_parser("build-site", help="Build the Vercel-ready static dashboard artifact.")
    build_site_parser.add_argument("--data-dir", default="data")
    build_site_parser.add_argument("--public-dir", default="site/public")
    build_site_parser.set_defaults(func=run_build_site)

    refresh_market = subparsers.add_parser("refresh-market", help="Refresh yfinance price metrics and portfolio backtests from committed report CSV.")
    refresh_market.add_argument("--data-dir", default="data")
    refresh_market.add_argument("--build-site", action=argparse.BooleanOptionalAction, default=True)
    refresh_market.add_argument("--public-dir", default="site/public")
    refresh_market.set_defaults(func=run_refresh_market)

    export_md = subparsers.add_parser("export-markdown", help="Export one markdown file per committed PDF/report row.")
    export_md.add_argument("--data-dir", default="data")
    export_md.add_argument("--markdown-opendataloader", action=argparse.BooleanOptionalAction, default=True)
    export_md.add_argument("--opendataloader-hybrid", default=os.environ.get("OPENDATALOADER_HYBRID", ""))
    export_md.set_defaults(func=run_export_markdown)

    warehouse = subparsers.add_parser("build-warehouse", help="Normalize report metadata into the v3 warehouse.")
    warehouse.add_argument("--data-dir", default="data")
    warehouse.add_argument("--warehouse-dir", default="data/warehouse")
    warehouse.set_defaults(func=run_build_warehouse)

    refresh_prices = subparsers.add_parser("refresh-prices", help="Download yfinance OHLCV history into the v3 warehouse.")
    refresh_prices.add_argument("--data-dir", default="data")
    refresh_prices.add_argument("--warehouse-dir", default="data/warehouse")
    refresh_prices.add_argument("--symbols", default="", help="Optional comma-separated yfinance symbols for a partial refresh.")
    refresh_prices.set_defaults(func=run_refresh_prices)

    backtest = subparsers.add_parser("run-backtest", help="Run event-driven walk-forward v3 strategy backtests.")
    backtest.add_argument("--data-dir", default="data")
    backtest.add_argument("--warehouse-dir", default="data/warehouse")
    backtest.add_argument("--output-dir", default="data/quant_v3")
    backtest.add_argument("--dry-run", action="store_true", help="Use deterministic synthetic prices when real OHLCV is missing.")
    backtest.add_argument("--export-dashboard", action=argparse.BooleanOptionalAction, default=True)
    backtest.set_defaults(func=run_backtest)

    optimize = subparsers.add_parser("optimize-strategies", help="Search v3 trading parameters with Optuna.")
    optimize.add_argument("--data-dir", default="data")
    optimize.add_argument("--warehouse-dir", default="data/warehouse")
    optimize.add_argument("--trials", type=int, default=25)
    optimize.add_argument("--seed", type=int, default=42)
    optimize.add_argument("--dry-run", action="store_true")
    optimize.set_defaults(func=run_optimize)

    dashboard = subparsers.add_parser("export-dashboard", help="Export v3 warehouse tables into dashboard JSON artifacts.")
    dashboard.add_argument("--data-dir", default="data")
    dashboard.add_argument("--warehouse-dir", default="data/warehouse")
    dashboard.add_argument("--output-dir", default="data/quant_v3")
    dashboard.set_defaults(func=run_export_dashboard)
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
