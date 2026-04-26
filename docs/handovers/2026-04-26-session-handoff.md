# 2026-04-26 Session Handoff

## Current state

- Branch: `main`
- Latest pushed commit: `2666ee1 Promote price metrics to a typed web artifact contract`
- GitHub Actions on latest commit: green
  - `ci`
  - `atomic-rehoming`
  - `Sync SNUSMIC reports`
  - `Publish GitHub Pages mirror`
- Vercel production HTTP check: 200
  - `https://snusmic-quant-terminal-choiinyeols-projects.vercel.app/`
- GitHub Pages mirror HTTP check: 200
  - `https://choiinyeol.github.io/snusmic-quant-terminal/`
- Working tree after this handoff commit should be clean except ignored/untracked runtime artifacts such as `.omc/` and `apps/web/.omc/`.

## Product direction locked in this session

The project should stay modest and maintainable.

Primary product surface:

- **Vercel / Next.js dashboard is primary** and should be the polished UI.
- **GitHub Pages/static page is a minimal mirror/archive**, not a full duplicate product surface unless that becomes cheap and obvious.

Optuna stance:

- Do **not** prioritize running Optuna locally right now.
- Local compute/design are insufficient for serious search.
- First priority is clean data contracts, explicit schemas, and maintainable baseline/strategy artifacts.
- Optuna should become an optional/server-side or later research phase once the baseline contracts are stable.

## Strategy framing

The project goal is to develop a strategy that sits between two baselines:

1. **Oracle / “투자의 신”**
   - Future-informed upper bound.
   - Knows all future prices in the SMIC report universe.
   - Chooses ideal entry/exit timing and potentially ideal allocation.
   - Real strategies should not exceed this in a sane backtest.

2. **SMIC follower / “스믹 추종자”**
   - Buys at report publication.
   - Sells at target if hit; otherwise remains open/marked at latest available price.
   - This is the naive lower benchmark.

3. **Real model strategy**
   - Should not beat oracle.
   - Should beat SMIC follower consistently enough to justify the project.
   - Optuna/search later tries to find strategies in this band.

Canonical decision doc:

- `docs/decisions/strategy-baselines.md`

## Completed changes in recent sessions

### 1. Baseline-band strategy contract

Implemented in commit:

- `83df60d Define sober strategy baseline band`

Main changes:

- Added `docs/decisions/strategy-baselines.md`.
- Added baseline fields to `PriceMetric` in `src/snusmic_pipeline/quant.py`:
  - `oracle_entry_price`
  - `oracle_exit_price`
  - `oracle_return`
  - `oracle_buy_lag_days`
  - `oracle_holding_days`
  - `smic_follower_entry_price`
  - `smic_follower_exit_price`
  - `smic_follower_return`
  - `smic_follower_holding_days`
  - `smic_follower_status`
- Updated Vercel dashboard Opportunity section to frame rows as `스믹 추종자 ↔ 예언자`.
- Updated static-site copy to clarify mirror/archive role.
- Added baseline tests.

### 2. Roadmap aligned to product goal

Implemented in commit:

- `bda2286 Align roadmap around baseline-band strategy research`

Main changes:

- README reframed around strategy research between follower and oracle.
- Vercel primary / Pages mirror clarified.
- Optuna documented as later/optional, not local immediate goal.
- Added synthetic baseline-band test in `tests/test_quant.py`.

### 3. `price_metrics.json` promoted to typed artifact contract

Implemented in commit:

- `2666ee1 Promote price metrics to a typed web artifact contract`

Main changes:

- Added `src/snusmic_pipeline/artifact_schemas.py`.
- Added `docs/schemas/price_metrics.schema.json`.
- Updated `scripts/export_schemas.py` so schema export covers both:
  - warehouse CSV table schemas from `TABLE_MODELS`
  - JSON artifact schemas from `ARTIFACT_MODELS`
- Updated `apps/web/scripts/gen-types.mjs` header/comment.
- Generated `PriceMetric` TS interface in `apps/web/src/lib/generated/types.ts`.
- Removed hand-written `PriceMetric` type from `apps/web/src/lib/data.ts`.
- CLI now validates `price_metrics.json` rows before writing:
  - `validate_price_metric_rows(dataclass_rows(price_metrics))`
- Added `tests/test_price_metrics_schema.py`:
  - schema fields match `PriceMetric` dataclass fields
  - baseline fields validate
  - unexpected fields are rejected

### 4. CI/build fixes and data-integrity fixes already landed

Already completed before this handoff:

