import { StrategySummary } from "../../components/strategies/StrategySummary";

async function loadStrategyRuns() {
  try {
    return (await import("../../public/artifacts/strategy-runs.json")).default;
  } catch {
    return { study_name: "No local export yet", runs: [], disclaimer: "Run scripts/export_optuna_artifacts.py to generate strategy artifacts." };
  }
}

export default async function StrategiesPage() {
  const data = await loadStrategyRuns();
  return (
    <main className="mx-auto max-w-6xl space-y-6 p-6">
      <header>
        <p className="text-sm font-medium text-amber-700">Local-only Optuna research</p>
        <h1 className="text-3xl font-bold text-slate-950">Strategy leaderboard</h1>
        <p className="mt-2 max-w-3xl text-slate-600">{data.disclaimer}</p>
      </header>
      <section className="grid gap-4">
        {data.runs.length ? data.runs.map((run: any) => <StrategySummary key={run.run_id} run={run} />) : (
          <div className="rounded-2xl border border-dashed border-slate-300 p-6 text-slate-600">
            No strategy artifacts found. Run the local search/export scripts, then copy data/web JSON into public artifacts.
          </div>
        )}
      </section>
    </main>
  );
}
