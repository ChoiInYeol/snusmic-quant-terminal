import 'server-only';
import fs from 'node:fs';
import path from 'node:path';
import type { Overview, PersonaSummary, PricePoint, ReportRow, StrategyRun, TrialRow } from './types';

const repoRoot = path.resolve(process.cwd(), '../..');
const artifactRoot = path.join(repoRoot, 'data/web');

function readJson<T>(relativePath: string, fallback: T): T {
  const fullPath = path.join(artifactRoot, relativePath);
  if (!fs.existsSync(fullPath)) return fallback;
  return JSON.parse(fs.readFileSync(fullPath, 'utf8')) as T;
}

export function getOverview(): Overview | null {
  return readJson<Overview | null>('overview.json', null);
}

export function getPersonas(): PersonaSummary[] {
  const overview = getOverview();
  return overview?.baseline_personas ?? readJson<PersonaSummary[]>('personas.json', []);
}

export function getReports(): ReportRow[] {
  return readJson<ReportRow[]>('reports.json', []);
}

export function getReport(reportId: string): ReportRow | undefined {
  return getReports().find((report) => report.report_id === reportId);
}

export function getPriceSeries(symbol: string): PricePoint[] {
  const payload = readJson<{ symbol: string; prices: PricePoint[] } | null>(`prices/${symbol}.json`, null);
  return payload?.prices ?? [];
}

export function getMissingSymbols(): { symbol: string }[] {
  return readJson<{ symbol: string }[]>('missing-symbols.json', []);
}

export function getDataQuality(): Record<string, unknown> {
  return readJson<Record<string, unknown>>('data-quality.json', {});
}

export function getStrategyRuns(): StrategyRun[] {
  const raw = readJson<StrategyRun[] | { runs?: StrategyRun[] }>('strategy-runs.json', []);
  return Array.isArray(raw) ? raw : raw.runs ?? [];
}

export function getStrategyRun(runId: string): StrategyRun | undefined {
  return getStrategyRuns().find((run) => run.run_id === runId);
}

export function getOptunaTrials(): TrialRow[] {
  const raw = readJson<TrialRow[] | { trials?: TrialRow[] }>('optuna-trials.json', []);
  return Array.isArray(raw) ? raw : raw.trials ?? [];
}

export function getParameterImportance(): { parameter: string; importance: number }[] {
  const raw = readJson<{ parameter: string; importance: number }[] | { parameters?: { parameter: string; importance: number }[] }>('parameter-importance.json', []);
  return Array.isArray(raw) ? raw : raw.parameters ?? [];
}

export function getMarkdownSnippet(report: ReportRow): string {
  if (!report.markdown_filename) return 'No markdown extraction file recorded for this report.';
  const fullPath = path.join(repoRoot, 'data/markdown', report.markdown_filename);
  if (!fs.existsSync(fullPath)) return `Missing markdown extraction: ${report.markdown_filename}`;
  return fs.readFileSync(fullPath, 'utf8').slice(0, 3500);
}