- Ruff format CI failure fixed.
- Next static export fixed by adding Suspense boundary around `nuqs/useSearchParams` consumers.
- Leading-zero ticker preservation fixed.
- `coerce_numbers_to_str` fallback removed.
- dtype hint registry introduced for CSV reads.
- OOS naming made more honest: `sortino_oos_tail` etc.

### 5. Shell convenience

User requested yolo defaults for `codex` / `omx`.

Done in `~/.zshrc`:

- `codex()` wrapper adds `--dangerously-bypass-approvals-and-sandbox` unless already in danger/full-auto mode.
- `omx()` wrapper adds `--yolo` for session/agent starts but avoids breaking management commands like `omx setup`, `omx doctor`, `omx version`.
- Existing alias conflicts handled with `unalias`.
- Backup file was created before editing.

## Verified after latest implementation

Local verification on commit `2666ee1`:

- `pytest tests/ -q` → `80 passed, 1 skipped`
- `ruff check .` → clean
- `ruff format --check .` → clean
- `mypy src/snusmic_pipeline/backtest src/snusmic_pipeline/artifact_schemas.py` → success
- `npm --prefix apps/web run lint` → clean
- `npm --prefix apps/web test -- --run` → 6 passed
- `npm --prefix apps/web run gen:types:check` → 5 schemas up to date
- `python scripts/export_schemas.py --check` → 5 schemas up to date
- `python scripts/check_schema_compat.py --base-ref HEAD` → no Principle-6 violations
- `GITHUB_PAGES=true NEXT_PUBLIC_BASE_PATH=/snusmic-quant-terminal npm --prefix apps/web run build` → static build success
- `python -m snusmic_pipeline build-site` → success

Remote verification:

- GitHub Actions all green on `2666ee1`.
- Vercel production HTTP 200.
- GitHub Pages mirror HTTP 200.

## Recommended next work

### P0 — data contract / maintainability

1. **Promote `portfolio_backtests.json` to typed artifact contract**
   - Add Pydantic artifact schema.
   - Add `docs/schemas/portfolio_backtests.schema.json`.
   - Generate TS type.
   - Validate CLI writes.
   - Add schema tests.
   - This mirrors the `price_metrics.json` work and is the safest next step.

2. **Split baseline computation into small pure helpers**
   - Candidate functions:
     - `compute_oracle_baseline(close, publication_date)`
     - `compute_smic_follower_baseline(close, publication_date, target)`
     - `compute_target_hit(close, target)`
     - `compute_price_distribution_metrics(close)`
   - Keep behavior first; add tests before/with refactor.

3. **Strengthen baseline invariant tests**
   - `smic_follower_return <= oracle_return` when both are available.
   - oracle uses publication-or-later prices only.
   - target hit vs open behavior.
   - no target / no price history / delisting-like cases.

### P1 — Vercel primary UI, modest scope

4. **Add simple baseline summary cards to Vercel dashboard**
   - SMIC follower average return.
   - Best/selected model strategy return.
   - Oracle average return.
   - Copy: “목표는 예언자를 이기는 것이 아니라, 스믹 추종자보다 일관되게 나은 전략을 찾는 것이다.”

5. **Keep GitHub Pages as minimal mirror/archive**
   - Do not chase full UI parity with Vercel.
   - Make primary Vercel link obvious.
   - Keep artifact/archive access simple.

6. **Reduce `apps/web/app/page.tsx` size gradually**
   - Extract only obvious sections.
   - Avoid overengineering/new dependencies.
   - Candidate components:
     - `BaselineBandSummary`
     - `OpportunityTable`
     - `StrategySummary`
     - `ReportArchive`
     - `ChartPanels`

### P2 — strategy research / Optuna later

7. **Document Optuna as optional/server research path**
   - Local is not default.
   - Dashboard/build should not depend on Optuna.
   - Search outputs should attach to typed artifacts only after schema stability.

8. **Design strategy comparison artifact**
   - Future fields:
     - `model_vs_follower_alpha`
     - `oracle_gap`
     - `oracle_capture_ratio`
     - `hit_rate`
     - `max_drawdown`
     - `turnover`
   - This can later feed both Vercel UI and Optuna result comparisons.

### P3 — defer unless needed

- Plotly removal / chart library switch.
- Playwright visual regression.
- Full atomic re-homing production PR.
- GitHub Actions Node 24 warning cleanup.
- Parquet migration.

## Important notes for next agent

- Do not add `.omc/` or `apps/web/.omc/` blindly; they are runtime artifacts.
- Prefer small schema/test/UI changes over broad refactors.
- No new dependencies unless clearly needed.
- Vercel dashboard is the primary UI; static Pages can stay minimal.
- Optuna is not the immediate local execution priority.
- When adding new data fields, update schema + generated TS + tests together.
