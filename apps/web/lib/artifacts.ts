import 'server-only';
import fs from 'node:fs';
import path from 'node:path';

const repoRoot = path.resolve(/* turbopackIgnore: true */ process.cwd(), '../..');

type RawReport = Record<string, unknown>;

type CsvRow = Record<string, string>;

export type ReportRow = {
  reportId: string;
  symbol: string;
  company: string;
  publicationDate: string;
  title: string;
  exchange: string;
  markdownFilename: string;
  pdfFilename: string;
  pdfUrl: string;
  entryPriceKrw: number | null;
  targetPriceKrw: number | null;
  targetUpsideAtPub: number | null;
  targetHit: boolean;
  targetHitDate: string | null;
  daysToTarget: number | null;
  lastCloseKrw: number | null;
  lastCloseDate: string | null;
  currentReturn: number | null;
  peakReturn: number | null;
  troughReturn: number | null;
  targetGapPct: number | null;
  caveatFlags: string[];
};


export type HoldingRow = {
  persona: string;
  symbol: string;
  company: string;
  qty: number | null;
  avgCostKrw: number | null;
  lastCloseKrw: number | null;
  marketValueKrw: number | null;
  unrealizedPnlKrw: number | null;
  unrealizedReturn: number | null;
  holdingDays: number | null;
  firstBuyDate: string | null;
};

export type MonthlyHoldingRow = {
  persona: string;
  monthEnd: string;
  symbol: string;
  company: string;
  qty: number | null;
  marketValueKrw: number | null;
  weightInPortfolio: number | null;
};

export type TradeRow = {
  persona: string;
  date: string;
  symbol: string;
  side: 'buy' | 'sell' | string;
  qty: number | null;
  fillPriceKrw: number | null;
  grossKrw: number | null;
  cashAfterKrw: number | null;
  reason: string;
  reportId: string | null;
};

export type PositionEpisodeRow = {
  persona: string;
  symbol: string;
  company: string;
  openDate: string;
  closeDate: string | null;
  holdingDays: number | null;
  buyFills: number | null;
  sellFills: number | null;
  totalQtyBought: number | null;
  totalQtySold: number | null;
  avgEntryPriceKrw: number | null;
  avgExitPriceKrw: number | null;
  realizedPnlKrw: number | null;
  unrealizedPnlKrw: number | null;
  lastCloseKrw: number | null;
  status: string;
  exitReasons: string;
};

export type PricePoint = { time: string; value: number };

export type ReportTargetDigest = {
  reportId: string;
  symbol: string;
  company: string;
  exchange: string;
  marketRegion: 'domestic' | 'overseas';
  publicationDate: string;
  targetPriceKrw: number | null;
  targetUpsideAtPub: number | null;
};
export type EquityPoint = {
  persona: string;
  date: string;
  equityKrw: number | null;
  contributedCapitalKrw: number | null;
  cumulativeReturn: number | null;
};
export type SummaryRow = {
  persona: string;
  label?: string;
  finalEquityKrw: number | null;
  totalContributedKrw: number | null;
  cumulativeDepositsKrw?: number | null;
  netProfitKrw: number | null;
  irr?: number | null;
  moneyWeightedReturn?: number | null;
  maxDrawdown: number | null;
  tradeCount: number | null;
};
export type DataQuality = {
  extractedReports: number;
  reportsWithPrices: number;
  totalReports: number;
  targetHitRate: number;
  missingPriceSymbols: number;
  extractionQuality: Record<string, unknown>;
};

export type WebPersona = {
  persona: string;
  label: string;
  final_equity_krw: number;
  total_contributed_krw?: number;
  net_profit_krw: number;
  money_weighted_return: number;
  cagr: number;
  max_drawdown: number;
  trade_count: number;
  open_positions: number;
};

export type WebReportRankingRow = {
  report_id: string;
  symbol: string;
  company: string;
  publication_date: string;
  date?: string;
  entry_price_krw: number | null;
  target_price_krw: number | null;
  target_upside_at_pub: number | null;
  target_hit: boolean;
  target_hit_date: string | null;
  days_to_target: number | null;
  last_close_krw: number | null;
  last_close_date: string | null;
  current_return: number | null;
  peak_return: number | null;
  trough_return: number | null;
  target_gap_pct: number | null;
  value?: number | null;
};

