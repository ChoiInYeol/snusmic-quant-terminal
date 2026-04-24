export type StrategyRun = {
  run_id: string;
  strategy_name: string;
  weighting: string;
  entry_rule: string;
  rebalance: string;
  lookback_days: number;
  final_wealth: number;
  total_return: number;
  cagr: number | null;
  sharpe: number | null;
  sortino: number | null;
  calmar: number | null;
  max_drawdown: number;
  annualized_volatility: number | null;
  realized_return: number;
  live_return: number;
  exposure_ratio: number;
  average_positions: number;
  turnover_events: number;
  trade_count: number;
  win_rate: number | null;
  objective: number;
  status: string;
};

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
  rs_score: number | null;
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

export type Trade = {
  run_id: string;
  date: string;
  symbol: string;
  company: string;
  event_type: string;
  reason: string;
  price: number;
  weight: number;
  gross_return: number | null;
  realized_return: number | null;
  holding_days: number | null;
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
  rs_score: number | null;
  candidate_universe_active: boolean;
  mtt_pass: boolean;
  pct_above_52w_low: number | null;
  pct_below_52w_high: number | null;
};

export type ReportRow = {
  report_id: string;
  page: number | null;
  ordinal: number | null;
  publication_date: string;
  title: string;
  company: string;
  ticker: string;
  exchange: string;
  symbol: string;
  pdf_filename: string;
  pdf_url: string;
  markdown_filename: string;
  report_current_price_krw: number | null;
  bear_target_krw: number | null;
  base_target_krw: number | null;
  bull_target_krw: number | null;
  target_price_krw: number | null;
  target_currency: string;
  price_currency: string;
  display_currency: string;
};

export type PriceMetric = {
  title: string;
  company: string;
  display_name: string;
  yfinance_symbol: string;
  display_currency: string;
  publication_date: string;
  publication_buy_price: number | null;
  current_price: number | null;
  lowest_price_since_publication: number | null;
  lowest_price_current_return: number | null;
  q25_price_since_publication: number | null;
  q25_price_current_return: number | null;
  q75_price_since_publication: number | null;
  q75_price_current_return: number | null;
  q75_price_realized_return: number | null;
  highest_price_since_publication: number | null;
  highest_price_realized_return: number | null;
  publication_buy_return: number | null;
  buy_at_publication_return: number | null;
  current_price_percentile: number | null;
  target_upside_remaining: number | null;
  target_hit: boolean;
  first_target_hit_date: string;
  status: string;
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
  const response = await fetch(dataUrl(path), { cache: 'no-store' });
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
