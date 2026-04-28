import Link from 'next/link';
import { MetricCard, Panel, StatusPill } from '@/components/ui/Terminal';
import { formatKrw, formatPercent } from '@/lib/format';

type StrategyRun = {
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
  max_positions: '최대 보유',
  stop_loss: '손절',
  take_profit: '익절',
  min_upside: '최소 업사이드',
  rebalance_days: '리밸런싱',
  holding_days: '보유 기간',
};

export function StrategySummary({ run, href }: { run: StrategyRun; href?: string }) {
  const params = run.params ?? {};
  const topParams = Object.keys(params).slice(0, 6);

  return (
    <Panel>
      <div className="action-row" style={{ justifyContent: 'space-between' }}>
        <div>
          <p className="eyebrow">{run.scope ?? 'local'} · {run.sampler ?? 'artifact'}{run.trial_number !== undefined ? ` · trial ${run.trial_number}` : ''}</p>
          <h2>{href ? <Link href={href}>{run.label}</Link> : run.label}</h2>
        </div>
        <StatusPill tone="accent">score {formatPercent(run.metrics.score)}</StatusPill>
      </div>
      <dl className="grid cards" style={{ marginTop: '1rem' }}>
        <MetricCard label="최종 자산" value={formatKrw(run.metrics.final_equity_krw)} tone="good" />
        <MetricCard label="IRR proxy" value={formatPercent(run.metrics.money_weighted_return)} />
        <MetricCard label="MDD" value={formatPercent(run.metrics.max_drawdown)} tone="bad" />
        <MetricCard label="목표 도달률" value={formatPercent(run.metrics.hit_rate)} tone="accent" />
      </dl>
      {topParams.length ? (
        <div className="tag-row" aria-label="핵심 파라미터">
          {topParams.map((key) => <span className="pill" key={key}>{PARAM_LABELS[key] ?? key}: {formatParam(params[key])}</span>)}
        </div>
      ) : null}
      {run.warnings?.length ? (
        <ul>
          {run.warnings.map((warning) => <li key={warning}>⚠ {warning}</li>)}
        </ul>
      ) : null}
    </Panel>
  );
}

function formatParam(value: unknown): string {
  if (typeof value === 'number') {
    if (Math.abs(value) < 1) return formatPercent(value);
    return value.toLocaleString('ko-KR', { maximumFractionDigits: 2 });
  }
  if (typeof value === 'boolean') return value ? '예' : '아니오';
  return String(value ?? '—');
}