export type WebOverview = {
  baseline_personas: WebPersona[];
  generated_from?: Record<string, string>;
  report_counts?: Record<string, number>;
  simulation_window?: Record<string, string | null>;
  target_stats?: Record<string, number | null>;
};

export type WebReportRankings = {
  top_winners?: WebReportRankingRow[];
  top_losers?: WebReportRankingRow[];
  most_aggressive_targets?: WebReportRankingRow[];
  fastest_hits?: WebReportRankingRow[];
  biggest_open_target_gaps?: WebReportRankingRow[];
  best_current_returns?: WebReportRankingRow[];
  worst_current_returns?: WebReportRankingRow[];
};

export type StrategyRunArtifact = {
  run_id: string;
  trial_number?: number;
  label: string;
  scope?: string;
  sampler?: string;
  params?: Record<string, unknown>;
  metrics: Record<string, number | null | undefined>;
  warnings?: string[];
};

export type StrategyRunsArtifact = {
  schema_version?: number;
  study_name?: string;
  scope?: string;
  disclaimer?: string;
  best_run_id?: string;
  runs: StrategyRunArtifact[];
};

export type StrategyExperimentPosition = {
  runId: string;
  symbol: string;
  company: string;
  publicationDate: string;
  exitDate: string | null;
  status: 'closed' | 'open';
  weight: number;
  entryPriceKrw: number | null;
  targetPriceKrw: number | null;
  expectedReturn: number | null;
  realizedReturn: number | null;
  targetHit: boolean;
};

export type StrategyExperimentTrade = {
  runId: string;
  date: string;
  side: 'buy' | 'sell';
  symbol: string;
  company: string;
  weight: number;
  referencePriceKrw: number | null;
  reason: string;
};

export type StrategyExperiment = {
  runId: string;
  positions: StrategyExperimentPosition[];
  trades: StrategyExperimentTrade[];
  cumulativeReturnSeries: PricePoint[];
};

export type ParameterImportanceArtifact = {
  schema_version?: number;
  study_name?: string;
  method?: string;
  parameters?: { parameter: string; importance: number }[];
};

export type WebDataQuality = {
  coverage?: Record<string, number>;
  extraction_quality?: Record<string, unknown>;
  missing_symbols?: { symbol: string; company?: string; reason?: string }[];
};

export type Insight = { id: string; title: string; sentence: string; metric?: number | string | null; related_report_ids?: string[] };

function fullPath(relativePath: string): string {
  return path.join(repoRoot, relativePath);
}

function readText(relativePath: string): string {
  return fs.readFileSync(fullPath(relativePath), 'utf8');
}

function readJson<T>(relativePath: string, fallback: T): T {
  const pathName = fullPath(relativePath);
  if (!fs.existsSync(pathName)) return fallback;
  return JSON.parse(fs.readFileSync(pathName, 'utf8')) as T;
}

function parseCsv(text: string): CsvRow[] {
  const rows: string[][] = [];
  let field = '';
  let row: string[] = [];
  let inQuotes = false;
  for (let index = 0; index < text.length; index += 1) {
    const char = text[index];
    const next = text[index + 1];
    if (char === '"') {
      if (inQuotes && next === '"') { field += '"'; index += 1; } else { inQuotes = !inQuotes; }
      continue;
    }
    if (char === ',' && !inQuotes) { row.push(field); field = ''; continue; }
    if ((char === '\n' || char === '\r') && !inQuotes) {
      if (char === '\r' && next === '\n') index += 1;
      row.push(field);
      if (row.some((cell) => cell.length > 0)) rows.push(row);
      row = []; field = ''; continue;
    }
    field += char;
  }
  if (field.length > 0 || row.length > 0) {
    row.push(field);
    if (row.some((cell) => cell.length > 0)) rows.push(row);
  }
  const [headers, ...body] = rows;
  if (!headers) return [];
  return body.map((cells) => Object.fromEntries(headers.map((header, index) => [header, cells[index] ?? ''])));
}

