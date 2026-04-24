export function pct(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '-';
  return `${(value * 100).toFixed(digits)}%`;
}

export function num(value: number | null | undefined, currency = '', digits?: number): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '-';
  const decimals = digits ?? (currency === 'USD' ? 2 : 0);
  return new Intl.NumberFormat('ko-KR', {
    maximumFractionDigits: decimals,
    minimumFractionDigits: decimals,
  }).format(value);
}

export function shortDate(value: string | null | undefined): string {
  if (!value) return '-';
  return value.slice(2, 10);
}

export function labelEntryRule(value: string): string {
  const labels: Record<string, string> = {
    mtt_or_rs: 'MTT 또는 RS',
    mtt_and_rs: 'MTT 그리고 RS',
    target_only: '목표가 여력',
    hybrid_score: '혼합 점수',
  };
  return labels[value] ?? value;
}

export function labelReason(value: string): string {
  const labels: Record<string, string> = {
    buy: '매수',
    sell: '매도',
    candidate_add: '후보 편입',
    candidate_exit: '후보 제외',
    report_publication: '리포트 발간',
    aging_out: '추적 만료',
    rebalance_entry: '리밸런싱 편입',
    weight_update: '비중 조정',
    signal_loss: '신호 이탈',
    stop_loss: '손절',
    take_profit: '익절',
    take_profit_rr: 'R:R 익절',
    target_hit: '목표가 도달',
    candidate_expired: '추적 만료',
    candidate_aging_out: '추적 만료',
  };
  return labels[value] ?? value;
}
