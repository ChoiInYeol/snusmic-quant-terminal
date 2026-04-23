const pct = v => v === null || v === undefined || v === "" || Number.isNaN(Number(v)) ? "" : (Number(v) * 100).toFixed(1) + "%";
const num = v => v === null || v === undefined || v === "" || Number.isNaN(Number(v)) ? "" : Number(v).toLocaleString(undefined, { maximumFractionDigits: 2 });
const signClass = v => Number(v) > 0 ? "pos" : (Number(v) < 0 ? "neg" : "");
const unique = arr => [...new Set(arr.filter(v => v !== null && v !== undefined && v !== ""))].sort();

async function loadJson(path) {
  const candidates = [`data/${path}`, `../data/${path}`];
  for (const candidate of candidates) {
    const response = await fetch(candidate);
    if (response.ok) return response.json();
  }
  return [];
}

function holdings(row) {
  const names = String(row.display_symbols || row.symbols || "").split(",");
  const weights = String(row.weights || "").split(",");
  return names.map((name, i) => `${name.trim()} ${(Number(weights[i] || 0) * 100).toFixed(1)}%`).join("<br>");
}

function renderTable(el, rows, columns, format = {}) {
  if (!el) return;
  el.dataset.sortKey = el.dataset.sortKey || "";
  el.dataset.sortDir = el.dataset.sortDir || "desc";
  const sorted = [...rows];
  if (el.dataset.sortKey) {
    const key = el.dataset.sortKey;
    const dir = el.dataset.sortDir === "asc" ? 1 : -1;
    sorted.sort((a, b) => {
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
    .sort((a, b) => Number(b.realized_return) - Number(a.realized_return)).slice(0, n);
}

function portfolioColumns() {
  return [
    { key: "cohort_month", label: "Cohort" },
    { key: "strategy", label: "Strategy" },
    { key: "risk_free_rate", label: "RF", num: true },
    { key: "realized_return", label: "Realized", num: true },
    { key: "expected_return", label: "Expected", num: true },
    { key: "expected_volatility", label: "Vol", num: true },
    { key: "expected_sharpe", label: "Sharpe", num: true },
    { key: "kospi_return", label: "KOSPI", num: true },
    { key: "nasdaq_return", label: "NASDAQ", num: true },
    { key: "display_symbols", label: "Holdings" },
  ];
}

function portfolioFormats() {
  return {
    risk_free_rate: pct,
    realized_return: v => `<span class="${signClass(v)}">${pct(v)}</span>`,
    expected_return: pct,
    expected_volatility: pct,
    expected_sharpe: num,
    kospi_return: pct,
    nasdaq_return: pct,
    display_symbols: (v, row) => holdings(row),
  };
}

function metricColumns() {
  return [
    { key: "publication_date", label: "Date" },
    { key: "company", label: "Company" },
    { key: "current_price", label: "Current", num: true },
    { key: "publication_buy_price", label: "Pub price", num: true },
    { key: "lowest_price_since_publication", label: "Low price", num: true },
    { key: "q25_price_since_publication", label: "Q25 price", num: true },
    { key: "q75_price_since_publication", label: "Q75 price", num: true },
    { key: "buy_at_publication_return", label: "Pub buy ret", num: true },
    { key: "lowest_price_current_return", label: "Low buy ret", num: true },
    { key: "low_to_high_return", label: "Low→High ret", num: true },
    { key: "optimal_buy_lag_days", label: "Best lag days", num: true },
    { key: "low_to_high_holding_days", label: "Best hold days", num: true },
    { key: "q25_price_current_return", label: "Q25 buy ret", num: true },
    { key: "q75_price_current_return", label: "Q75 buy ret", num: true },
    { key: "current_price_percentile", label: "Current pctile", num: true },
    { key: "target_upside_remaining", label: "Target upside", num: true },
    { key: "highest_price_realized_return", label: "Best sell ret", num: true },
    { key: "target_hit", label: "Target" },
    { key: "first_target_hit_date", label: "Hit date" },
  ];
}

function metricFormats() {
  return {
    current_price: num,
    publication_buy_price: num,
    lowest_price_since_publication: num,
    q25_price_since_publication: num,
    q75_price_since_publication: num,
    buy_at_publication_return: v => `<span class="${signClass(v)}">${pct(v)}</span>`,
    lowest_price_current_return: v => `<span class="${signClass(v)}">${pct(v)}</span>`,
    low_to_high_return: pct,
    q25_price_current_return: v => `<span class="${signClass(v)}">${pct(v)}</span>`,
    q75_price_current_return: v => `<span class="${signClass(v)}">${pct(v)}</span>`,
    current_price_percentile: pct,
    target_upside_remaining: v => `<span class="${signClass(v)}">${pct(v)}</span>`,
    highest_price_realized_return: pct,
    target_hit: v => v ? "hit" : "miss",
  };
}

function reportColumns() {
  return [
    { key: "Report Date", label: "Date" },
    { key: "Company", label: "Company" },
    { key: "Bear 목표가", label: "Bear target", num: true },
    { key: "Base 목표가", label: "Base target", num: true },
    { key: "Bull 목표가", label: "Bull target", num: true },
    { key: "Report Price", label: "Report price", num: true },
    { key: "Markdown", label: "Markdown" },
    { key: "GitHub PDF", label: "PDF" },
  ];
}

function renderFrontier(portfolio) {
  const rows = portfolio.filter(r => r.expected_volatility !== null && r.expected_return !== null);
  const svg = document.getElementById("frontierSvg");
  if (!svg || !rows.length) return;
  const w = 760, h = 390, pad = 48;
  const xs = rows.map(r => Number(r.expected_volatility)), ys = rows.map(r => Number(r.expected_return));
  const xmin = Math.min(...xs), xmax = Math.max(...xs), ymin = Math.min(...ys), ymax = Math.max(...ys);
  const sx = x => pad + (x - xmin) / Math.max(1e-9, xmax - xmin) * (w - pad * 1.6);
  const sy = y => h - pad - (y - ymin) / Math.max(1e-9, ymax - ymin) * (h - pad * 1.6);
  const colors = { "1/N": "#607d8b", momentum: "#126b83", max_sharpe: "#087443", sortino: "#8e44ad", max_return: "#c0392b", min_var: "#f39c12", calmar: "#2c3e50" };
  const axis = `<line x1="${pad}" y1="${h - pad}" x2="${w - pad / 2}" y2="${h - pad}" stroke="#9aa8b4"/><line x1="${pad}" y1="${pad / 2}" x2="${pad}" y2="${h - pad}" stroke="#9aa8b4"/><text x="${w / 2}" y="${h - 10}" text-anchor="middle" font-size="12" fill="#5d6975">Expected volatility</text><text x="14" y="${h / 2}" transform="rotate(-90 14 ${h / 2})" text-anchor="middle" font-size="12" fill="#5d6975">Expected return</text>`;
  const dots = rows.map(r => `<circle cx="${sx(Number(r.expected_volatility))}" cy="${sy(Number(r.expected_return))}" r="${4 + Math.max(0, Number(r.realized_return || 0)) * 3}" fill="${colors[r.strategy] || "#126b83"}" opacity="0.72"><title>${r.cohort_month} ${r.strategy} RF ${pct(r.risk_free_rate)} | exp ${pct(r.expected_return)} vol ${pct(r.expected_volatility)} realized ${pct(r.realized_return)}</title></circle>`).join("");
  svg.innerHTML = axis + dots;
  const legend = document.getElementById("frontierLegend");
  if (legend) legend.innerHTML = Object.entries(colors).map(([k, c]) => `<span><span class="bar" style="width:18px;background:${c}"></span>${k}</span>`).join("");
}

function renderOverview(reports, metrics, portfolio) {
  const el = document.getElementById("overviewStats");
  if (!el) return;
  const okPrices = metrics.filter(r => r.status === "ok");
  const targetHits = okPrices.filter(r => r.target_hit).length;
  const best = topPortfolios(portfolio, 1)[0];
  const avgRet = okPrices.reduce((s, r) => s + Number(r.buy_at_publication_return || 0), 0) / Math.max(1, okPrices.length);
  el.innerHTML = [
    ["Reports", reports.length],
    ["Price coverage", `${okPrices.length}/${metrics.length}`],
    ["Target hit ratio", pct(targetHits / Math.max(1, okPrices.length))],
    ["Avg post-publication return", pct(avgRet)],
  ].map(([k, v]) => `<div class="metric-card"><span>${k}</span><strong>${v}</strong></div>`).join("");
  const bestEl = document.getElementById("bestPortfolio");
  if (bestEl) {
    bestEl.innerHTML = best ? `
      <div class="best-title">Best realized portfolio so far</div>
      <div class="best-main">${best.cohort_month} · ${best.strategy} · RF ${pct(best.risk_free_rate)}</div>
      <p><span class="pill">Realized ${pct(best.realized_return)}</span><span class="pill">Sharpe ${num(best.expected_sharpe)}</span><span class="pill">Vol ${pct(best.expected_volatility)}</span></p>
      <h2>Weights</h2>
      ${(best.display_symbols || best.symbols).split(",").map((s, i) => `<p><span class="bar" style="width:${Math.max(6, Number(best.weights.split(",")[i] || 0) * 160)}px"></span>${s.trim()} ${(Number(best.weights.split(",")[i] || 0) * 100).toFixed(1)}%</p>`).join("")}
    ` : "<p>No portfolio data.</p>";
  }
  renderFrontier(portfolio);
  renderTable(document.getElementById("topPortfolioTable"), topPortfolios(portfolio), portfolioColumns(), portfolioFormats());
  renderTable(document.getElementById("overviewMetricsTable"), [...metrics].filter(r => r.status === "ok").sort((a, b) => Number(b.low_to_high_return || 0) - Number(a.low_to_high_return || 0)).slice(0, 15), metricColumns(), metricFormats());
}

function renderPortfolio(portfolio) {
  const cohort = document.getElementById("portfolioCohort")?.value || "";
  const rf = document.getElementById("portfolioRf")?.value || "";
  const strategy = document.getElementById("portfolioStrategy")?.value || "";
  const rows = portfolio.filter(r => (!cohort || r.cohort_month === cohort) && (!rf || String(r.risk_free_rate) === rf) && (!strategy || r.strategy === strategy));
  const table = document.getElementById("portfolioTable");
  if (table) table.dataset.sortKey = table.dataset.sortKey || "realized_return";
  renderTable(table, rows, portfolioColumns(), portfolioFormats());
}

function renderMetrics(metrics) {
  const q = document.getElementById("metricsSearch")?.value.toLowerCase() || "";
  const target = document.getElementById("targetFilter")?.value || "";
  const rows = metrics.filter(r => (!target || (target === "hit" ? r.target_hit : !r.target_hit)) && JSON.stringify(r).toLowerCase().includes(q));
  renderTable(document.getElementById("metricsTable"), rows, metricColumns(), metricFormats());
}

function renderReports(reports) {
  const q = document.getElementById("reportSearch")?.value.toLowerCase() || "";
  const rows = reports.filter(r => JSON.stringify(r).toLowerCase().includes(q));
  const stats = document.getElementById("reportStats");
  if (stats) {
    stats.innerHTML = [
      ["Reports", rows.length],
      ["With target", rows.filter(r => r["Base 목표가"]).length],
      ["Markdown", rows.filter(r => r.Markdown).length],
    ].map(([k, v]) => `<div class="metric-card"><span>${k}</span><strong>${v}</strong></div>`).join("");
  }
  renderTable(document.getElementById("reportsTable"), rows, reportColumns(), {
    "GitHub PDF": v => v ? `<a href="${v}">PDF</a>` : "",
    "Markdown": v => v ? `<a href="${v}">Markdown</a>` : "",
    "Report Price": num,
  });
}

Promise.all([loadJson("reports.json"), loadJson("price_metrics.json"), loadJson("portfolio_backtests.json")]).then(([reports, metrics, portfolio]) => {
  renderOverview(reports, metrics, portfolio);
  renderPortfolio(portfolio);
  renderMetrics(metrics);
  renderReports(reports);
  const cohorts = unique(portfolio.map(r => r.cohort_month));
  const rfs = unique(portfolio.map(r => String(r.risk_free_rate)));
  const strategies = unique(portfolio.map(r => r.strategy));
  const cohortEl = document.getElementById("portfolioCohort");
  const rfEl = document.getElementById("portfolioRf");
  const strategyEl = document.getElementById("portfolioStrategy");
  if (cohortEl) cohortEl.innerHTML = `<option value="">All cohorts</option>` + cohorts.map(v => `<option>${v}</option>`).join("");
  if (rfEl) rfEl.innerHTML = `<option value="">All RF</option>` + rfs.map(v => `<option value="${v}">${pct(v)}</option>`).join("");
  if (strategyEl) strategyEl.innerHTML = `<option value="">All strategies</option>` + strategies.map(v => `<option>${v}</option>`).join("");
  ["portfolioCohort", "portfolioRf", "portfolioStrategy"].forEach(id => document.getElementById(id)?.addEventListener("change", () => renderPortfolio(portfolio)));
  document.getElementById("metricsSearch")?.addEventListener("input", () => renderMetrics(metrics));
  document.getElementById("targetFilter")?.addEventListener("change", () => renderMetrics(metrics));
  document.getElementById("reportSearch")?.addEventListener("input", () => renderReports(reports));
});
