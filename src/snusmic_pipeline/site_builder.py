from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


def read_csv_dicts(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def read_json(path: Path) -> Any:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def repo_pdf_url(filename: str, repo: str = "ChoiInYeol/snusmic-google-finance-sheets", branch: str = "main") -> str:
    return f"https://github.com/{repo}/blob/{branch}/data/pdfs/{filename}"


def repo_markdown_url(filename: str, repo: str = "ChoiInYeol/snusmic-google-finance-sheets", branch: str = "main") -> str:
    return f"https://github.com/{repo}/blob/{branch}/data/markdown/{Path(filename).with_suffix('.md').name}"


def build_reports_json(data_dir: Path, public_dir: Path) -> list[dict[str, Any]]:
    reports = read_csv_dicts(data_dir / "extracted_reports.csv")
    metrics = {item.get("title", ""): item for item in read_json(data_dir / "price_metrics.json")}
    for report in reports:
        filename = report.get("PDF 파일명", "")
        report["GitHub PDF"] = repo_pdf_url(filename) if filename else ""
        report["Markdown"] = repo_markdown_url(filename) if filename else ""
        metric = metrics.get(report.get("리포트명", ""), {})
        report["Company"] = report.get("종목명", "")
        report["Report Date"] = format_kst_datetime(report.get("게시일", ""))
        report["Report Price"] = metric.get("publication_buy_price", "")
    write_json(public_dir / "data" / "reports.json", reports)
    return reports


def format_kst_datetime(value: str) -> str:
    if not value:
        return ""
    normalized = value.replace("T", " ")
    return normalized[:16]


def render_index_html() -> str:
    script = Path("site/quarto/dashboard.js").read_text(encoding="utf-8")
    css = Path("site/quarto/styles.css").read_text(encoding="utf-8")
    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>SNUSMIC Quant Dashboard</title>
  <style>
{css}
  </style>
</head>
<body>
  <header>
    <h1>SNUSMIC Quant Dashboard</h1>
    <p>SNUSMIC 리포트 아카이브, 목표가 추출, 발간 이후 가격 경로, 포트폴리오 전략 랭킹을 한 곳에서 봅니다.</p>
  </header>
  <main>
    <div class="tabs">
      <button class="active" data-tab="overview">Overview</button>
      <button data-tab="portfolio">Portfolio Ranking</button>
      <button data-tab="metrics">Price Metrics</button>
      <button data-tab="reports">Report Archive</button>
    </div>

    <section class="active" data-panel="overview">
      <div id="overviewStats" class="grid stats"></div>
      <div class="grid two">
        <div id="bestPortfolio" class="card"></div>
        <div class="card">
          <h2 style="margin-top:0">Risk / Return Map</h2>
          <svg id="frontierSvg" viewBox="0 0 760 390" role="img" aria-label="portfolio risk return map"></svg>
          <div id="frontierLegend" class="legend"></div>
        </div>
      </div>
      <h2>Top Portfolio Candidates</h2>
      <div class="table-wrap"><table id="topPortfolioTable"></table></div>
    </section>

    <section data-panel="portfolio">
      <div class="toolbar">
        <select id="portfolioCohort"></select>
        <select id="portfolioRf"></select>
        <select id="portfolioStrategy"></select>
      </div>
      <div class="table-wrap"><table id="portfolioTable"></table></div>
    </section>

    <section data-panel="metrics">
      <div class="toolbar">
        <input id="metricsSearch" placeholder="종목, 티커, 리포트 검색">
        <select id="targetFilter"><option value="">All</option><option value="hit">Target hit</option><option value="miss">Target miss</option></select>
      </div>
      <div class="table-wrap"><table id="metricsTable"></table></div>
    </section>

    <section data-panel="reports">
      <div class="toolbar">
        <input id="reportSearch" placeholder="종목, 티커, 리포트 검색">
      </div>
      <p class="small" style="margin-bottom:12px">Markdown 파일을 ChatGPT나 Claude에 입력하면 리포트별 인사이트를 더 깊게 뽑아볼 수 있습니다.</p>
      <div id="reportStats" class="grid stats"></div>
      <div class="table-wrap"><table id="reportsTable"></table></div>
    </section>
  </main>
  <script>
{script}
  </script>
</body>
</html>
"""


def build_site(data_dir: Path, public_dir: Path) -> None:
    public_dir.mkdir(parents=True, exist_ok=True)
    reports = build_reports_json(data_dir, public_dir)
    write_json(public_dir / "data" / "price_metrics.json", read_json(data_dir / "price_metrics.json"))
    write_json(public_dir / "data" / "portfolio_backtests.json", read_json(data_dir / "portfolio_backtests.json"))
    (public_dir / "index.html").write_text(render_index_html(), encoding="utf-8")
    write_json(public_dir / "data" / "site_summary.json", {"reports": len(reports)})
