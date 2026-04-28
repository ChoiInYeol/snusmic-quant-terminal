import Link from 'next/link';
import { MetricCard, Panel, StatusPill } from '@/components/ui/Terminal';

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

const formatPct = (value: number | null | undefined) =>
  typeof value === 'number' ? `${(value * 100).toFixed(1)}%` : 'n/a';

const formatKrw = (value: number | null | undefined) =>
  typeof value === 'number' ? `${(value / 1_000_000).toLocaleString('ko-KR', { maximumFractionDigits: 1 })}M KRW` : 'n/a';

export function StrategySummary({ run, href }: { run: StrategyRun; href?: string }) {
  return (
    <Panel>
      <div className="action-row" style={{ justifyContent: 'space-between' }}>
        <div>
          <p className="eyebrow">{run.scope ?? 'local'} · {run.sampler ?? 'artifact'}</p>
          <h2>{href ? <Link href={href}>{run.label}</Link> : run.label}</h2>
        </div>
        <StatusPill tone="accent">score {formatPct(run.metrics.score)}</StatusPill>
      </div>
      <dl className="grid cards" style={{ marginTop: '1rem' }}>
        <MetricCard label="최종 자산" value={formatKrw(run.metrics.final_equity_krw)} tone="good" />
        <MetricCard label="IRR proxy" value={formatPct(run.metrics.money_weighted_return)} />
        <MetricCard label="MDD" value={formatPct(run.metrics.max_drawdown)} tone="bad" />
        <MetricCard label="목표 도달률" value={formatPct(run.metrics.hit_rate)} tone="accent" />
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
