import { StrategySummary, type StrategyRun } from "../../components/strategies/StrategySummary";

export default function StrategiesPage() {
  const data = getStrategyRuns();
  const importance = getParameterImportance();
  const runs = data.runs ?? [];
  const best = runs.find((run) => run.run_id === data.best_run_id) ?? runs[0];

  return (
    <main className="mx-auto max-w-6xl space-y-6 p-6">
      <header>
        <p className="text-sm font-medium text-amber-700">Local-only Optuna research</p>
        <h1 className="text-3xl font-bold text-slate-950">Strategy leaderboard</h1>
        <p className="mt-2 max-w-3xl text-slate-600">{data.disclaimer}</p>
      </header>
      <section className="grid gap-4">
        {data.runs.length ? data.runs.map((run: StrategyRun) => <StrategySummary key={run.run_id} run={run} />) : (
          <div className="rounded-2xl border border-dashed border-slate-300 p-6 text-slate-600">
            No strategy artifacts found. Run the local search/export scripts, then copy data/web JSON into public artifacts.
          </div>
          <div className="bar-list">
            {importance.parameters.slice(0, 6).map((item) => (
              <div className="bar-row" key={item.parameter}>
                <span>{item.parameter}</span>
                <div className="bar-track"><div className="bar-fill" style={{ width: `${Math.min(100, item.importance * 100)}%` }} /></div>
                <strong>{formatPercent(item.importance, 1)}</strong>
              </div>
            ))}
          </div>
        </section>
      ) : null}

      <section className="grid" aria-label="전략 순위">
        {runs.length ? runs.map((run, index) => <StrategySummary key={run.run_id} run={run} rank={index + 1} />) : (
          <div className="panel">전략 artifact가 없습니다. 로컬 탐색과 export 스크립트를 먼저 실행하세요.</div>
        )}
      </section>
    </>
  );
}
