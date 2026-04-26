# Phase 2 — Optuna primary objective

**Status:** Decided (2026-04-25).
**Scope:** Decision required *before* Phase 2 coding starts, per
`.omc/plans/consensus-full-overhaul.md` (Phase 2 AC #3 blocker).
**Consumers:** `scripts/check_schema_compat.py` reads this file to validate
the `{primary_objective}_in_sample` / `{primary_objective}_oos` column names
in `strategy_runs.csv`.

## Decision

```yaml
primary_objective: sortino
schema_suffixes:
  in_sample: sortino_in_sample
  oos:       sortino_oos
legacy_fallback_cli_flag: "--legacy-objective"
legacy_fallback_metric:   total_return
```

## Rationale

1. **Sortino matches the portfolio profile.** SNUSMIC's MTT-gated strategy
   runs a long-only book with infrequent exits on absolute stop-losses.
   Downside volatility (what Sortino penalizes) is the risk an investor
   actually feels; symmetric variance (Sharpe) overcounts upside excursions
   that are not risk.
2. **Single-objective keeps plotting simple.** A multi-objective Pareto
   surface via `optuna.study.add_objective` is richer but forces the dashboard
   to render a 2-D frontier instead of a scalar ranking. That is a Phase 7
   visualization problem, not a Phase 2 one. Ship a scalar now, evaluate a
   multi-objective study after Phase 7's chart rework.
3. **Max-drawdown as a constraint, not an objective.** Phase 2 wires a
   constraint `max_drawdown <= 0.35` into the Optuna trial via
   `study.add_trial_constraint` (or equivalent soft penalty when unavailable).
   Trials that violate the constraint are pruned — the objective stays
   one-dimensional.
4. **Walk-forward 3-fold, 70/30 split each** (per plan line 159, already
   resolved in iteration 2 of ralplan). Sortino is computed per fold; OOS
   Sortino is the Optuna objective; in-sample Sortino is reported alongside
   for stakeholder-facing drift detection.
5. **Legacy fallback via `--legacy-objective` is retained** through Phase 8
   deletion per plan. The flag restores `total_return` maximisation over the
   full horizon — it does *not* revive the 4-site look-ahead bugs, which stay
   fixed unconditionally (plan line 172).

## Alternatives considered

- **Sharpe.** Rejected as primary: symmetric variance is wrong risk proxy for
  a long-only MTT strategy. We still report `sharpe_oos` (computed cheaply
  from the same equity curve) as a secondary diagnostic column in
  `strategy_runs.csv` — it's additive per Principle 6 and adds ~0 runtime.
- **Multi-objective (Sortino + max-DD).** Rejected for Phase 2, revisited
  after Phase 7 ships the chart upgrade that can render a Pareto surface.
- **Calmar.** Rejected: too unstable for short fold windows (<6 months) —
  single drawdown events dominate the ratio.

## Column contract

`strategy_runs.csv` in Phase 2 gains these additive columns:

| column                | type             | description                                                 |
|-----------------------|------------------|-------------------------------------------------------------|
| `sortino_in_sample`   | `float \| null`  | Sortino on each fold's IS window, averaged.                 |
| `sortino_oos`         | `float \| null`  | Sortino on each fold's OOS window, averaged (= `objective`).|
| `sharpe_oos`          | `float \| null`  | Secondary diagnostic.                                       |
| `max_drawdown_oos`    | `float`          | Worst OOS drawdown across folds (used by constraint check). |
| `fold_count`          | `int`            | `3` by default; recorded for reproducibility.               |

`scripts/check_schema_compat.py` enforces that the `*_in_sample` / `*_oos`
prefix matches `primary_objective` above. Changing `primary_objective` after
Phase 2 merges requires a `strategy_runs.v2.schema.json` sidecar (Principle 6).

## Consequences

- Headline dashboard metric becomes Sortino OOS, and it **will** be lower than
  the iteration-1 in-sample `total_return` number. Phase 2's AC #0 pre-merge
  comms gate handles the announcement (plan lines 171-172); this decision
  file is the technical companion artifact.
- `--legacy-objective` flag deletes in Phase 8 per plan scope (line 312).
- Deletion of `sortino_in_sample` from `strategy_runs.csv` is **punted to
  post-2026-Q4** per plan ADR follow-ups and `.omc/plans/open-questions.md`.

## Rollback

Reverting the Phase 2 PR restores the pre-Phase-2 Optuna objective. The
`*_in_sample` / `*_oos` columns are additive; pre-Phase-2 readers ignore
them (Principle 6). No on-disk CSV rewrite required.
