import { StrategySummary } from "../../../components/strategies/StrategySummary";

async function loadStrategyRuns() {
  try {
    return (await import("../../../public/artifacts/strategy-runs.json")).default;
  } catch {
    return { runs: [] };
  }
}

export async function generateStaticParams() {
  const data = await loadStrategyRuns();
  return data.runs.map((run: { run_id: string }) => ({ runId: run.run_id }));
}

export default async function StrategyDetailPage({ params }: { params: Promise<{ runId: string }> }) {
  const { runId } = await params;
  const data = await loadStrategyRuns();
  const run = data.runs.find((item: any) => item.run_id === runId);
  if (!run) {
    return <main className="mx-auto max-w-4xl p-6"><h1 className="text-2xl font-bold">Strategy not found</h1></main>;
  }
  return (
    <main className="mx-auto max-w-4xl space-y-6 p-6">
      <StrategySummary run={run} />
      <section className="rounded-2xl border border-slate-200 bg-white p-5">
        <h2 className="text-lg font-semibold">Parameters</h2>
        <pre className="mt-3 overflow-auto rounded-xl bg-slate-950 p-4 text-sm text-slate-50">{JSON.stringify(run.params, null, 2)}</pre>
      </section>
    </main>
  );
}
