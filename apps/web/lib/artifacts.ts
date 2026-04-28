import 'server-only';
import fs from 'node:fs';
import path from 'node:path';

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
};

export type PricePoint = { time: string; value: number };
export type SummaryRow = { persona: string; finalEquityKrw: number | null; cumulativeDepositsKrw: number | null; netProfitKrw: number | null; irr: number | null; maxDrawdown: number | null; tradeCount: number | null };
export type DataQuality = { extractedReports: number; reportsWithPrices: number; totalReports: number; targetHitRate: number; missingPriceSymbols: number; extractionQuality: Record<string, unknown> };

type CsvRow = Record<string, string>;

const repoRoot = path.resolve(/* turbopackIgnore: true */ process.cwd(), '../..');

function readText(relativePath: string): string {
  return fs.readFileSync(path.join(repoRoot, relativePath), 'utf8');
}

function readJson(relativePath: string): unknown {
  return JSON.parse(readText(relativePath));
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
      if (inQuotes && next === '"') {
        field += '"';
        index += 1;
      } else {
        inQuotes = !inQuotes;
      }
      continue;
    }
    if (char === ',' && !inQuotes) {
      row.push(field);
      field = '';
      continue;
    }
    if ((char === '\n' || char === '\r') && !inQuotes) {
      if (char === '\r' && next === '\n') index += 1;
      row.push(field);
      if (row.some((cell) => cell.length > 0)) rows.push(row);
      row = [];
      field = '';
      continue;
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

function num(value: string | undefined): number | null {
  if (value === undefined || value === '') return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function bool(value: string | undefined): boolean {
  return value === 'True' || value === 'true' || value === '1';
}

let reportCache: ReportRow[] | undefined;
export function getReportRows(): ReportRow[] {
  if (reportCache) return reportCache;
  const reportMeta = new Map(parseCsv(readText('data/warehouse/reports.csv')).map((row) => [row.report_id, row]));
  reportCache = parseCsv(readText('data/sim/report_performance.csv')).map((row) => {
    const meta = reportMeta.get(row.report_id) ?? {};
    return {
      reportId: row.report_id,
      symbol: row.symbol,
      company: row.company,
      publicationDate: row.publication_date,
      title: meta.title || row.company,
      exchange: meta.exchange || '',
      markdownFilename: meta.markdown_filename || '',
      pdfFilename: meta.pdf_filename || '',
      pdfUrl: meta.pdf_url || '',
      entryPriceKrw: num(row.entry_price_krw),
      targetPriceKrw: num(row.target_price_krw),
      targetUpsideAtPub: num(row.target_upside_at_pub),
      targetHit: bool(row.target_hit),
      targetHitDate: row.target_hit_date || null,
      daysToTarget: num(row.days_to_target),
      lastCloseKrw: num(row.last_close_krw),
      lastCloseDate: row.last_close_date || null,
      currentReturn: num(row.current_return),
      peakReturn: num(row.peak_return),
      troughReturn: num(row.trough_return),
      targetGapPct: num(row.target_gap_pct),
    };
  }).sort((a, b) => b.publicationDate.localeCompare(a.publicationDate) || a.company.localeCompare(b.company));
  return reportCache;
}

export function getReportById(reportId: string): ReportRow | undefined {
  return getReportRows().find((report) => report.reportId === reportId);
}

export function getPriceSeries(symbol: string, startDate: string, endDate?: string | null): PricePoint[] {
  const stop = endDate ?? '9999-99-99';
  return parseCsv(readText('data/warehouse/daily_prices.csv'))
    .filter((row) => row.symbol === symbol && row.date >= startDate && row.date <= stop)
    .map((row) => ({ time: row.date, value: num(row.close) ?? 0 }))
    .filter((point) => point.value > 0);
}

export function getMarkdownSnippet(report: ReportRow): string {
  if (!report.markdownFilename) return 'No markdown extraction file recorded for this report.';
  const fullPath = path.join(repoRoot, 'data/markdown', report.markdownFilename);
  if (!fs.existsSync(fullPath)) return `Missing markdown extraction: ${report.markdownFilename}`;
  return fs.readFileSync(fullPath, 'utf8').slice(0, 5000);
}

export function getSummaryRows(): SummaryRow[] {
  if (!fs.existsSync(path.join(repoRoot, 'data/sim/summary.csv'))) return [];
  return parseCsv(readText('data/sim/summary.csv')).map((row) => ({
    persona: row.persona,
    finalEquityKrw: num(row.final_equity_krw),
    cumulativeDepositsKrw: num(row.cumulative_deposits_krw),
    netProfitKrw: num(row.net_profit_krw),
    irr: num(row.irr),
    maxDrawdown: num(row.max_drawdown),
    tradeCount: num(row.trade_count),
  })).sort((a, b) => (b.finalEquityKrw ?? 0) - (a.finalEquityKrw ?? 0));
}

export function getDataQuality(): DataQuality {
  const reports = getReportRows();
  const extractedRows = parseCsv(readText('data/extracted_reports.csv'));
  const reportStats = readJson('data/sim/report_stats.json') as Record<string, unknown>;
  const extractionQuality = readJson('data/extraction_quality.json') as Record<string, unknown>;
  const targetHitCount = reports.filter((report) => report.targetHit).length;
  return {
    extractedReports: extractedRows.length,
    reportsWithPrices: reports.length,
    totalReports: Number(reportStats.total_reports ?? reports.length),
    targetHitRate: targetHitCount / Math.max(1, reports.length),
    missingPriceSymbols: Number(reportStats.missing_price_symbols ?? 0),
    extractionQuality,
  };
}

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

function readJsonIfExists<T>(relativePath: string, fallback: T): T {
  const fullPath = path.join(repoRoot, relativePath);
  if (!fs.existsSync(fullPath)) return fallback;
  return JSON.parse(fs.readFileSync(fullPath, 'utf8')) as T;
}

export function getOverview(): WebOverview {
  return readJsonIfExists<WebOverview>('data/web/overview.json', {
    baseline_personas: [],
    report_counts: {
      extracted_reports: getDataQuality().extractedReports,
      price_matched_reports: getDataQuality().reportsWithPrices,
      report_stat_rows: getDataQuality().totalReports,
      missing_price_symbols: getDataQuality().missingPriceSymbols,
    },
    target_stats: {
      target_hit_rate: getDataQuality().targetHitRate,
      target_hit_count: getReportRows().filter((report) => report.targetHit).length,
    },
  });
}

export function getReportRankings(): WebReportRankings {
  return readJsonIfExists<WebReportRankings>('data/web/report-rankings.json', {
    top_winners: [...getReportRows()].sort((a, b) => (b.currentReturn ?? -Infinity) - (a.currentReturn ?? -Infinity)).slice(0, 10).map(toRankingRow),
    top_losers: [...getReportRows()].sort((a, b) => (a.currentReturn ?? Infinity) - (b.currentReturn ?? Infinity)).slice(0, 10).map(toRankingRow),
    most_aggressive_targets: [...getReportRows()].sort((a, b) => (b.targetUpsideAtPub ?? -Infinity) - (a.targetUpsideAtPub ?? -Infinity)).slice(0, 10).map(toRankingRow),
  });
}

export function getStrategyRuns(): StrategyRunsArtifact {
  return readJsonIfExists<StrategyRunsArtifact>('data/web/strategy-runs.json',
    readJsonIfExists<StrategyRunsArtifact>('apps/web/public/artifacts/strategy-runs.json', { runs: [], study_name: 'No local export yet' }),
  );
}

export function getParameterImportance(): ParameterImportanceArtifact {
  return readJsonIfExists<ParameterImportanceArtifact>('data/web/parameter-importance.json',
    readJsonIfExists<ParameterImportanceArtifact>('apps/web/public/artifacts/parameter-importance.json', { parameters: [] }),
  );
}

export function getWebDataQuality(): WebDataQuality {
  return readJsonIfExists<WebDataQuality>('data/web/data-quality.json', {});
}

function toRankingRow(report: ReportRow): WebReportRankingRow {
  return {
    report_id: report.reportId,
    symbol: report.symbol,
    company: report.company,
    publication_date: report.publicationDate,
    entry_price_krw: report.entryPriceKrw,
    target_price_krw: report.targetPriceKrw,
    target_upside_at_pub: report.targetUpsideAtPub,
    target_hit: report.targetHit,
    target_hit_date: report.targetHitDate,
    days_to_target: report.daysToTarget,
    last_close_krw: report.lastCloseKrw,
    last_close_date: report.lastCloseDate,
    current_return: report.currentReturn,
    peak_return: report.peakReturn,
    trough_return: report.troughReturn,
    target_gap_pct: report.targetGapPct,
  };
}
