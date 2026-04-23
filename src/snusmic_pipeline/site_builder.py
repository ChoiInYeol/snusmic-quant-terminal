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


def build_reports_json(data_dir: Path, public_dir: Path) -> list[dict[str, Any]]:
    reports = read_csv_dicts(data_dir / "extracted_reports.csv")
    for report in reports:
        filename = report.get("PDF 파일명", "")
        report["GitHub PDF"] = repo_pdf_url(filename) if filename else ""
    write_json(public_dir / "data" / "reports.json", reports)
    return reports


def render_index_html() -> str:
    return """<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>SNUSMIC Report Dashboard</title>
  <style>
    :root { color-scheme: light; font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
    body { margin: 0; color: #172026; background: #f6f8fb; }
    header { padding: 32px 24px 18px; background: #fff; border-bottom: 1px solid #dce3ea; }
    main { padding: 24px; max-width: 1440px; margin: 0 auto; }
    h1 { margin: 0 0 8px; font-size: 28px; letter-spacing: 0; }
    .toolbar { display: flex; gap: 12px; flex-wrap: wrap; margin: 18px 0; }
    input, select { padding: 10px 12px; border: 1px solid #c8d2dc; border-radius: 6px; background: #fff; font-size: 14px; }
    input { min-width: 280px; }
    .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin-bottom: 18px; }
    .stat { background: #fff; border: 1px solid #dce3ea; border-radius: 8px; padding: 14px; }
    .stat strong { display: block; font-size: 22px; }
    .table-wrap { overflow: auto; background: #fff; border: 1px solid #dce3ea; border-radius: 8px; }
    table { border-collapse: collapse; width: 100%; min-width: 1280px; }
    th, td { border-bottom: 1px solid #edf1f5; padding: 10px; vertical-align: top; text-align: left; font-size: 13px; }
    th { position: sticky; top: 0; background: #eef4f8; z-index: 1; }
    td.num { text-align: right; font-variant-numeric: tabular-nums; }
    a { color: #0b6b88; text-decoration: none; }
    .ok { color: #0b6b3a; font-weight: 600; }
    .review { color: #a34b00; font-weight: 600; }
    .tabs { display: flex; gap: 8px; margin: 20px 0 12px; }
    .tabs button { border: 1px solid #c8d2dc; background: #fff; padding: 9px 12px; border-radius: 6px; cursor: pointer; }
    .tabs button.active { background: #0b6b88; color: #fff; border-color: #0b6b88; }
    section[data-panel] { display: none; }
    section[data-panel].active { display: block; }
  </style>
</head>
<body>
  <header>
    <h1>SNUSMIC Report Dashboard</h1>
    <p>SNUSMIC 리포트 PDF, 목표가 추출, 발간 이후 수익률, 포트폴리오 백테스트를 정리합니다.</p>
  </header>
  <main>
    <div class="tabs">
      <button class="active" data-tab="reports">Reports</button>
      <button data-tab="metrics">Price Metrics</button>
      <button data-tab="portfolio">Portfolio</button>
    </div>
    <section class="active" data-panel="reports">
      <div class="toolbar"><input id="reportSearch" placeholder="종목, 티커, 리포트 검색"><select id="statusFilter"><option value="">All status</option><option value="ok">ok</option><option value="needs_review">needs_review</option></select></div>
      <div id="reportStats" class="stats"></div>
      <div class="table-wrap"><table id="reportsTable"></table></div>
    </section>
    <section data-panel="metrics">
      <div class="table-wrap"><table id="metricsTable"></table></div>
    </section>
    <section data-panel="portfolio">
      <div class="table-wrap"><table id="portfolioTable"></table></div>
    </section>
  </main>
  <script>
    const fmtPct = v => v === null || v === undefined || v === "" ? "" : (Number(v) * 100).toFixed(1) + "%";
    const fmtNum = v => v === null || v === undefined || v === "" ? "" : Number(v).toLocaleString(undefined, { maximumFractionDigits: 2 });
    async function loadJson(path) { const r = await fetch(path); return r.ok ? r.json() : []; }
    function renderTable(el, rows, columns, format = {}) {
      el.innerHTML = "<thead><tr>" + columns.map(c => `<th>${c.label}</th>`).join("") + "</tr></thead><tbody>" +
        rows.map(row => "<tr>" + columns.map(c => {
          let value = row[c.key] ?? "";
          if (format[c.key]) value = format[c.key](value, row);
          return `<td class="${c.num ? "num" : ""}">${value}</td>`;
        }).join("") + "</tr>").join("") + "</tbody>";
    }
    function renderStats(rows) {
      const ok = rows.filter(r => r["추출 상태"] === "ok").length;
      document.getElementById("reportStats").innerHTML = [
        ["Reports", rows.length],
        ["Extracted OK", ok],
        ["Needs review", rows.length - ok],
        ["With target", rows.filter(r => r["Base 목표가"]).length],
      ].map(([k,v]) => `<div class="stat"><span>${k}</span><strong>${v}</strong></div>`).join("");
    }
    function reportColumns() {
      return [
        { key:"게시일", label:"게시일" }, { key:"종목명", label:"종목" }, { key:"티커", label:"티커" },
        { key:"Base 목표가", label:"Base 목표가", num:true }, { key:"리포트 현재주가", label:"리포트 현재가", num:true },
        { key:"투자포인트", label:"투자포인트" }, { key:"추출 상태", label:"상태" },
        { key:"GitHub PDF", label:"PDF" }
      ];
    }
    function renderReports(all) {
      const q = document.getElementById("reportSearch").value.toLowerCase();
      const status = document.getElementById("statusFilter").value;
      const rows = all.filter(r => (!status || r["추출 상태"] === status) && JSON.stringify(r).toLowerCase().includes(q));
      renderStats(rows);
      renderTable(document.getElementById("reportsTable"), rows, reportColumns(), {
        "GitHub PDF": v => v ? `<a href="${v}">PDF</a>` : "",
        "추출 상태": v => `<span class="${v === "ok" ? "ok" : "review"}">${v}</span>`
      });
    }
    Promise.all([loadJson("data/reports.json"), loadJson("data/price_metrics.json"), loadJson("data/portfolio_backtests.json")]).then(([reports, metrics, portfolio]) => {
      renderReports(reports);
      document.getElementById("reportSearch").addEventListener("input", () => renderReports(reports));
      document.getElementById("statusFilter").addEventListener("change", () => renderReports(reports));
      renderTable(document.getElementById("metricsTable"), metrics, [
        {key:"publication_date", label:"발간일"}, {key:"title", label:"리포트"}, {key:"yfinance_symbol", label:"YF"},
        {key:"buy_at_publication_return", label:"발간일 매수 현재수익률", num:true},
        {key:"lowest_price_current_return", label:"최저가 매수 현재수익률", num:true},
        {key:"highest_price_realized_return", label:"최고가 매도 수익률", num:true},
        {key:"target_hit", label:"목표가 도달"}, {key:"first_target_hit_date", label:"첫 도달일"}
      ], {"buy_at_publication_return":fmtPct,"lowest_price_current_return":fmtPct,"highest_price_realized_return":fmtPct});
      renderTable(document.getElementById("portfolioTable"), portfolio, [
        {key:"cohort_month", label:"코호트"}, {key:"rebalance_date", label:"리밸런싱"}, {key:"strategy", label:"전략"},
        {key:"risk_free_rate", label:"무위험"}, {key:"realized_return", label:"실현수익률", num:true},
        {key:"symbols", label:"종목"}, {key:"weights", label:"비중"}
      ], {"risk_free_rate":fmtPct,"realized_return":fmtPct});
      document.querySelectorAll("[data-tab]").forEach(btn => btn.addEventListener("click", () => {
        document.querySelectorAll("[data-tab]").forEach(b => b.classList.remove("active"));
        document.querySelectorAll("[data-panel]").forEach(p => p.classList.remove("active"));
        btn.classList.add("active");
        document.querySelector(`[data-panel="${btn.dataset.tab}"]`).classList.add("active");
      }));
    });
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
