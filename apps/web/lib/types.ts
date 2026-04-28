export type PersonaSummary = {
  persona: string;
  label: string;
  initial_capital_krw: number;
  total_contributed_krw: number;
  final_equity_krw: number;
  final_cash_krw: number;
  final_holdings_value_krw: number;
  net_profit_krw: number;
  money_weighted_return: number;
  time_weighted_return: number;
  cagr: number;
  max_drawdown: number;
  realized_pnl_krw: number;
  trade_count: number;
  open_positions: number;
};

export type ReportRow = {
  report_id: string;
  date: string;
  company: string;
  ticker: string;
  exchange: string;
  symbol: string;
  title: string;
  pdf_url: string;
  markdown_filename: string;
  target_price_krw: number | null;
  publication_price_krw: number | null;
  entry_price_krw: number | null;
  target_upside_at_pub: number | null;
  target_hit: boolean | null;
  target_hit_date: string | null;
  days_to_target: number | null;
  last_close_krw: number | null;
  last_close_date: string | null;
  current_return: number | null;
  peak_return: number | null;
  trough_return: number | null;
  target_gap_pct: number | null;
  caveat_flags: string[];
};

export type Overview = {
  report_counts: {
    extracted_reports: number;
    report_stat_rows: number;
    price_matched_reports: number;
    missing_price_symbols: number;
    web_report_rows: number;
  };
  target_stats: Record<string, number | null>;
  baseline_personas: PersonaSummary[];
  simulation_window: Record<string, string | null>;
};

export type PricePoint = {
  date: string;
  open: number | null;
  high: number | null;
  low: number | null;
  close: number | null;
  close_krw: number | null;
  volume: number | null;
};

export type StrategyRun = {
  run_id: string;
  label: string;
  family?: string;
  scope?: string;
  sampler?: string;
  in_sample?: boolean;
  score?: number;
  metrics: Record<string, number>;
  parameters?: Record<string, string | number | boolean>;
  params?: Record<string, string | number | boolean>;
  baseline_excess?: Record<string, number>;
};

export type TrialRow = StrategyRun & { trial_number: number };
