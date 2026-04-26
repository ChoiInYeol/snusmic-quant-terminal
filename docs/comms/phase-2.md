# Phase 2 — stakeholder communication

**Purpose:** this file satisfies the Phase 2 pre-merge communications gate
(AC #0 in `.omc/plans/consensus-full-overhaul.md`). The PR description must
contain either a hosted announcement URL (`Comms announcement: https://...`)
or reference this file (`Comms: see docs/comms/phase-2.md`).

**Announcer:** repo maintainer (`@ChoiInYeol` for this repo).
**Announcement lead time:** 24h before merge.
**Framing:** "honest OOS baseline enables future strategy improvements" — not
"we lied before." Position the change as methodological maturation.

---

## What changes on Phase 2 merge-day

1. **Headline metric switches from `total_return` to OOS Sortino.** The
   dashboard's headline strategy ranking is now driven by
   `sortino_oos`, computed on each fold's out-of-sample window across a
   3-fold 70/30 walk-forward split. See
   `docs/decisions/phase-2-objective.md` for the locked objective
   contract.
2. **Reported Sortino / Sharpe / total_return will drop.** Iteration-1
   numbers were in-sample-optimised. Expect headline metrics to land
   meaningfully lower once OOS values replace them. Side-by-side columns
   (`sortino_in_sample` + `sortino_oos`) stay through end of 2026-Q4 so
   stakeholders can directly compare the optimism gap.
3. **Execution events carry lookahead-safe metadata.** Each trade row now
   records `signal_date` (t-1), `decision_price` (t-1 close),
   `fill_price` (t open, fallback t close), and `fill_rule`. See
   `src/snusmic_pipeline/backtest/engine.py`.
4. **Delisted symbols are no longer silently dropped.** A position whose
   symbol stops reporting prices for 21+ trading days is exited with
   `reason='delisting'` and `fill_rule='delisting_last_close'` at the
   last observed close.
5. **NaN-close policy change (semantic drift, Principle-6 guarded).** The
   backtest engine forward-fills missing close values per symbol instead
   of dropping them, with a `close_imputed` in-memory flag. The main
   `daily_prices.schema.json` declares
   `close.nan_policy='forward_fill_then_flag'`; the
   `daily_prices.v2.schema.json` sidecar committed alongside this PR
   satisfies the semantic-drift guard in
   `scripts/check_schema_compat.py`.

## Rollback

- **Revert the PR.** Technical revertability is preserved. The
  `--legacy-objective` CLI flag (via env var `SNUSMIC_LEGACY_OBJECTIVE=1`)
  restores `total_return` as the objective without reverting the look-ahead
  fix (the 4-site fix is unconditional per plan line 172). The flag deletes
  in Phase 8.
- **Social rollback cost is real.** Reverting after stakeholders have seen
  the OOS number is credibility whiplash; a second comms cycle with its own
  framing note is required.

## Pre-merge checklist for the PR author

- [ ] This file or a hosted announcement URL is referenced in the PR body
      (`Comms: see docs/comms/phase-2.md`).
- [ ] The announcement was posted ≥24h before merge.
- [ ] Side-by-side `sortino_in_sample` vs `sortino_oos` screenshot attached
      to the PR description.
- [ ] The sibling `docs/schemas/daily_prices.v2.schema.json` is committed.
- [ ] `docs/decisions/phase-2-objective.md` primary_objective is locked
      and matches the `strategy_runs` schema columns.
