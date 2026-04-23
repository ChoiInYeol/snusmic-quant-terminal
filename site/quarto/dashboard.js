const pct = v => v === null || v === undefined || v === "" || Number.isNaN(Number(v)) ? "" : (Number(v) * 100).toFixed(1) + "%";
const num = v => v === null || v === undefined || v === "" || Number.isNaN(Number(v)) ? "" : Number(v).toLocaleString(undefined, { maximumFractionDigits: 2 });
const signClass = v => Number(v) > 0 ? "pos" : (Number(v) < 0 ? "neg" : "");
const unique = arr => [...new Set(arr.filter(v => v !== null && v !== undefined && v !== ""))].sort();
const plotConfig = { responsive: true, displayModeBar: false };
const plotBaseLayout = {
  autosize: true,
  height: 420,
  paper_bgcolor: "#fbfcfd",
  plot_bgcolor: "#fbfcfd",
  font: { color: "#18242e", family: "Inter, system-ui, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif" },
};

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

function opportunityColumns() {
  return [
    { key: "publication_date", label: "Date" },
    { key: "company", label: "Company" },
    { key: "current_price", label: "Current", num: true },
    { key: "publication_buy_price", label: "Pub price", num: true },
    { key: "lowest_price_since_publication", label: "Low price", num: true },
    { key: "q25_price_since_publication", label: "Q25 price", num: true },
    { key: "q75_price_since_publication", label: "Q75 price", num: true },
    { key: "buy_at_publication_return", label: "Pub ret", num: true },
    { key: "lowest_price_current_return", label: "Low buy ret", num: true },
    { key: "q25_price_current_return", label: "Q25 ret", num: true },
    { key: "q75_price_current_return", label: "Q75 ret", num: true },
    { key: "target_upside_remaining", label: "Target upside", num: true },
    { key: "target_hit", label: "Target" },
    { key: "first_target_hit_date", label: "Hit date" },
  ];
}

