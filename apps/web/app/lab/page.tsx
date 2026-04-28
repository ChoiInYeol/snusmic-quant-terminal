import { getOptunaTrials, getParameterImportance } from '@/lib/artifacts';
import { formatNumber } from '@/lib/format';

export default function LabPage() {
  const trials = getOptunaTrials();
  const importance = getParameterImportance();
  return <><section className="hero"><div className="eyebrow">Research lab</div><h1>Optuna trial diagnostics.</h1><p>Trial scatter/importance placeholders backed by local-only exported artifacts.</p></section><section className="grid cards"><div className="card"><div className="muted">Trials exported</div><div className="metric">{formatNumber(trials.length)}</div></div><div className="card"><div className="muted">Parameters ranked</div><div className="metric">{formatNumber(importance.length)}</div></div></section><section className="panel spaced"><h2>Parameter importance</h2>{importance.length ? <ul>{importance.map((row) => <li key={row.parameter}>{row.parameter}: {formatNumber(row.importance, 3)}</li>)}</ul> : <p>No parameter-importance export yet.</p>}</section></>;
}
