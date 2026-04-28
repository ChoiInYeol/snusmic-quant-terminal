export type StrategyRun = {
  run_id: string;
  trial_number?: number;
  label: string;
  scope?: string;
  sampler?: string;
  params?: Record<string, unknown>;
  metrics: Record<string, number | null | undefined>;
  warnings?: string[];
};

const PARAM_LABELS: Record<string, string> = {
  target_hit_multiplier: '목표가 달성 배수',
  min_target_upside_at_pub: '최소 제시 업사이드',
  max_target_upside_at_pub: '최대 제시 업사이드',
  max_report_age_days: '리포트 유효기간',
  time_loss_days: '시간 손절',
  stop_loss_pct: '손절선',
  take_profit_pct: '익절선',
  rebalance: '리밸런싱',
  max_positions: '최대 보유 종목',
  weighting: '가중 방식',
  universe: '투자 유니버스',
  exclude_missing_confidence_rows: '신뢰도 누락 제외',
  require_publication_price: '발간가 필수',
};

export function StrategySummary({ run, rank }: { run: StrategyRun; rank?: number }) {
  const score = run.metrics.score;
  const params = run.params ?? {};
  const topParams = ['max_positions', 'stop_loss_pct', 'take_profit_pct', 'time_loss_days', 'weighting']
    .filter((key) => key in params);

  return (
    <article className="panel strategy-card">
      <div className="split-header">
        <div>
          <div className="eyebrow">{rank ? `전략 #${rank}` : 'Strategy'} · {run.scope ?? 'in-sample'} · {run.sampler ?? 'local'}</div>
          <h2>{run.label}</h2>
          <p>웹 앱은 Optuna를 실행하지 않고, 로컬에서 내보낸 정적 결과만 표시합니다.</p>
        </div>
        <div className="score-badge">score {formatPercent(score, 1)}</div>
      </div>
      <dl className="metric-grid compact">
        <Metric label="최종 평가액" value={formatKrwMillions(run.metrics.final_equity_krw)} />
        <Metric label="순이익" value={formatKrwMillions(run.metrics.net_profit_krw)} />
        <Metric label="자금가중 수익률" value={formatPercent(run.metrics.money_weighted_return)} />
        <Metric label="최대 낙폭" value={formatPercent(run.metrics.max_drawdown)} tone="bad" />
        <Metric label="목표 달성률" value={formatPercent(run.metrics.hit_rate)} tone="good" />
        <Metric label="거래 수" value={formatCount(run.metrics.trade_count)} />
        <Metric label="평균 보유일" value={formatDays(run.metrics.average_holding_days)} />
        <Metric label="오픈 포지션" value={formatCount(run.metrics.open_positions)} />
      </dl>
      {topParams.length ? (
        <div className="tag-row" aria-label="핵심 파라미터">
          {topParams.map((key) => <span className="pill" key={key}>{PARAM_LABELS[key] ?? key}: {formatParam(params[key])}</span>)}
        </div>
      ) : null}
      {run.warnings?.length ? (
        <ul className="warning-list">
          {run.warnings.map((warning) => <li key={warning}>⚠ {translateWarning(warning)}</li>)}
        </ul>
      ) : null}
      <p><Link href={`/strategies/${run.run_id}`}>상세 파라미터 보기 →</Link></p>
    </article>
  );
}

function Metric({ label, value, tone }: { label: string; value: string; tone?: 'good' | 'bad' }) {
  return <div><dt className="muted">{label}</dt><dd className={tone ?? ''}>{value}</dd></div>;
}

function formatCount(value: number | null | undefined): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) return '—';
  return Math.round(value).toLocaleString('ko-KR');
}

function formatParam(value: unknown): string {
  if (typeof value === 'number') {
    if (Math.abs(value) < 10 && !Number.isInteger(value)) return value.toLocaleString('ko-KR', { maximumFractionDigits: 2 });
    return value.toLocaleString('ko-KR', { maximumFractionDigits: 0 });
  }
  if (typeof value === 'boolean') return value ? '예' : '아니오';
  return String(value);
}

function translateWarning(value: string): string {
  if (value.includes('in-sample')) return '인샘플 탐색 결과입니다. 실전 판단 전 별도 검증이 필요합니다.';
  return value;
}