function opportunityFormats() {
  return {
    current_price: num,
    publication_buy_price: num,
    lowest_price_since_publication: num,
    q25_price_since_publication: num,
    q75_price_since_publication: num,
    buy_at_publication_return: v => `<span class="${signClass(v)}">${pct(v)}</span>`,
    lowest_price_current_return: v => `<span class="${signClass(v)}">${pct(v)}</span>`,
    q25_price_current_return: v => `<span class="${signClass(v)}">${pct(v)}</span>`,
    q75_price_current_return: v => `<span class="${signClass(v)}">${pct(v)}</span>`,
    target_upside_remaining: v => `<span class="${signClass(v)}">${pct(v)}</span>`,
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

function strategyColumns() {
  return [
    { key: "strategy_name", label: "Strategy" },
    { key: "weighting", label: "Weighting" },
    { key: "entry_rule", label: "Entry" },
    { key: "rebalance", label: "Rebalance" },
    { key: "final_wealth", label: "Wealth", num: true },
    { key: "total_return", label: "Return", num: true },
    { key: "max_drawdown", label: "MDD", num: true },
    { key: "sharpe", label: "Sharpe", num: true },
    { key: "calmar", label: "Calmar", num: true },
    { key: "exposure_ratio", label: "Exposure", num: true },
    { key: "win_rate", label: "Win", num: true },
    { key: "trade_count", label: "Trades", num: true },
  ];
}

function strategyFormats() {
  return {
    final_wealth: num,
    total_return: v => `<span class="${signClass(v)}">${pct(v)}</span>`,
    max_drawdown: pct,
    sharpe: num,
    calmar: num,
    exposure_ratio: pct,
    win_rate: pct,
  };
}

function tradeColumns() {
  return [
    { key: "date", label: "Date" },
    { key: "event_type", label: "Event" },
    { key: "company", label: "Company" },
    { key: "reason", label: "Reason" },
    { key: "price", label: "Price", num: true },
    { key: "weight", label: "Weight", num: true },
    { key: "gross_return", label: "Gross ret", num: true },
    { key: "realized_return", label: "Realized ret", num: true },
    { key: "holding_days", label: "Days", num: true },
  ];
}

function tradeFormats() {
  return {
    price: num,
    weight: pct,
    gross_return: v => `<span class="${signClass(v)}">${pct(v)}</span>`,
    realized_return: v => `<span class="${signClass(v)}">${pct(v)}</span>`,
  };
}

function positionColumns() {
  return [
    { key: "date", label: "Date" },
    { key: "company", label: "Company" },
    { key: "weight", label: "Weight", num: true },
    { key: "close", label: "Close", num: true },
    { key: "target_price", label: "Target", num: true },
    { key: "gross_return", label: "Gross ret", num: true },
    { key: "model_contribution", label: "Model contrib", num: true },
    { key: "rs_score", label: "RS", num: true },
    { key: "mtt_pass", label: "MTT" },
  ];
}

function positionFormats() {
  return {
    weight: pct,
    close: num,
    target_price: num,
    gross_return: v => `<span class="${signClass(v)}">${pct(v)}</span>`,
    model_contribution: v => `<span class="${signClass(v)}">${pct(v)}</span>`,
    rs_score: num,
    mtt_pass: v => v === true || v === "True" || v === "true" ? "pass" : "",
  };
}

function signalColumns() {
  return [
    { key: "date", label: "Date" },
    { key: "symbol", label: "Symbol" },
    { key: "close", label: "Close", num: true },
    { key: "rs_score", label: "RS", num: true },
    { key: "mtt_pass", label: "MTT" },
    { key: "pct_above_52w_low", label: "52w low +", num: true },
    { key: "pct_below_52w_high", label: "52w high gap", num: true },
    { key: "ma50", label: "MA50", num: true },
    { key: "ma150", label: "MA150", num: true },
    { key: "ma200", label: "MA200", num: true },
  ];
}

function signalFormats() {
  return {
    close: num,
    rs_score: num,
    mtt_pass: v => v === true || v === "True" || v === "true" ? "pass" : "",
    pct_above_52w_low: pct,
    pct_below_52w_high: pct,
    ma50: num,
    ma150: num,
    ma200: num,
  };
}

function bestStrategy(strategies) {
  return [...strategies].filter(r => r.status === "ok")
    .sort((a, b) => Number(b.total_return || 0) - Number(a.total_return || 0))[0];
}

function selectedRunId(defaultRows, selectId) {
  const selected = document.getElementById(selectId)?.value;
  if (selected) return selected;
  return bestStrategy(defaultRows)?.run_id || defaultRows[0]?.run_id || "";
}

function rowsForRun(rows, runId) {
  return rows.filter(r => !runId || r.run_id === runId);
}

function renderV3Overview(v3) {
  const best = bestStrategy(v3.strategyRuns);
  const stats = document.getElementById("v3OverviewStats");
  if (stats) {
    const runRows = v3.strategyRuns.filter(r => r.status === "ok");
    stats.innerHTML = [
      ["Strategies", runRows.length],
      ["Best return", best ? pct(best.total_return) : ""],
      ["Best total return", best ? pct(best.total_return) : ""],
      ["Execution events", v3.executions.length],
    ].map(([k, value]) => `<div class="metric-card"><span>${k}</span><strong>${value}</strong></div>`).join("");
  }
  const bestEl = document.getElementById("v3BestStrategy");
  if (bestEl) {
    bestEl.innerHTML = best ? `
      <div class="best-title">Best walk-forward strategy</div>
      <div class="best-main">${best.strategy_name}</div>
      <p><span class="pill">Wealth ${num(best.final_wealth)}</span><span class="pill">Return ${pct(best.total_return)}</span><span class="pill">MDD ${pct(best.max_drawdown)}</span></p>
      <p><span class="pill">${best.entry_rule}</span><span class="pill">${best.weighting}</span><span class="pill">${best.rebalance}</span></p>
    ` : "<p>No v3 strategy data yet.</p>";
  }
  renderTable(document.getElementById("v3StrategyTable"), v3.strategyRuns, strategyColumns(), strategyFormats());
  const runId = best?.run_id || "";
  renderEquityPlot(document.getElementById("v3EquityPlot"), rowsForRun(v3.equity, runId));
  renderPoolTimelinePlot(document.getElementById("v3PoolTimelinePlot"), rowsForRun(v3.poolTimeline, runId));
}

function renderEquityPlot(el, rows) {
  if (!el || !window.Plotly || !rows.length) return;
  const dates = rows.map(r => r.date);
  const equity = rows.map(r => Number(r.equity || 1));
  let peak = 1;
  const drawdown = equity.map(v => {
    peak = Math.max(peak, v);
    return v / peak - 1;
  });
  Plotly.newPlot(el, [
    { type: "scatter", mode: "lines", name: "Equity", x: dates, y: equity, line: { color: "#126b83", width: 2 } },
    { type: "scatter", mode: "lines", name: "Drawdown", x: dates, y: drawdown, yaxis: "y2", line: { color: "#b53b2d", width: 1.5 } },
  ], {
    ...plotBaseLayout,
    margin: { l: 55, r: 55, t: 10, b: 40 },
    yaxis: { title: "Equity", gridcolor: "#e2e8ef" },
    yaxis2: { title: "Drawdown", overlaying: "y", side: "right", tickformat: ".0%" },
    legend: { orientation: "h" },
  }, plotConfig).then(() => Plotly.Plots.resize(el));
}

function renderPoolTimelinePlot(el, rows) {
  if (!el || !window.Plotly || !rows.length) return;
  Plotly.newPlot(el, [
    { type: "scatter", mode: "lines", name: "Candidate", x: rows.map(r => r.date), y: rows.map(r => Number(r.candidate_count || 0)), line: { color: "#126b83" } },
    { type: "scatter", mode: "lines", name: "Execution", x: rows.map(r => r.date), y: rows.map(r => Number(r.execution_count || 0)), line: { color: "#d47a00" } },
  ], {
    ...plotBaseLayout,
    margin: { l: 55, r: 20, t: 10, b: 40 },
    yaxis: { title: "Pool size", gridcolor: "#e2e8ef" },
    legend: { orientation: "h" },
  }, plotConfig).then(() => Plotly.Plots.resize(el));
}

function renderStrategyPage(v3) {
  populateStrategyControls(v3.strategyRuns, "strategyRunSelect");
  const weighting = document.getElementById("strategyWeightingFilter")?.value || "";
  const entry = document.getElementById("strategyEntryFilter")?.value || "";
  const rows = v3.strategyRuns.filter(r => (!weighting || r.weighting === weighting) && (!entry || r.entry_rule === entry));
  const runId = selectedRunId(rows, "strategyRunSelect");
  renderEquityPlot(document.getElementById("strategyEquityDrawdownPlot"), rowsForRun(v3.equity, runId));
  renderStrategyRiskMap(v3.strategyRuns);
  renderTable(document.getElementById("strategyLeaderboardTable"), rows, strategyColumns(), strategyFormats());
  renderTable(document.getElementById("optunaTrialsTable"), [...v3.optunaTrials].sort((a, b) => Number(b.objective || 0) - Number(a.objective || 0)), [
    { key: "trial", label: "Trial", num: true },
    { key: "objective", label: "Objective ret", num: true },
    { key: "weighting", label: "Weighting" },
    { key: "entry_rule", label: "Entry" },
    { key: "rebalance", label: "Rebalance" },
    { key: "rs_threshold", label: "RS", num: true },
    { key: "max_pool_months", label: "Pool M", num: true },
    { key: "stop_loss_pct", label: "Stop", num: true },
    { key: "reward_risk", label: "R:R", num: true },
    { key: "total_return", label: "Return", num: true },
    { key: "max_drawdown", label: "MDD", num: true },
  ], {
    objective: v => `<span class="${signClass(v)}">${pct(v)}</span>`,
    stop_loss_pct: pct,
    total_return: v => `<span class="${signClass(v)}">${pct(v)}</span>`,
    max_drawdown: pct,
  });
}

function renderStrategyRiskMap(rows) {
  const el = document.getElementById("strategyRiskMapPlot");
  if (!el || !window.Plotly || !rows.length) return;
  Plotly.newPlot(el, [{
    type: "scatter",
    mode: "markers",
    x: rows.map(r => Number(r.max_drawdown || 0)),
    y: rows.map(r => Number(r.total_return || 0)),
    text: rows.map(r => `${r.strategy_name}<br>${r.entry_rule}<br>${r.weighting}<br>Return ${pct(r.total_return)}`),
    marker: { size: rows.map(r => 8 + Number(r.exposure_ratio || 0) * 18), color: rows.map(r => Number(r.sharpe || 0)), colorscale: "Viridis", showscale: true },
    hovertemplate: "%{text}<br>MDD %{x:.1%}<br>Total return %{y:.1%}<extra></extra>",
  }], {
    ...plotBaseLayout,
    margin: { l: 55, r: 20, t: 10, b: 45 },
    xaxis: { title: "Max drawdown", tickformat: ".0%", gridcolor: "#e2e8ef" },
    yaxis: { title: "Total return", tickformat: ".0%", gridcolor: "#e2e8ef" },
  }, plotConfig).then(() => Plotly.Plots.resize(el));
}

function populateStrategyControls(rows, selectId) {
  const runSelect = document.getElementById(selectId);
  if (runSelect && !runSelect.dataset.ready) {
    const best = bestStrategy(rows);
    runSelect.innerHTML = rows.map(r => `<option value="${r.run_id}" ${best && r.run_id === best.run_id ? "selected" : ""}>${r.strategy_name}</option>`).join("");
    runSelect.dataset.ready = "true";
  }
  const weighting = document.getElementById("strategyWeightingFilter");
  if (weighting && !weighting.dataset.ready) {
    weighting.innerHTML = `<option value="">All weighting</option>` + unique(rows.map(r => r.weighting)).map(v => `<option>${v}</option>`).join("");
    weighting.dataset.ready = "true";
  }
  const entry = document.getElementById("strategyEntryFilter");
  if (entry && !entry.dataset.ready) {
    entry.innerHTML = `<option value="">All entry rules</option>` + unique(rows.map(r => r.entry_rule)).map(v => `<option>${v}</option>`).join("");
    entry.dataset.ready = "true";
  }
}

function renderPoolsPage(v3) {
  populateRunOnly(v3.strategyRuns, "poolRunSelect");
  const runId = selectedRunId(v3.strategyRuns, "poolRunSelect");
  const q = document.getElementById("poolSearch")?.value.toLowerCase() || "";
  const match = row => !q || JSON.stringify(row).toLowerCase().includes(q);
  renderPoolTimelinePlot(document.getElementById("poolTimelinePlot"), rowsForRun(v3.poolTimeline, runId));
  renderHoldingsArea(document.getElementById("holdingsAreaPlot"), rowsForRun(v3.positions, runId));
  renderTable(document.getElementById("tradeJournalTable"), rowsForRun(v3.executions, runId).filter(match), tradeColumns(), tradeFormats());
  renderTable(document.getElementById("positionLedgerTable"), rowsForRun(v3.positions, runId).filter(match).slice(-250).reverse(), positionColumns(), positionFormats());
  renderTable(document.getElementById("candidateEventsTable"), rowsForRun(v3.candidateEvents, runId).filter(match).slice(-250).reverse(), [
    { key: "date", label: "Date" },
    { key: "event_type", label: "Event" },
    { key: "company", label: "Company" },
    { key: "reason", label: "Reason" },
    { key: "close", label: "Close", num: true },
    { key: "target_price", label: "Target", num: true },
  ], { close: num, target_price: num });
}

function renderHoldingsArea(el, rows) {
  if (!el || !window.Plotly || !rows.length) return;
  const symbols = unique(rows.map(r => r.company || r.symbol)).slice(0, 15);
  const traces = symbols.map(name => {
    const filtered = rows.filter(r => (r.company || r.symbol) === name);
    return { type: "scatter", mode: "lines", stackgroup: "one", name, x: filtered.map(r => r.date), y: filtered.map(r => Number(r.weight || 0)), hovertemplate: `${name}<br>%{x}<br>Weight %{y:.1%}<extra></extra>` };
  });
  Plotly.newPlot(el, traces, {
    ...plotBaseLayout,
    margin: { l: 55, r: 20, t: 10, b: 40 },
    yaxis: { title: "Weight", tickformat: ".0%", gridcolor: "#e2e8ef" },
    legend: { orientation: "h" },
  }, plotConfig).then(() => Plotly.Plots.resize(el));
}

function populateRunOnly(rows, selectId) {
  const el = document.getElementById(selectId);
  if (el && !el.dataset.ready) {
    const best = bestStrategy(rows);
    el.innerHTML = rows.map(r => `<option value="${r.run_id}" ${best && r.run_id === best.run_id ? "selected" : ""}>${r.strategy_name}</option>`).join("");
    el.dataset.ready = "true";
  }
}

function renderSignalsPage(v3) {
  populateRunOnly(v3.strategyRuns, "signalRunSelect");
  const runId = selectedRunId(v3.strategyRuns, "signalRunSelect");
  const q = document.getElementById("signalSearch")?.value.toLowerCase() || "";
  const rows = rowsForRun(v3.signals, runId).filter(r => !q || JSON.stringify(r).toLowerCase().includes(q));
  renderSignalScatter(document.getElementById("signalScatterPlot"), rows);
  renderTable(document.getElementById("signalTable"), rows, signalColumns(), signalFormats());
}

function renderSignalScatter(el, rows) {
  if (!el || !window.Plotly || !rows.length) return;
  Plotly.newPlot(el, [{
    type: "scatter",
    mode: "markers",
    x: rows.map(r => Number(r.rs_score || 0)),
    y: rows.map(r => Number(r.pct_above_52w_low || 0)),
    text: rows.map(r => `${r.symbol}<br>${r.date}<br>MTT ${r.mtt_pass}<br>52w high gap ${pct(r.pct_below_52w_high)}`),
    marker: { size: rows.map(r => (r.mtt_pass === true || r.mtt_pass === "True" || r.mtt_pass === "true") ? 13 : 8), color: rows.map(r => Number(r.pct_below_52w_high || 0)), colorscale: "RdYlGn", showscale: true },
    hovertemplate: "%{text}<br>RS %{x:.1f}<br>52w low +%{y:.1%}<extra></extra>",
  }], {
    ...plotBaseLayout,
    margin: { l: 55, r: 20, t: 10, b: 45 },
    xaxis: { title: "RS score", gridcolor: "#e2e8ef" },
    yaxis: { title: "Above 52w low", tickformat: ".0%", gridcolor: "#e2e8ef" },
  }, plotConfig).then(() => Plotly.Plots.resize(el));
}

function renderFrontier(portfolio) {
  const rows = portfolio.filter(r => r.expected_volatility !== null && r.expected_return !== null);
  const el = document.getElementById("frontierPlot");
  if (!el || !rows.length || !window.Plotly) return;
  const strategies = unique(rows.map(r => r.strategy));
  const traces = strategies.map(strategy => {
    const subset = rows.filter(r => r.strategy === strategy);
    return {
      type: "scatter",
      mode: "markers",
      name: strategy,
      x: subset.map(r => Number(r.expected_volatility)),
      y: subset.map(r => Number(r.expected_return)),
      marker: {
        size: subset.map(r => 8 + Math.max(0, Number(r.realized_return || 0)) * 5),
        opacity: 0.72,
      },
      text: subset.map(r => `${r.cohort_month}<br>${r.strategy}<br>RF ${pct(r.risk_free_rate)}<br>Realized ${pct(r.realized_return)}<br>${holdings(r)}`),
      hovertemplate: "%{text}<br>Expected vol %{x:.1%}<br>Expected return %{y:.1%}<extra></extra>",
    };
  });
  Plotly.newPlot(el, traces, {
    ...plotBaseLayout,
    margin: { l: 55, r: 20, t: 10, b: 50 },
    xaxis: { title: "Expected volatility", tickformat: ".0%", gridcolor: "#e2e8ef", zerolinecolor: "#b8c4cf" },
    yaxis: { title: "Expected return", tickformat: ".0%", gridcolor: "#e2e8ef", zerolinecolor: "#b8c4cf" },
    legend: { orientation: "h" },
  }, plotConfig).then(() => Plotly.Plots.resize(el));
}

function renderOverview(reports, metrics, portfolio) {
  const el = document.getElementById("overviewStats");
  const okPrices = metrics.filter(r => r.status === "ok");
  const targetHits = okPrices.filter(r => r.target_hit).length;
  const best = topPortfolios(portfolio, 1)[0];
  const avgRet = okPrices.reduce((s, r) => s + Number(r.buy_at_publication_return || 0), 0) / Math.max(1, okPrices.length);
  if (el) {
    el.innerHTML = [
      ["Reports", reports.length],
      ["Price coverage", `${okPrices.length}/${metrics.length}`],
      ["Target hit ratio", pct(targetHits / Math.max(1, okPrices.length))],
      ["Avg post-publication return", pct(avgRet)],
    ].map(([k, v]) => `<div class="metric-card"><span>${k}</span><strong>${v}</strong></div>`).join("");
  }
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
  renderOpportunityPlot(metrics);
  renderTable(document.getElementById("topPortfolioTable"), topPortfolios(portfolio), portfolioColumns(), portfolioFormats());
  renderPriceOpportunitySnapshot(metrics);
}

function renderPriceOpportunitySnapshot(metrics) {
  const q = document.getElementById("opportunitySearch")?.value.toLowerCase() || "";
  const target = document.getElementById("opportunityTargetFilter")?.value || "";
  const rows = [...metrics]
    .filter(r => r.status === "ok")
    .filter(r => !target || (target === "hit" ? r.target_hit : !r.target_hit))
    .filter(r => !q || JSON.stringify(r).toLowerCase().includes(q))
    .sort((a, b) => Number(b.target_upside_remaining || 0) - Number(a.target_upside_remaining || 0));
  renderTable(document.getElementById("priceOpportunityTable"), rows, opportunityColumns(), opportunityFormats());
}

function renderOpportunityPlot(metrics) {
  const el = document.getElementById("opportunityPlot");
  if (!el || !window.Plotly) return;
  const rows = [...metrics].filter(r => r.status === "ok").sort((a, b) => Number(b.low_to_high_return || 0) - Number(a.low_to_high_return || 0)).slice(0, 18).reverse();
  Plotly.newPlot(el, [
    {
      type: "bar",
      orientation: "h",
      name: "Low→High return",
      y: rows.map(r => r.company),
      x: rows.map(r => Number(r.low_to_high_return || 0)),
      hovertemplate: "%{y}<br>Low→High %{x:.1%}<extra></extra>",
    },
    {
      type: "bar",
      orientation: "h",
      name: "Target upside",
      y: rows.map(r => r.company),
      x: rows.map(r => Number(r.target_upside_remaining || 0)),
      hovertemplate: "%{y}<br>Target upside %{x:.1%}<extra></extra>",
    },
  ], {
    ...plotBaseLayout,
    barmode: "group",
    margin: { l: 140, r: 20, t: 10, b: 40 },
    xaxis: { tickformat: ".0%", gridcolor: "#e2e8ef", zerolinecolor: "#b8c4cf" },
    yaxis: { automargin: true },
    legend: { orientation: "h" },
  }, plotConfig).then(() => Plotly.Plots.resize(el));
}

function renderPortfolio(portfolio) {
  const cohort = document.getElementById("portfolioCohort")?.value || "";
  const rf = document.getElementById("portfolioRf")?.value || "";
  const strategy = document.getElementById("portfolioStrategy")?.value || "";
  const rows = portfolio.filter(r => (!cohort || r.cohort_month === cohort) && (!rf || String(r.risk_free_rate) === rf) && (!strategy || r.strategy === strategy));
  const table = document.getElementById("portfolioTable");
  if (table) table.dataset.sortKey = table.dataset.sortKey || "realized_return";
  renderTable(table, rows, portfolioColumns(), portfolioFormats());
  renderPortfolioBarPlot(rows);
}

function renderPortfolioBarPlot(rows) {
  const el = document.getElementById("portfolioBarPlot");
  if (!el || !window.Plotly) return;
  const top = [...rows].filter(r => r.realized_return !== null).sort((a, b) => Number(b.realized_return) - Number(a.realized_return)).slice(0, 20).reverse();
  Plotly.newPlot(el, [{
    type: "bar",
    orientation: "h",
    y: top.map(r => `${r.cohort_month} · ${r.strategy} · ${pct(r.risk_free_rate)}`),
    x: top.map(r => Number(r.realized_return || 0)),
    text: top.map(r => holdings(r).replaceAll("<br>", "<br>")),
    hovertemplate: "%{y}<br>Realized %{x:.1%}<br>%{text}<extra></extra>",
    marker: { color: top.map(r => Number(r.realized_return || 0) >= 0 ? "#126b83" : "#b53b2d") },
  }], {
    ...plotBaseLayout,
    margin: { l: 190, r: 20, t: 10, b: 40 },
    xaxis: { title: "Realized forward return", tickformat: ".0%", gridcolor: "#e2e8ef", zerolinecolor: "#b8c4cf" },
    yaxis: { automargin: true },
  }, plotConfig).then(() => Plotly.Plots.resize(el));
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

Promise.all([
  loadJson("reports.json"),
  loadJson("price_metrics.json"),
  loadJson("portfolio_backtests.json"),
  loadJson("quant_v3/strategy_runs.json"),
  loadJson("quant_v3/equity_daily.json"),
  loadJson("quant_v3/pool_timeline.json"),
  loadJson("quant_v3/candidate_pool_events.json"),
  loadJson("quant_v3/execution_events.json"),
  loadJson("quant_v3/positions_daily.json"),
  loadJson("quant_v3/signals_daily.json"),
  loadJson("quant_v3/strategy_heatmap.json"),
  loadJson("quant_v3/optuna_trials.json"),
]).then(([reports, metrics, portfolio, strategyRuns, equity, poolTimeline, candidateEvents, executions, positions, signals, heatmap, optunaTrials]) => {
  const v3 = { strategyRuns, equity, poolTimeline, candidateEvents, executions, positions, signals, heatmap, optunaTrials };
  renderV3Overview(v3);
  renderStrategyPage(v3);
  renderPoolsPage(v3);
  renderSignalsPage(v3);
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
  ["strategyRunSelect", "strategyWeightingFilter", "strategyEntryFilter"].forEach(id => document.getElementById(id)?.addEventListener("change", () => renderStrategyPage(v3)));
  ["poolRunSelect", "poolSearch"].forEach(id => {
    const el = document.getElementById(id);
    const eventName = id.endsWith("Search") ? "input" : "change";
    el?.addEventListener(eventName, () => renderPoolsPage(v3));
  });
  ["signalRunSelect", "signalSearch"].forEach(id => {
    const el = document.getElementById(id);
    const eventName = id.endsWith("Search") ? "input" : "change";
    el?.addEventListener(eventName, () => renderSignalsPage(v3));
  });
  ["opportunitySearch", "opportunityTargetFilter"].forEach(id => {
    const el = document.getElementById(id);
    const eventName = id.endsWith("Search") ? "input" : "change";
    el?.addEventListener(eventName, () => renderPriceOpportunitySnapshot(metrics));
  });
  document.getElementById("metricsSearch")?.addEventListener("input", () => renderMetrics(metrics));
  document.getElementById("targetFilter")?.addEventListener("change", () => renderMetrics(metrics));
  document.getElementById("reportSearch")?.addEventListener("input", () => renderReports(reports));
  window.addEventListener("resize", () => {
    ["frontierPlot", "opportunityPlot", "portfolioBarPlot", "v3EquityPlot", "v3PoolTimelinePlot", "strategyEquityDrawdownPlot", "strategyRiskMapPlot", "poolTimelinePlot", "holdingsAreaPlot", "signalScatterPlot"].forEach(id => {
      const el = document.getElementById(id);
      if (el && window.Plotly) Plotly.Plots.resize(el);
    });
  });
});
