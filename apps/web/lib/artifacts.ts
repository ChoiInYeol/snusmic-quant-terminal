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

export type PricePoint = { time: string; value: number };
export type SummaryRow = {
  persona: string;
  label?: string;
  finalEquityKrw: number | null;
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
