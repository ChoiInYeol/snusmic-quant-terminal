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
        report["Insight Prompt"] = "해당 .md 을 ChatGPT, Claude에게 입력하여 인사이트를 얻으세요."
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
    return """<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>SNUSMIC Quant Dashboard</title>
  <style>
    :root {
      color-scheme: light;
      --ink: #18242e;
      --muted: #5d6975;
      --line: #d8e0e8;
      --panel: #ffffff;
      --bg: #f5f7fa;
      --accent: #126b83;
      --accent-soft: #e5f3f6;
      --good: #087443;
      --bad: #b53b2d;
      font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    body { margin: 0; color: var(--ink); background: var(--bg); }
    header { padding: 30px 28px 18px; background: var(--panel); border-bottom: 1px solid var(--line); }
    main { max-width: 1520px; margin: 0 auto; padding: 22px 24px 36px; }
    h1 { margin: 0 0 8px; font-size: 30px; letter-spacing: 0; }
    h2 { margin: 28px 0 12px; font-size: 20px; letter-spacing: 0; }
    p { color: var(--muted); margin: 0; }
    a { color: var(--accent); text-decoration: none; }
    .tabs { display: flex; gap: 8px; margin: 22px 0 16px; flex-wrap: wrap; }
    .tabs button, .toolbar button {
      border: 1px solid var(--line); background: var(--panel); padding: 9px 12px; border-radius: 6px; cursor: pointer;
    }
    .tabs button.active { background: var(--accent); color: #fff; border-color: var(--accent); }
    section[data-panel] { display: none; }
    section[data-panel].active { display: block; }
    .grid { display: grid; gap: 14px; }
    .stats { grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); margin-bottom: 16px; }
    .two { grid-template-columns: minmax(340px, 0.85fr) minmax(460px, 1.15fr); align-items: stretch; }
    .card { background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 16px; }
    .stat strong { display: block; font-size: 24px; margin-top: 4px; }
    .stat span, .small { color: var(--muted); font-size: 12px; }
    .best-title { font-size: 15px; color: var(--muted); margin-bottom: 8px; }
    .best-main { font-size: 22px; font-weight: 700; margin-bottom: 8px; }
    .pill { display: inline-block; padding: 3px 7px; border-radius: 999px; background: var(--accent-soft); color: var(--accent); font-size: 12px; margin-right: 6px; }
    .toolbar { display: flex; gap: 10px; flex-wrap: wrap; margin: 14px 0; align-items: center; }
    input, select { padding: 10px 12px; border: 1px solid #c8d2dc; border-radius: 6px; background: #fff; font-size: 14px; }
    input { min-width: 280px; }
    .table-wrap { overflow: auto; background: var(--panel); border: 1px solid var(--line); border-radius: 8px; max-height: 650px; }
    table { border-collapse: collapse; width: 100%; min-width: 1180px; }
    th, td { border-bottom: 1px solid #edf1f5; padding: 9px 10px; vertical-align: top; text-align: left; font-size: 13px; }
    th { position: sticky; top: 0; background: #edf4f8; z-index: 1; cursor: pointer; white-space: nowrap; }
    td.num { text-align: right; font-variant-numeric: tabular-nums; }
    .ok { color: var(--good); font-weight: 600; }
    .review, .neg { color: var(--bad); font-weight: 600; }
    .pos { color: var(--good); font-weight: 600; }
    svg { width: 100%; height: 390px; display: block; background: #fbfcfd; border: 1px solid var(--line); border-radius: 8px; }
    .legend { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 8px; color: var(--muted); font-size: 12px; }
    .bar { display: inline-block; height: 8px; background: var(--accent); border-radius: 4px; vertical-align: middle; margin-right: 6px; }
    @media (max-width: 980px) { .two { grid-template-columns: 1fr; } main { padding: 18px 12px; } }
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
      <div id="reportStats" class="grid stats"></div>
      <div class="table-wrap"><table id="reportsTable"></table></div>
    </section>
  </main>
  <script>
    const pct = v => v === null || v === undefined || v === "" || Number.isNaN(Number(v)) ? "" : (Number(v) * 100).toFixed(1) + "%";
    const num = v => v === null || v === undefined || v === "" || Number.isNaN(Number(v)) ? "" : Number(v).toLocaleString(undefined, { maximumFractionDigits: 2 });
    const signClass = v => Number(v) > 0 ? "pos" : (Number(v) < 0 ? "neg" : "");
    const unique = arr => [...new Set(arr.filter(v => v !== null && v !== undefined && v !== ""))].sort();
    function holdings(row) {
      const names = String(row.display_symbols || row.symbols || "").split(",");
      const weights = String(row.weights || "").split(",");
      return names.map((name, i) => `${name.trim()} ${(Number(weights[i] || 0) * 100).toFixed(1)}%`).join("<br>");
    }
    async function loadJson(path) { const r = await fetch(path); return r.ok ? r.json() : []; }
    function renderTable(el, rows, columns, format = {}) {
      el.dataset.sortKey = el.dataset.sortKey || "";
      el.dataset.sortDir = el.dataset.sortDir || "desc";
      const sorted = [...rows];
      if (el.dataset.sortKey) {
        const key = el.dataset.sortKey, dir = el.dataset.sortDir === "asc" ? 1 : -1;
        sorted.sort((a,b) => {
          const av = a[key], bv = b[key];
          const an = Number(av), bn = Number(bv);
          if (!Number.isNaN(an) && !Number.isNaN(bn)) return (an - bn) * dir;
          return String(av ?? "").localeCompare(String(bv ?? "")) * dir;
        });
      }
      el.innerHTML = "<thead><tr>" + columns.map(c => `<th data-key="${c.key}">${c.label}</th>`).join("") + "</tr></thead><tbody>" +
        sorted.map(row => "<tr>" + columns.map(c => {
          let value = row[c.key] ?? "";
          if (format[c.key]) value = format[c.key](value, row);
          return `<td class="${c.num ? "num" : ""}">${value}</td>`;
        }).join("") + "</tr>").join("") + "</tbody>";
      el.querySelectorAll("th").forEach(th => th.addEventListener("click", () => {
        const key = th.dataset.key;
        el.dataset.sortDir = el.dataset.sortKey === key && el.dataset.sortDir === "desc" ? "asc" : "desc";
        el.dataset.sortKey = key;
        renderTable(el, rows, columns, format);
      }));
    }
    function topPortfolios(portfolio, n = 12) {
      return [...portfolio].filter(r => r.status === "ok" && r.realized_return !== null)
        .sort((a,b) => Number(b.realized_return) - Number(a.realized_return)).slice(0, n);
    }
    function renderOverview(reports, metrics, portfolio) {
      const okPrices = metrics.filter(r => r.status === "ok");
      const targetHits = okPrices.filter(r => r.target_hit).length;
      const best = topPortfolios(portfolio, 1)[0];
      const avgRet = okPrices.reduce((s,r) => s + Number(r.buy_at_publication_return || 0), 0) / Math.max(1, okPrices.length);
      document.getElementById("overviewStats").innerHTML = [
        ["Reports", reports.length],
        ["Price coverage", `${okPrices.length}/${metrics.length}`],
        ["Target hit ratio", pct(targetHits / Math.max(1, okPrices.length))],
        ["Avg post-publication return", pct(avgRet)],
      ].map(([k,v]) => `<div class="card stat"><span>${k}</span><strong>${v}</strong></div>`).join("");
      document.getElementById("bestPortfolio").innerHTML = best ? `
        <div class="best-title">Best realized portfolio so far</div>
        <div class="best-main">${best.cohort_month} · ${best.strategy} · RF ${pct(best.risk_free_rate)}</div>
        <p><span class="pill">Realized ${pct(best.realized_return)}</span><span class="pill">Sharpe ${num(best.expected_sharpe)}</span><span class="pill">Vol ${pct(best.expected_volatility)}</span></p>
        <h2>Weights</h2>
        ${(best.display_symbols || best.symbols).split(",").map((s,i) => `<p><span class="bar" style="width:${Math.max(6, Number(best.weights.split(",")[i] || 0)*160)}px"></span>${s.trim()} ${(Number(best.weights.split(",")[i] || 0)*100).toFixed(1)}%</p>`).join("")}
      ` : "<p>No portfolio data.</p>";
      renderFrontier(portfolio);
      renderTable(document.getElementById("topPortfolioTable"), topPortfolios(portfolio), portfolioColumns(), portfolioFormats());
    }
    function renderFrontier(portfolio) {
      const rows = portfolio.filter(r => r.expected_volatility !== null && r.expected_return !== null);
      const svg = document.getElementById("frontierSvg");
      const w = 760, h = 390, pad = 48;
      if (!rows.length) { svg.innerHTML = ""; return; }
      const xs = rows.map(r => Number(r.expected_volatility)), ys = rows.map(r => Number(r.expected_return));
      const xmin = Math.min(...xs), xmax = Math.max(...xs), ymin = Math.min(...ys), ymax = Math.max(...ys);
      const sx = x => pad + (x - xmin) / Math.max(1e-9, xmax - xmin) * (w - pad * 1.6);
      const sy = y => h - pad - (y - ymin) / Math.max(1e-9, ymax - ymin) * (h - pad * 1.6);
      const colors = { "1/N":"#607d8b", momentum:"#126b83", max_sharpe:"#087443", sortino:"#8e44ad", max_return:"#c0392b", min_var:"#f39c12", calmar:"#2c3e50" };
      const axis = `<line x1="${pad}" y1="${h-pad}" x2="${w-pad/2}" y2="${h-pad}" stroke="#9aa8b4"/><line x1="${pad}" y1="${pad/2}" x2="${pad}" y2="${h-pad}" stroke="#9aa8b4"/><text x="${w/2}" y="${h-10}" text-anchor="middle" font-size="12" fill="#5d6975">Expected volatility</text><text x="14" y="${h/2}" transform="rotate(-90 14 ${h/2})" text-anchor="middle" font-size="12" fill="#5d6975">Expected return</text>`;
      const dots = rows.map(r => `<circle cx="${sx(Number(r.expected_volatility))}" cy="${sy(Number(r.expected_return))}" r="${4 + Math.max(0, Number(r.realized_return || 0))*3}" fill="${colors[r.strategy] || "#126b83"}" opacity="0.72"><title>${r.cohort_month} ${r.strategy} RF ${pct(r.risk_free_rate)} | exp ${pct(r.expected_return)} vol ${pct(r.expected_volatility)} realized ${pct(r.realized_return)}</title></circle>`).join("");
      svg.innerHTML = axis + dots;
      document.getElementById("frontierLegend").innerHTML = Object.entries(colors).map(([k,c]) => `<span><span class="bar" style="width:18px;background:${c}"></span>${k}</span>`).join("");
    }
    function portfolioColumns() {
      return [
        {key:"cohort_month", label:"Cohort"}, {key:"strategy", label:"Strategy"}, {key:"risk_free_rate", label:"RF", num:true},
        {key:"realized_return", label:"Realized", num:true}, {key:"expected_return", label:"Expected", num:true},
        {key:"expected_volatility", label:"Vol", num:true}, {key:"expected_sharpe", label:"Sharpe", num:true},
        {key:"kospi_return", label:"KOSPI", num:true}, {key:"nasdaq_return", label:"NASDAQ", num:true}, {key:"display_symbols", label:"Holdings"}
      ];
    }
    function portfolioFormats() {
      return {risk_free_rate:pct, realized_return:v=>`<span class="${signClass(v)}">${pct(v)}</span>`, expected_return:pct, expected_volatility:pct, expected_sharpe:num, kospi_return:pct, nasdaq_return:pct, display_symbols:(v,row)=>holdings(row)};
    }
    function renderPortfolio(portfolio) {
      const cohort = document.getElementById("portfolioCohort").value;
      const rf = document.getElementById("portfolioRf").value;
      const strategy = document.getElementById("portfolioStrategy").value;
      const rows = portfolio.filter(r => (!cohort || r.cohort_month === cohort) && (!rf || String(r.risk_free_rate) === rf) && (!strategy || r.strategy === strategy));
      const table = document.getElementById("portfolioTable");
      table.dataset.sortKey = table.dataset.sortKey || "realized_return";
      renderTable(table, rows, portfolioColumns(), portfolioFormats());
    }
    function metricColumns() {
      return [
        {key:"publication_date", label:"Date"}, {key:"company", label:"Company"},
        {key:"current_price", label:"Current", num:true}, {key:"publication_buy_price", label:"Pub price", num:true},
        {key:"lowest_price_since_publication", label:"Low price", num:true},
        {key:"q25_price_since_publication", label:"Q25 price", num:true}, {key:"q75_price_since_publication", label:"Q75 price", num:true},
        {key:"buy_at_publication_return", label:"Pub buy ret", num:true}, {key:"lowest_price_current_return", label:"Low buy ret", num:true},
        {key:"low_to_high_return", label:"Low→High ret", num:true}, {key:"optimal_buy_lag_days", label:"Best lag days", num:true}, {key:"low_to_high_holding_days", label:"Best hold days", num:true},
        {key:"q25_price_current_return", label:"Q25 buy ret", num:true}, {key:"q75_price_current_return", label:"Q75 buy ret", num:true},
        {key:"current_price_percentile", label:"Current pctile", num:true}, {key:"target_upside_remaining", label:"Target upside", num:true},
        {key:"highest_price_realized_return", label:"Best sell ret", num:true}, {key:"target_hit", label:"Target"}, {key:"first_target_hit_date", label:"Hit date"}
      ];
    }
    function renderMetrics(metrics) {
      const q = document.getElementById("metricsSearch").value.toLowerCase();
      const target = document.getElementById("targetFilter").value;
      const rows = metrics.filter(r => (!target || (target === "hit" ? r.target_hit : !r.target_hit)) && JSON.stringify(r).toLowerCase().includes(q));
      renderTable(document.getElementById("metricsTable"), rows, metricColumns(), {
        current_price:num, publication_buy_price:num, lowest_price_since_publication:num, q25_price_since_publication:num, q75_price_since_publication:num,
        buy_at_publication_return:v=>`<span class="${signClass(v)}">${pct(v)}</span>`,
        lowest_price_current_return:v=>`<span class="${signClass(v)}">${pct(v)}</span>`,
        low_to_high_return:pct,
        q25_price_current_return:v=>`<span class="${signClass(v)}">${pct(v)}</span>`,
        q75_price_current_return:v=>`<span class="${signClass(v)}">${pct(v)}</span>`,
        current_price_percentile:pct,
        target_upside_remaining:v=>`<span class="${signClass(v)}">${pct(v)}</span>`,
        highest_price_realized_return:pct,
        target_hit:v=>v ? "hit" : "miss"
      });
    }
    function reportColumns() {
      return [
        { key:"Report Date", label:"Date" }, { key:"Company", label:"Company" },
        { key:"Bear 목표가", label:"Bear target", num:true }, { key:"Base 목표가", label:"Base target", num:true }, { key:"Bull 목표가", label:"Bull target", num:true },
        { key:"Report Price", label:"Report price", num:true }, { key:"Markdown", label:"Markdown" }, { key:"Insight Prompt", label:"Prompt" }, { key:"GitHub PDF", label:"PDF" }
      ];
    }
    function renderReports(all) {
      const q = document.getElementById("reportSearch").value.toLowerCase();
      const rows = all.filter(r => JSON.stringify(r).toLowerCase().includes(q));
      document.getElementById("reportStats").innerHTML = [
        ["Reports", rows.length], ["With target", rows.filter(r => r["Base 목표가"]).length], ["Target hit", rows.filter(r => r["Base 대비 괴리율"]).length],
      ].map(([k,v]) => `<div class="card stat"><span>${k}</span><strong>${v}</strong></div>`).join("");
      renderTable(document.getElementById("reportsTable"), rows, reportColumns(), {
        "GitHub PDF": v => v ? `<a href="${v}">PDF</a>` : "",
        "Markdown": v => v ? `<a href="${v}">Markdown</a>` : "",
        "Report Price": num
      });
    }
    Promise.all([loadJson("data/reports.json"), loadJson("data/price_metrics.json"), loadJson("data/portfolio_backtests.json")]).then(([reports, metrics, portfolio]) => {
      const cohorts = unique(portfolio.map(r => r.cohort_month));
      const rfs = unique(portfolio.map(r => String(r.risk_free_rate)));
      const strategies = unique(portfolio.map(r => r.strategy));
      document.getElementById("portfolioCohort").innerHTML = `<option value="">All cohorts</option>` + cohorts.map(v=>`<option>${v}</option>`).join("");
      document.getElementById("portfolioRf").innerHTML = `<option value="">All RF</option>` + rfs.map(v=>`<option value="${v}">${pct(v)}</option>`).join("");
      document.getElementById("portfolioStrategy").innerHTML = `<option value="">All strategies</option>` + strategies.map(v=>`<option>${v}</option>`).join("");
      renderOverview(reports, metrics, portfolio);
      renderPortfolio(portfolio);
      renderMetrics(metrics);
      renderReports(reports);
      ["portfolioCohort","portfolioRf","portfolioStrategy"].forEach(id => document.getElementById(id).addEventListener("change", () => renderPortfolio(portfolio)));
      document.getElementById("metricsSearch").addEventListener("input", () => renderMetrics(metrics));
      document.getElementById("targetFilter").addEventListener("change", () => renderMetrics(metrics));
      document.getElementById("reportSearch").addEventListener("input", () => renderReports(reports));
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
