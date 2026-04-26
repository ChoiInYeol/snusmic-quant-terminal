// Generated table-row types (from docs/schemas/*.schema.json via
// apps/web/scripts/gen-types.mjs — DO NOT hand-edit the underlying definitions).
// We re-export them here so existing `import { StrategyRun } from '../lib/data'`
// call sites keep working without a rename pass.
export type {
  DailyPrice,
  ExecutionEvent,
  PriceMetric,
  ReportRow,
  StrategyRun,
  Trade,
} from './generated/types';

import type { StrategyRun, ReportRow, Trade, PriceMetric } from './generated/types';

export type Position = {
  run_id: string;
  date: string;
  symbol: string;
  company: string;
  weight: number;
  close: number | null;
  target_price: number | null;
  gross_return: number | null;
  model_contribution: number | null;
  mtt_pass: boolean;
};

export type EquityRow = {
  run_id: string;
  date: string;
  portfolio_return: number;
  cumulative_return: number;
  equity: number;
  candidate_count: number;
  execution_count: number;
  cash_weight: number;
};

export type CandidateEvent = {
  run_id: string;
  date: string;
  symbol: string;
  company: string;
  event_type: string;
  reason: string;
  close: number | null;
  target_price: number | null;
  candidate_count_after: number | null;
};

export type SignalRow = {
  run_id: string;
  strategy_name: string;
  date: string;
  symbol: string;
  close: number | null;
  ma50: number | null;
  ma150: number | null;
  ma200: number | null;
  candidate_universe_active: boolean;
  mtt_pass: boolean;
  pct_above_52w_low: number | null;
  pct_below_52w_high: number | null;
};

export type ChartIndexRow = {
  symbol: string;
  company: string;
  file: string;
  last_date: string;
  last_close: number | null;
  report_count: number;
  trade_count: number;
};

export type StockChartData = {
  meta: {
    symbol: string;
    company: string;
    last_date: string;
    last_close: number | null;
    display_currency: string;
  };
  ohlc: Array<{ time: string; open: number; high: number; low: number; close: number }>;
  ma50: Array<{ time: string; value: number }>;
  ma150: Array<{ time: string; value: number }>;
  ma200: Array<{ time: string; value: number }>;
  report_markers: Array<Record<string, unknown>>;
  trade_markers: Array<Record<string, unknown> & { run_id?: string }>;
  price_lines: Array<{ title: string; price: number; color: string }>;
};

export type DashboardData = {
  strategies: StrategyRun[];
  positions: Position[];
  equity: EquityRow[];
  trades: Trade[];
  candidateEvents: CandidateEvent[];
  signals: SignalRow[];
  reports: ReportRow[];
  priceMetrics: PriceMetric[];
  chartIndex: ChartIndexRow[];
};

const basePath = process.env.NEXT_PUBLIC_BASE_PATH ?? '';

export function dataUrl(path: string): string {
  return `${basePath}/data/${path}`;
}

export async function fetchJson<T>(path: string): Promise<T> {
  // Phase 4 — switch from ``cache: 'no-store'`` to ``'force-cache'``. Once
  // the data pipeline lives in GitHub Actions (Phase 4 plan AC #5) the
  // dashboard JSONs change at most once per scheduled run; ``no-store``
  // forced a network round-trip on every navigation. ``force-cache`` lets
  // the browser / CDN serve the bundled artifact and the StaleDataBanner is
  // the source of truth for "is this data current?" rather than a
  // network-cache-busting heuristic.
  const response = await fetch(dataUrl(path), { cache: 'force-cache' });
  if (!response.ok) {
    throw new Error(`Failed to load ${path}: ${response.status}`);
  }
  return (await response.json()) as T;
}

export async function loadDashboard(): Promise<DashboardData> {
  const [strategies, positions, equity, trades, candidateEvents, signals, reports, priceMetrics, chartIndex] = await Promise.all([
    fetchJson<StrategyRun[]>('quant_v3/strategy_runs.json'),
    fetchJson<Position[]>('quant_v3/current_positions.json'),
    fetchJson<EquityRow[]>('quant_v3/equity_daily.json'),
    fetchJson<Trade[]>('quant_v3/recent_trades.json'),
    fetchJson<CandidateEvent[]>('quant_v3/candidate_pool_events.json'),
    fetchJson<SignalRow[]>('quant_v3/signals_daily.json'),
    fetchJson<ReportRow[]>('quant_v3/reports.json'),
    fetchJson<PriceMetric[]>('price_metrics.json'),
    fetchJson<ChartIndexRow[]>('quant_v3/chart_series/index.json'),
  ]);
  return { strategies, positions, equity, trades, candidateEvents, signals, reports, priceMetrics, chartIndex };
}

export function bestStrategy(strategies: StrategyRun[]): StrategyRun | null {
  return [...strategies].sort((a, b) => (b.objective ?? b.total_return) - (a.objective ?? a.total_return))[0] ?? null;
}
