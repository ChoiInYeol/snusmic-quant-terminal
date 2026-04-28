# Next.js / Optuna Showcase Verification Guide

This guide is the integration-readiness checklist for the planned public showcase in
`.omx/plans/2026-04-28-nextjs-optuna-showcase-plan.md`. It keeps Python as the compute
source of truth and treats the future Next.js app as a static artifact consumer.

## Ownership boundaries

- Python data/warehouse/simulation exports remain the canonical compute layer.
- Local Optuna search/export must write artifacts; the web app must not run Optuna or mutate
  `data/warehouse/` at request time.
- Next.js should read generated JSON/CSV-derived artifacts from `data/web/` or
  `apps/web/public/artifacts/`.
- Verification/docs changes may live in `README.md` and `docs/`; implementation fixes in worker-owned
  Python or web files should be reported before editing unless they are required to unblock integration.

## Required verification sequence

Run these checks after integrating worker branches and before marking the showcase ready:

```bash
# Python quality gate
uv run pytest -q --durations=10
uv run ruff check .
uv run ruff format --check .
uv run mypy

# Data artifact gate
uv run python -m snusmic_pipeline run-sim
# When the web export command exists, run it here. Expected output root: data/web/.
# Example target shape from the plan:
#   data/web/overview.json
#   data/web/personas.json
#   data/web/reports.json
#   data/web/report-rankings.json
#   data/web/missing-symbols.json
#   data/web/prices/*.json

# Optuna artifact gate, local only
# When the local search/export commands exist, run a small deterministic smoke search first,
# then export artifacts under data/optuna/ and/or data/web/strategy-runs.json.

# Web quality gate, after apps/web is integrated
cd apps/web
npm run typecheck
npm run build
```

## Artifact presence checklist

The integrated branch should have all of the following before a public demo:

- `data/warehouse/reports.csv`
- `data/warehouse/daily_prices.csv`
- `data/warehouse/fx_rates.csv`
- `data/sim/summary.csv`
- `data/sim/report_stats.json`
- `data/sim/report_performance.csv`
- `data/web/overview.json`
- `data/web/reports.json`
- `data/web/report-rankings.json`
- `data/web/missing-symbols.json`
- `apps/web/package.json`
- `apps/web/app/page.tsx`
- report explorer/detail routes
- strategy/Optuna routes or clear placeholder pages explaining that Optuna runs locally

## Current worker-5 baseline evidence

On the worker-5 branch before other worker branches were integrated:

- `uv run pytest -q --durations=10` passed: 82 tests in 46.74s.
- `uv run ruff check .` passed.
- `uv run mypy` passed: 19 source files.
- Existing warehouse/simulation artifacts are present under `data/warehouse/` and `data/sim/`.
- `apps/web/package.json`, `data/web/`, and `data/optuna/` are not present in this isolated worktree yet,
  so web build and generated web/Optuna artifact checks remain pending integration gates.

## Integration risk notes

- Do not count a green Python suite as a green showcase: the web app has its own typecheck/build gate.
- Do not deploy a web page that recomputes Optuna results. Optuna is local-only; the web app should display
  exported trial summaries and strategy artifacts.
- Keep missing-price symbols and extraction caveats visible in the web data-quality page instead of silently
  dropping them from UI counts.
- Treat generated artifact schemas as contracts. If a field is renamed, update Python export tests and TypeScript
  loaders together.
