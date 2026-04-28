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

const repoRoot = path.resolve(process.cwd(), '../..');

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
