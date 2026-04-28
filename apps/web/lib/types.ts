export type PersonaSummary = {
  persona: string;
  label: string;
  final_equity_krw: number | null;
  net_profit_krw: number | null;
  money_weighted_return: number | null;
  max_drawdown: number | null;
  trade_count: number | null;
};

export type ReportRow = {
  report_id: string;
  date: string;
  company: string;
  ticker: string;
  exchange: string;
  symbol: string;
  title: string;
  rating: string | null;
  pdf_url: string;
  markdown_filename: string;
  target_price: number | null;
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
  generated_from?: string;
  report_counts: {
    extracted_reports?: number;
    report_stat_rows?: number;
    price_matched_reports?: number;
    missing_price_symbols?: number;
    web_report_rows?: number;
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

export type ChartMarker = {
  type: 'publication' | 'target_hit' | 'peak' | 'trough' | 'latest' | string;
  date: string;
  label: string;
  price_krw: number | null;
};

export type ReportDetailMetric = {
  report_id?: string;
  company?: string;
  symbol?: string;
  target_hit?: boolean | null;
  days_to_target?: number | null;
  current_return?: number | null;
  peak_return?: number | null;
  trough_return?: number | null;
  target_gap_pct?: number | null;
  entry_price_krw?: number | null;
  target_price_krw?: number | null;
  latest_close_krw?: number | null;
  price_extremes?: Record<string, ChartMarker>;
  markers?: ChartMarker[];
  interpretation?: string[];
};

export type Insight = {
  id: string;
  title: string;
  sentence: string;
  metric?: number | string | null;
  related_report_ids?: string[];
};

export type DataQuality = {
  coverage: Record<string, number | string | null>;
  extraction_quality: Record<string, unknown>;
  missing_symbols: Array<{ symbol: string }>;
};

export type Rankings = Record<string, ReportRow[]>;

export type StrategyRun = {
  run_id: string;
  trial_number?: number;
  label: string;
  family?: string;
  scope?: string;
  sampler?: string;
  score?: number;
  metrics: Record<string, number | null>;
  parameters?: Record<string, string | number | boolean | null>;
  params?: Record<string, string | number | boolean | null>;
  warnings?: string[];
};

export type StrategyRunsArtifact = {
  study_name?: string;
  scope?: string;
  best_run_id?: string;
  disclaimer?: string;
  runs: StrategyRun[];
};

export type ParameterImportance = {
  method?: string;
  parameters?: Array<{ parameter: string; importance: number }>;
};