function num(value: unknown): number | null {
  if (value === undefined || value === null || value === '') return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function bool(value: unknown): boolean {
  return value === true || value === 'True' || value === 'true' || value === '1' || value === 1;
}

function strOrNull(value: unknown): string | null {
  if (value === undefined || value === null || value === '') return null;
  return String(value);
}

let reportCache: ReportRow[] | undefined;
export function getReportRows(): ReportRow[] {
  if (reportCache) return reportCache;
  const raw = readJson<RawReport[]>('data/web/reports.json', []);
  if (raw.length) {
    reportCache = raw.map(fromRawReport).sort((a, b) => b.publicationDate.localeCompare(a.publicationDate) || a.company.localeCompare(b.company, 'ko-KR'));
    return reportCache;
  }
  const reportMeta = new Map(parseCsv(readText('data/warehouse/reports.csv')).map((row) => [row.report_id, row]));
  reportCache = parseCsv(readText('data/sim/report_performance.csv')).map((row) => fromRawReport({ ...reportMeta.get(row.report_id), ...row, date: row.publication_date })).sort((a, b) => b.publicationDate.localeCompare(a.publicationDate));
  return reportCache;
}

function fromRawReport(row: RawReport): ReportRow {
  return {
    reportId: String(row.report_id ?? row.reportId ?? ''),
    symbol: String(row.symbol ?? ''),
    company: String(row.company ?? ''),
    publicationDate: String(row.date ?? row.publication_date ?? row.publicationDate ?? ''),
    title: String(row.title ?? row.company ?? ''),
    exchange: String(row.exchange ?? ''),
    markdownFilename: String(row.markdown_filename ?? row.markdownFilename ?? ''),
    pdfFilename: String(row.pdf_filename ?? row.pdfFilename ?? ''),
    pdfUrl: String(row.pdf_url ?? row.pdfUrl ?? ''),
    entryPriceKrw: num(row.entry_price_krw ?? row.publication_price_krw ?? row.entryPriceKrw),
    targetPriceKrw: num(row.target_price_krw ?? row.targetPriceKrw),
    targetUpsideAtPub: num(row.target_upside_at_pub ?? row.targetUpsideAtPub),
    targetHit: bool(row.target_hit ?? row.targetHit),
    targetHitDate: strOrNull(row.target_hit_date ?? row.targetHitDate),
    daysToTarget: num(row.days_to_target ?? row.daysToTarget),
    lastCloseKrw: num(row.last_close_krw ?? row.lastCloseKrw),
    lastCloseDate: strOrNull(row.last_close_date ?? row.lastCloseDate),
    currentReturn: num(row.current_return ?? row.currentReturn),
    peakReturn: num(row.peak_return ?? row.peakReturn),
    troughReturn: num(row.trough_return ?? row.troughReturn),
    targetGapPct: num(row.target_gap_pct ?? row.targetGapPct),
    caveatFlags: Array.isArray(row.caveat_flags) ? row.caveat_flags : [],
  };
}

export function getReportById(reportId: string): ReportRow | undefined {
  return getReportRows().find((report) => report.reportId === reportId);
}

export function getReportsBySymbol(symbol: string): ReportRow[] {
  const normalized = symbol.toUpperCase();
  return getReportRows()
    .filter((report) => report.symbol.toUpperCase() === normalized)
    .sort((a, b) => b.publicationDate.localeCompare(a.publicationDate) || b.reportId.localeCompare(a.reportId));
}

export function getReportBySymbol(symbol: string): ReportRow | undefined {
  return getReportsBySymbol(symbol)[0];
}

export function getReportSymbolById(reportId: string | null | undefined): string | null {
  if (!reportId) return null;
  return getReportById(reportId)?.symbol ?? null;
}

export function getReportTargetDigests(): ReportTargetDigest[] {
  return getReportRows().map((report) => ({
    reportId: report.reportId,
    symbol: report.symbol,
    company: report.company,
    exchange: report.exchange,
    marketRegion: marketRegionForSymbol(report.symbol, report.exchange),
    publicationDate: report.publicationDate,
    targetPriceKrw: report.targetPriceKrw,
    targetUpsideAtPub: report.targetUpsideAtPub,
  }));
}

export function getLatestReportTargetsBySymbol(): Record<string, ReportTargetDigest> {
  const out: Record<string, ReportTargetDigest> = {};
  for (const report of getReportTargetDigests()) {
    const previous = out[report.symbol];
    if (!previous || report.publicationDate > previous.publicationDate) out[report.symbol] = report;
  }
  return out;
}

export function getReportTargetsById(): Record<string, ReportTargetDigest> {
  return Object.fromEntries(getReportTargetDigests().map((report) => [report.reportId, report]));
}

export function marketRegionForSymbol(symbol: string, exchange?: string): 'domestic' | 'overseas' {
  const upperExchange = (exchange ?? '').toUpperCase();
  if (symbol.endsWith('.KS') || symbol.endsWith('.KQ') || upperExchange === 'KRX' || upperExchange === 'KOSPI' || upperExchange === 'KOSDAQ') return 'domestic';
  return 'overseas';
}

export function getPriceSeries(symbol: string, startDate?: string, endDate?: string | null): PricePoint[] {
  const artifact = readJson<{ prices: Array<Record<string, unknown>> }>(`data/web/prices/${symbol}.json`, { prices: [] });
  const stop = endDate ?? '9999-99-99';
  return artifact.prices
    .filter((point) => (!startDate || String(point.date) >= startDate) && String(point.date) <= stop)
    .map((point) => ({ time: String(point.date), value: num(point.close_krw ?? point.close) ?? 0 }))
    .filter((point) => point.value > 0);
}

export function getMarkdownSnippet(report: ReportRow): string {
  if (!report.markdownFilename) return '이 리포트에는 markdown 추출 파일이 기록되어 있지 않습니다.';
  const markdownPath = fullPath(`data/markdown/${report.markdownFilename}`);
  if (!fs.existsSync(markdownPath)) return `markdown 추출 파일을 찾을 수 없습니다: ${report.markdownFilename}`;
  return fs.readFileSync(markdownPath, 'utf8').slice(0, 5000);
}

export function getSummaryRows(): SummaryRow[] {
  const overview = getOverview();
  if (overview.baseline_personas?.length) {
    return overview.baseline_personas.map((row) => ({
      persona: row.persona,
      label: row.label,
      finalEquityKrw: num(row.final_equity_krw),
      totalContributedKrw: num(row.total_contributed_krw),
      netProfitKrw: num(row.net_profit_krw),
      moneyWeightedReturn: num(row.money_weighted_return),
      maxDrawdown: num(row.max_drawdown),
      tradeCount: num(row.trade_count),
    }));
  }
  if (!fs.existsSync(fullPath('data/sim/summary.csv'))) return [];
  return parseCsv(readText('data/sim/summary.csv')).map((row) => ({
    persona: row.persona,
    label: row.label,
    finalEquityKrw: num(row.final_equity_krw),
    totalContributedKrw: num(row.total_contributed_krw),
    cumulativeDepositsKrw: num(row.cumulative_deposits_krw),
    netProfitKrw: num(row.net_profit_krw),
    irr: num(row.irr),
    maxDrawdown: num(row.max_drawdown),
    tradeCount: num(row.trade_count),
  }));
}

export function getDataQuality(): DataQuality {
  const web = getWebDataQuality();
  const reports = getReportRows();
  const targetHitCount = reports.filter((report) => report.targetHit).length;
  return {
    extractedReports: Number(web.coverage?.warehouse_reports ?? web.coverage?.extracted_reports ?? reports.length),
    reportsWithPrices: Number(web.coverage?.report_performance_rows ?? reports.length),
    totalReports: Number(web.coverage?.warehouse_reports ?? reports.length),
    targetHitRate: targetHitCount / Math.max(1, reports.length),
    missingPriceSymbols: web.missing_symbols?.length ?? 0,
    extractionQuality: web.extraction_quality ?? {},
  };
}

export function getWebDataQuality(): WebDataQuality {
  return readJson<WebDataQuality>('data/web/data-quality.json', {});
}

export function getOverview(): WebOverview {
  return readJson<WebOverview>('data/web/overview.json', {
    baseline_personas: [],
    report_counts: { price_matched_reports: getReportRows().length },
    target_stats: { target_hit_rate: getDataQuality().targetHitRate, target_hit_count: getReportRows().filter((report) => report.targetHit).length },
  });
}

export function getReportRankings(): WebReportRankings {
  const raw = readJson<WebReportRankings>('data/web/report-rankings.json', {});
  return {
    ...raw,
    top_winners: raw.top_winners ?? raw.best_current_returns,
    top_losers: raw.top_losers ?? raw.worst_current_returns,
  };
}

export const getRankings = getReportRankings;

export function getInsights(): Insight[] {
  return readJson<Insight[]>('data/web/insights.json', []);
}

export function getStrategyRuns(): StrategyRunsArtifact {
  return readJson<StrategyRunsArtifact>('data/web/strategy-runs.json', readJson<StrategyRunsArtifact>('apps/web/public/artifacts/strategy-runs.json', { runs: [], study_name: 'No local export yet' }));
}

export function getParameterImportance(): ParameterImportanceArtifact {
  return readJson<ParameterImportanceArtifact>('data/web/parameter-importance.json', readJson<ParameterImportanceArtifact>('apps/web/public/artifacts/parameter-importance.json', { parameters: [] }));
}

export function getDownloadHref(fileName: string): string {
  return `/downloads/${fileName}`;
}

export function readDownloadCsv(fileName: string): string {
  return readText(`data/web/${fileName}`);
}

let holdingsCache: HoldingRow[] | undefined;
export function getCurrentHoldings(): HoldingRow[] {
  if (holdingsCache) return holdingsCache;
  const raw = readJson<RawReport[]>('data/web/current-holdings.json', []);
  holdingsCache = raw.map((row) => ({
    persona: String(row.persona ?? ''),
    symbol: String(row.symbol ?? ''),
    company: String(row.company ?? row.symbol ?? ''),
    qty: num(row.qty),
    avgCostKrw: num(row.avg_cost_krw ?? row.avgCostKrw),
    lastCloseKrw: num(row.last_close_krw ?? row.lastCloseKrw),
    marketValueKrw: num(row.market_value_krw ?? row.marketValueKrw),
    unrealizedPnlKrw: num(row.unrealized_pnl_krw ?? row.unrealizedPnlKrw),
    unrealizedReturn: num(row.unrealized_return ?? row.unrealizedReturn),
    holdingDays: num(row.holding_days ?? row.holdingDays),
    firstBuyDate: strOrNull(row.first_buy_date ?? row.firstBuyDate),
  })).sort((a, b) => (b.marketValueKrw ?? 0) - (a.marketValueKrw ?? 0));
  return holdingsCache;
}

let monthlyHoldingsCache: MonthlyHoldingRow[] | undefined;
export function getMonthlyHoldings(): MonthlyHoldingRow[] {
  if (monthlyHoldingsCache) return monthlyHoldingsCache;
  const raw = readJson<RawReport[]>('data/web/monthly-holdings.json', []);
  monthlyHoldingsCache = raw.map((row) => ({
    persona: String(row.persona ?? ''),
    monthEnd: String(row.month_end ?? row.monthEnd ?? ''),
    symbol: String(row.symbol ?? ''),
    company: String(row.company ?? row.symbol ?? ''),
    qty: num(row.qty),
    marketValueKrw: num(row.market_value_krw ?? row.marketValueKrw),
    weightInPortfolio: num(row.weight_in_portfolio ?? row.weightInPortfolio),
  })).sort((a, b) => b.monthEnd.localeCompare(a.monthEnd) || (b.marketValueKrw ?? 0) - (a.marketValueKrw ?? 0));
  return monthlyHoldingsCache;
}

let tradesCache: TradeRow[] | undefined;
export function getTrades(): TradeRow[] {
  if (tradesCache) return tradesCache;
  tradesCache = parseCsv(readText('data/sim/trades.csv')).map((row) => ({
    persona: String(row.persona ?? ''),
    date: String(row.date ?? ''),
    symbol: String(row.symbol ?? ''),
    side: String(row.side ?? ''),
    qty: num(row.qty),
    fillPriceKrw: num(row.fill_price_krw),
    grossKrw: num(row.gross_krw),
    cashAfterKrw: num(row.cash_after_krw),
    reason: String(row.reason ?? ''),
    reportId: strOrNull(row.report_id),
  })).sort((a, b) => b.date.localeCompare(a.date));
  return tradesCache;
}

let positionEpisodesCache: PositionEpisodeRow[] | undefined;
export function getPositionEpisodes(): PositionEpisodeRow[] {
  if (positionEpisodesCache) return positionEpisodesCache;
  positionEpisodesCache = parseCsv(readText('data/sim/position_episodes.csv')).map((row) => ({
    persona: String(row.persona ?? ''),
    symbol: String(row.symbol ?? ''),
    company: String(row.company ?? row.symbol ?? ''),
    openDate: String(row.open_date ?? ''),
    closeDate: strOrNull(row.close_date),
    holdingDays: num(row.holding_days),
    buyFills: num(row.buy_fills),
    sellFills: num(row.sell_fills),
    totalQtyBought: num(row.total_qty_bought),
    totalQtySold: num(row.total_qty_sold),
    avgEntryPriceKrw: num(row.avg_entry_price_krw),
    avgExitPriceKrw: num(row.avg_exit_price_krw),
    realizedPnlKrw: num(row.realized_pnl_krw),
    unrealizedPnlKrw: num(row.unrealized_pnl_krw),
    lastCloseKrw: num(row.last_close_krw),
    status: String(row.status ?? ''),
    exitReasons: String(row.exit_reasons ?? ''),
  })).sort((a, b) => b.openDate.localeCompare(a.openDate));
  return positionEpisodesCache;
}

export function getPersonaLabel(persona: string): string {
  return getSummaryRows().find((row) => row.persona === persona)?.label ?? persona;
}

let equityDailyCache: EquityPoint[] | undefined;
export function getEquityDaily(): EquityPoint[] {
  if (equityDailyCache) return equityDailyCache;
  if (!fs.existsSync(fullPath('data/sim/equity_daily.csv'))) return [];
  equityDailyCache = parseCsv(readText('data/sim/equity_daily.csv')).map((row) => {
    const equity = num(row.equity_krw);
    const contributed = num(row.contributed_capital_krw);
    return {
      persona: String(row.persona ?? ''),
      date: String(row.date ?? ''),
      equityKrw: equity,
      contributedCapitalKrw: contributed,
      cumulativeReturn: equity !== null && contributed !== null && contributed > 0 ? equity / contributed - 1 : null,
    };
  });
  return equityDailyCache;
}

export function getStrategyExperiment(run: StrategyRunArtifact): StrategyExperiment {
  const params = run.params ?? {};
  const selected = selectReportsForRun(getReportRows(), params);
  const weights = weightsForRun(selected, params);
  const multiplier = readParam(params, 'target_hit_multiplier', 1);
  const takeProfit = readParam(params, 'take_profit_pct', Number.POSITIVE_INFINITY);
  const stopLoss = readParam(params, 'stop_loss_pct', 1);
  const positions = selected.map((report, index) => {
    const targetReturn = clamp((report.targetUpsideAtPub ?? 0) * multiplier, -stopLoss, takeProfit);
    const observedReturn = report.targetHit ? targetReturn : clamp(report.currentReturn ?? 0, -stopLoss, takeProfit);
    return {
      runId: run.run_id,
      symbol: report.symbol,
      company: report.company,
      publicationDate: report.publicationDate,
      exitDate: report.targetHitDate ?? report.lastCloseDate,
      status: report.targetHit ? 'closed' as const : 'open' as const,
      weight: weights[index] ?? 0,
      entryPriceKrw: report.entryPriceKrw,
      targetPriceKrw: report.targetPriceKrw,
      expectedReturn: targetReturn,
      realizedReturn: observedReturn,
      targetHit: report.targetHit,
    };
  });
  const trades = positions.flatMap((position) => {
    const out: StrategyExperimentTrade[] = [{
      runId: run.run_id,
      date: position.publicationDate,
      side: 'buy',
      symbol: position.symbol,
      company: position.company,
      weight: position.weight,
      referencePriceKrw: position.entryPriceKrw,
      reason: '조건 충족 리포트 발간 후 매수',
    }];
    if (position.status === 'closed' && position.exitDate) {
      out.push({
        runId: run.run_id,
        date: position.exitDate,
        side: 'sell',
        symbol: position.symbol,
        company: position.company,
        weight: position.weight,
        referencePriceKrw: position.targetPriceKrw,
        reason: '목표가 도달 청산',
      });
    }
    return out;
  }).sort((a, b) => b.date.localeCompare(a.date));
  return {
    runId: run.run_id,
    positions,
    trades,
    cumulativeReturnSeries: experimentCumulativeSeries(positions),
  };
}

function selectReportsForRun(reports: ReportRow[], params: Record<string, unknown>): ReportRow[] {
  const minUpside = readParam(params, 'min_target_upside_at_pub', 0.05);
  const maxUpside = readParam(params, 'max_target_upside_at_pub', 5);
  const maxReportAgeDays = readParam(params, 'max_report_age_days', 1500);
  const maxPositions = Math.max(1, Math.round(readParam(params, 'max_positions', 30)));
  const universe = String(params.universe ?? 'all');
  const requirePublicationPrice = Boolean(params.require_publication_price);
  return reports
    .filter((report) => {
      if (requirePublicationPrice && !report.entryPriceKrw) return false;
      if ((report.targetUpsideAtPub ?? Number.NaN) < minUpside || (report.targetUpsideAtPub ?? Number.NaN) > maxUpside) return false;
      if (report.daysToTarget !== null && report.daysToTarget > maxReportAgeDays) return false;
      if (universe !== 'all') {
        const domestic = report.symbol.endsWith('.KS') || report.symbol.endsWith('.KQ');
        if (universe === 'domestic' && !domestic) return false;
        if (universe === 'overseas' && domestic) return false;
      }
      return true;
    })
    .sort((a, b) => a.publicationDate.localeCompare(b.publicationDate) || a.reportId.localeCompare(b.reportId))
    .slice(0, maxPositions);
}

function weightsForRun(reports: ReportRow[], params: Record<string, unknown>): number[] {
  if (!reports.length) return [];
  const weighting = String(params.weighting ?? 'equal');
  const raw = reports.map((report) => {
    if (weighting === 'target_upside' || weighting === 'capped_target_upside') {
      const value = Math.max(0.01, report.targetUpsideAtPub ?? 0.01);
      return weighting === 'capped_target_upside' ? Math.min(1, value) : value;
    }
    if (weighting === 'inverse_volatility') {
      return 1 / Math.max(0.05, Math.abs(report.troughReturn ?? -0.2));
    }
    return 1;
  });
  const total = raw.reduce((sum, value) => sum + value, 0);
  return raw.map((value) => value / Math.max(total, Number.EPSILON));
}

function experimentCumulativeSeries(positions: StrategyExperimentPosition[]): PricePoint[] {
  if (!positions.length) return [];
  const start = positions.reduce((min, position) => position.publicationDate < min ? position.publicationDate : min, positions[0].publicationDate);
  let cumulative = 0;
  const points: PricePoint[] = [{ time: start, value: 0 }];
  for (const position of [...positions].sort((a, b) => (a.exitDate ?? a.publicationDate).localeCompare(b.exitDate ?? b.publicationDate))) {
    cumulative += position.weight * (position.realizedReturn ?? 0);
    points.push({ time: position.exitDate ?? position.publicationDate, value: cumulative });
  }
  return coalescePricePoints(points);
}

function coalescePricePoints(points: PricePoint[]): PricePoint[] {
  const byTime = new Map<string, number>();
  for (const point of points) byTime.set(point.time, point.value);
  return [...byTime.entries()].sort(([a], [b]) => a.localeCompare(b)).map(([time, value]) => ({ time, value }));
}

function readParam(params: Record<string, unknown>, key: string, fallback: number): number {
  const value = params[key];
  return typeof value === 'number' && Number.isFinite(value) ? value : fallback;
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}
