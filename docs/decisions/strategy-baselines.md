# Strategy baseline contract

**Status:** accepted  
**Scope:** cheap deterministic baselines only; no Optuna run required.

## Why this exists

The project is not trying to prove that an optimizer can beat hindsight. The
research goal is to place realistic strategies between two explicit reference
points over the SNUSMIC report universe:

1. **Oracle / investment-god upper bound** — an impossible future-informed
   trader that knows the post-publication path and chooses the best long-only
   buy/sell pair with the buy at or after publication and the sell at or after
   that buy. This is a ceiling and should not be beaten by a realistic strategy
   under the same price universe.
2. **SMIC follower baseline** — a simple report follower that buys at the first
   tradable publication price and exits exactly at the report target when hit;
   if the target is not hit, the position remains open and is marked to the
   latest price.
3. **Account scenario** — walk-forward strategy runs use a fixed KRW account:
   KRW 10,000,000 initial capital plus KRW 1,000,000 at the first trading day of
   each later month. Rebalance days reallocate the selected book to its target
   weights so active books do not intentionally retain cash.
3. **Model strategy** — the actual strategy family. Future Optuna/search work
   should try to beat the follower while staying below the oracle ceiling.

## Data contract

`price_metrics.json` exposes the per-report band directly:

| Field | Meaning |
| --- | --- |
| `oracle_entry_price` | Entry price from the maximum-return chronological long-only trade at/after publication. |
| `oracle_exit_price` | Exit price from that same chronological trade, never before the oracle entry. |
| `oracle_return` | `oracle_exit_price / oracle_entry_price - 1` for the selected chronological pair. |
| `oracle_buy_lag_days` | Days from publication to oracle entry. |
| `oracle_holding_days` | Days from oracle entry to oracle exit. |
| `smic_follower_entry_price` | First tradable close at/after publication. |
| `smic_follower_exit_price` | Target price if hit, otherwise latest price. |
| `smic_follower_return` | Realized target return or current open return. |
| `smic_follower_holding_days` | Days to target hit or latest mark date. |
| `smic_follower_status` | `target_hit`, `open`, or `unavailable`. |

## Account-level assumptions

- The SMIC follower account is `1/N` only: every active report position receives
  the same target weight at rebalance.
- A target-hit position is sold when the target is observed. A losing or still
  open position is held with the belief that the target will eventually be hit;
  new monthly savings are still contributed and rebalanced under the same rule.
- The oracle account is future-informed and therefore may choose the best
  long-only allocation for the interval being evaluated. It is an upper bound,
  not an executable strategy.
- Account-level KRW columns are additive diagnostics; percentage performance
  columns remain time-weighted so historical comparisons are stable.

## Invariant

For one report with valid price history, `smic_follower_return <= oracle_return`
should normally hold because the oracle is allowed to choose the highest-return
chronological long-only entry/exit pair with future information. If this invariant appears violated, inspect data
quality first: currency conversion, missing bars, target-price extraction, and
split-adjusted price history are the likely causes.

## Output surface decision

The repository is now server-simulation first. Python code and committed CSV/JSON
data artifacts are the durable contract; frontend deployment surfaces are no
longer part of the core product path.
