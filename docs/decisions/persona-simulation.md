# Persona simulation contract

**Status:** accepted
**Scope:** end-to-end account-level simulation of 5 investor personas + 1 benchmark
on the SNUSMIC report universe.

## Why this exists

The existing `snusmic_pipeline.backtest` module is **weight-based** (positions
are floats summing to 1.0, returns are computed from `weight × asset_return`).
That is fine for strategy comparison but does not look like a real brokerage
account: there is no cash ledger, no integer share count, no commission/tax,
and no escalating savings plan.

This module (`snusmic_pipeline.sim`) adds a **share-based account ledger** that
mirrors what a Korean retail brokerage shows: a KRW cash balance, integer-share
holdings with weighted-average cost, fees on every fill, and a step-up monthly
contribution.

It is run as a separate experiment surface so the production
`run-backtest` CLI is not affected.

## Account scenario (fixed inputs)

| Field | Value | Note |
| --- | --- | --- |
| `initial_capital_krw` | 10,000,000 | One-shot deposit on day 0 |
| `monthly_contribution_krw` | 1,000,000 | First trading day of every later month |
| `escalation_step_krw` | 500,000 | Increment applied on each escalation tick |
| `escalation_period_years` | 2 | After 2y → +500k, after 4y → +1.0M, etc. |
| `commission_bps` | 1.5 | 0.015% per fill (KR retail order) |
| `sell_tax_bps` | 18 | 0.18% sell-side tax (KOSPI/KOSDAQ) |
| `slippage_bps` | 5 | 0.05% adverse slippage modeled into fill price |

Parameters travel on `SavingsPlan` and `BrokerageFees` Pydantic models so they
are easy to swap from a single config file.

## Personas

All personas operate on the same `(reports, prices)` warehouse already produced
by the backtest module. They differ in **what they buy** and **when they sell**.

### 1. `oracle` — Prophet (perfect lookahead)
At every cash event the prophet looks at the realized post-event price path
of every active report and:

- ranks reports by realized peak return reachable on or after today,
- if the top symbol's realized return is `>= dominance_threshold × second-best`,
  concentrates 100% on the top symbol,
- otherwise allocates proportional to realized return weights (long-only,
  sum to 1, capped at `max_weight`).

It exits at each symbol's realized peak. This is an **upper bound**, not an
executable strategy.

### 2. `weak_prophet` — 6-month forward max-Sharpe
At every rebalance date `t`:

1. take all reports active at `t` whose price history covers `[t, t+6M]`,
2. compute realized daily returns over `[t, t+6M]` (this is the 6-month
   look-ahead bias the user explicitly opts into),
3. solve `max (μ − rf) / σ_p` long-only, sum-to-1, with optional
   `max_weight` cap, via `scipy.optimize.minimize` (SLSQP),
4. rebalance the share book to the resulting weights.

### 3. `smic_follower` — 1/N true believer
- Buys every active SMIC report with available price data.
- Cash arrives → re-allocate the entire book to 1/N across all currently
  active (non-target-hit) names.
- Sells **only** when the close ≥ `target_price` (per report).
- Never sells at a loss. Holds delisted / aged reports until their target
  hits or the simulation ends.

### 4. `smic_follower_v2` — 1/N with stop-loss
Same as v1 but adds three exit gates evaluated each trading day:

| Rule | Condition | Reason code |
| --- | --- | --- |
| `time_loss` | `holding_days ≥ time_loss_days` AND `unrealized_return < 0` | held a year, still red |
| `averaged_down_stop` | last buy was an add-on AND `unrealized_return < -averaged_down_stop_pct` | doubled down, still bleeding |
| `report_age_stop` | `now − report_publication_date ≥ report_age_stop_days` AND target not hit | report theis is too old |

`time_loss_days` defaults to **365**, `averaged_down_stop_pct` to **0.20**,
`report_age_stop_days` to **730**.

### 5. `all_weather` — benchmark (not a persona, a yardstick)
Buy-and-hold all-weather portfolio with monthly rebalance:

- Gold ETF (`GLD`, USD → KRW)
- NASDAQ-100 ETF (`QQQ`, USD → KRW)
- S&P 500 ETF (`SPY`, USD → KRW)
- KOSPI 200 ETF (`069500.KS`, KRW native)

Each cash event splits the inflow 1/4 per asset; once a month the book is
rebalanced back to 25/25/25/25 by trading existing shares.

## Realistic profit calculation

Every persona shares the same **share-based** ledger:

```
holdings[symbol] = {
    qty: int,                  # share count, never fractional
    avg_cost: Decimal,         # weighted-average cost in KRW
    total_cost_krw: Decimal,   # sum of all buy fills (incl. fees)
}
cash_krw: Decimal
realized_pnl_krw: Decimal      # sum of (sell_price − avg_cost) × qty − fees
```

A buy fill subtracts `qty × fill_price + commission` from cash. A sell fill
adds `qty × fill_price − commission − sell_tax` to cash and increments
realized PnL by the difference between fill proceeds and the proportional
average cost (FIFO not used — Korean retail uses moving-average cost basis).

Mark-to-market equity = `cash + Σ qty × close_price`. Net profit = equity −
total contributed capital. **This is what the user sees in their brokerage
app**, not a weight-based time-weighted return.

## Data contracts (SSOT)

Everything that crosses module boundaries is a Pydantic v2 `BaseModel` with
`extra="forbid"` and (where shape is fixed) `frozen=True`. The full registry
lives in `src/snusmic_pipeline/sim/contracts.py`:

| Contract | Mutable? | Purpose |
| --- | --- | --- |
| `SavingsPlan` | frozen | Initial capital + monthly contribution + escalation |
| `BrokerageFees` | frozen | commission/tax/slippage in bps |
| `BenchmarkAsset` | frozen | One slot of the all-weather basket |
| `PersonaConfig` (and 5 subclasses) | frozen | Each persona's tunable knobs |
| `SimulationConfig` | frozen | Root config: time range + plan + fees + personas |
| `Trade` | frozen | One fill: persona, date, symbol, side, qty, price, fees |
| `EquityPoint` | frozen | Daily mark-to-market equity row |
| `PersonaSummary` | frozen | Final stats: net profit, IRR, max DD, win rate |
| `SimulationResult` | frozen | One result per persona |

SDD/TDD methodology: the test suite in `tests/sim/` exercises each contract
roundtrip first, then builds engine behavior on top of those guarantees. New
parameters are added by extending the relevant config model — the simulation
runner reads `SimulationConfig` and never relies on globals.

## Output

`scripts/run_persona_sim.py` writes:

- `data/sim/personas.json` — `SimulationResult.model_dump_json()`
- `data/sim/equity_daily.csv` — long-form `(persona, date, equity_krw, cash_krw)`
- `data/sim/trades.csv` — long-form trade ledger
- `data/sim/equity_curves.png` — matplotlib equity curve overlay
- `data/sim/net_profit_bar.png` — bar chart of final net profit per persona

The PNGs are the user-facing graphs requested in the brief.
