import Link from 'next/link';
import { getPersonas, getStrategyRuns } from '@/lib/artifacts';
import { formatKrwCompact, formatNumber, formatPercent } from '@/lib/format';

export default function StrategiesPage() {
  const runs = getStrategyRuns();
  const personas = getPersonas();
  return (
    <>
      <section className="hero"><div className="eyebrow">Local Optuna results</div><h1>Strategy leaderboard.</h1><p>로컬에서 생성된 Optuna/랜덤서치 결과만 표시합니다. 결과가 없으면 baseline 비교부터 보여줍니다.</p></section>
      {runs.length ? <div className="table-wrap"><table><thead><tr><th>Run</th><th>Family</th><th>Score</th><th>Final equity</th><th>MDD</th><th>Excess vs SMIC v2</th></tr></thead><tbody>{runs.map((run) => <tr key={run.run_id}><td><Link href={`/strategies/${run.run_id}`}>{run.label}</Link><div className="muted">{(run.in_sample ?? run.scope === 'in-sample') ? 'in-sample' : 'walk-forward/test'}</div></td><td>{(run.family ?? 'smic_follower_parametric')}</td><td>{formatNumber(run.score ?? run.metrics.score, 3)}</td><td>{formatKrwCompact(run.metrics.final_equity_krw)}</td><td className="bad">{formatPercent(run.metrics.max_drawdown)}</td><td>{formatKrwCompact((run.baseline_excess?.smic_follower_v2 ?? run.metrics.excess_return_vs_smic_follower_v2))}</td></tr>)}</tbody></table></div> : <section className="empty"><h2>No local strategy export yet</h2><p>Run <code>uv run python scripts/run_optuna_search.py --trials 20</code> then <code>uv run python scripts/export_optuna_artifacts.py</code>.</p></section>}
      <section className="panel spaced"><h2>Baseline reference</h2><div className="table-wrap"><table><thead><tr><th>Persona</th><th>Final equity</th><th>MWR</th><th>MDD</th></tr></thead><tbody>{personas.map((p) => <tr key={p.persona}><td>{p.label}</td><td>{formatKrwCompact(p.final_equity_krw)}</td><td>{formatPercent(p.money_weighted_return)}</td><td className="bad">{formatPercent(p.max_drawdown)}</td></tr>)}</tbody></table></div></section>
    </>
  );
}
