type StrategyRun = {
  run_id: string;
  label: string;
  scope: string;
  sampler: string;
  params: Record<string, unknown>;
  metrics: Record<string, number | null>;
  warnings?: string[];
};

const formatPct = (value: number | null | undefined) =>
  typeof value === "number" ? `${(value * 100).toFixed(1)}%` : "n/a";

const formatKrw = (value: number | null | undefined) =>
  typeof value === "number" ? `${(value / 1_000_000).toFixed(1)}M KRW` : "n/a";

export function StrategySummary({ run }: { run: StrategyRun }) {
  return (
    <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-wide text-amber-700">{run.scope} · {run.sampler}</p>
          <h2 className="mt-1 text-xl font-semibold text-slate-950">{run.label}</h2>
        </div>
        <span className="rounded-full bg-slate-950 px-3 py-1 text-sm text-white">
          score {formatPct(run.metrics.score)}
        </span>
      </div>
      <dl className="mt-4 grid grid-cols-2 gap-3 text-sm md:grid-cols-4">
        <Metric label="Final equity" value={formatKrw(run.metrics.final_equity_krw)} />
        <Metric label="IRR proxy" value={formatPct(run.metrics.money_weighted_return)} />
        <Metric label="MDD" value={formatPct(run.metrics.max_drawdown)} />
        <Metric label="Hit rate" value={formatPct(run.metrics.hit_rate)} />
      </dl>
      {run.warnings?.length ? (
        <ul className="mt-4 space-y-1 text-sm text-amber-800">
          {run.warnings.map((warning) => <li key={warning}>⚠ {warning}</li>)}
        </ul>
      ) : null}
    </article>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return <div><dt className="text-slate-500">{label}</dt><dd className="font-medium text-slate-950">{value}</dd></div>;
}
