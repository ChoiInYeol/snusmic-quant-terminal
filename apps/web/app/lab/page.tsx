export default function LabPage() {
  return (
    <main className="mx-auto max-w-5xl space-y-5 p-6">
      <p className="text-sm font-medium text-amber-700">Research lab</p>
      <h1 className="text-3xl font-bold text-slate-950">Local strategy search workflow</h1>
      <p className="text-slate-600">Optuna runs only on the local Python side. The deployed web app reads static JSON exports and never imports Optuna, yfinance, or Python simulation code.</p>
      <ol className="list-decimal space-y-2 pl-5 text-slate-700">
        <li>Run <code>uv run python scripts/run_optuna_search.py --trials 100</code>.</li>
        <li>Export web artifacts with <code>uv run python scripts/export_optuna_artifacts.py</code>.</li>
        <li>Review /strategies for in-sample winners and risk warning badges.</li>
      </ol>
    </main>
  );
}
