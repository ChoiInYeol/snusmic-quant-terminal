/**
 * Phase 8 — vitest coverage for the dashboard data helpers.
 */

import { describe, expect, test } from 'vitest';
import { bestStrategy } from './data';
import type { StrategyRun } from './generated/types';

function strategy(run_id: string, total_return: number, objective?: number | null): StrategyRun {
  return {
    run_id,
    strategy_name: run_id,
    weighting: '1/N',
    entry_rule: 'mtt',
    rebalance: 'weekly',
    stop_loss_pct: 0.08,
    reward_risk: 3,
    max_pool_months: 12,
    target_hit_multiplier: 1,
    lookback_days: 252,
    final_wealth: 1 + total_return,
    final_account_value_krw: 10_000_000 * (1 + total_return),
    total_contributed_capital_krw: 10_000_000,
    net_profit_krw: 10_000_000 * total_return,
    initial_capital_krw: 10_000_000,
    monthly_contribution_krw: 1_000_000,
    total_return,
    cagr: null,
    annualized_volatility: null,
    sharpe: null,
    sortino: null,
    max_drawdown: 0,
    calmar: null,
    realized_return: 0,
    live_return: 0,
    exposure_ratio: 0,
    average_positions: 0,
    max_positions: 0,
    turnover_events: 0,
    trade_count: 0,
    win_rate: null,
    target_hit_rate: null,
    stop_loss_hit_rate: null,
    average_holding_days: null,
    objective: (objective ?? total_return) as number,
    open_position_count: 0,
    status: 'ok',
    sortino_in_sample: null,
    sortino_oos_tail: null,
    sharpe_oos_tail: null,
    max_drawdown_oos_tail: null,
    fold_count: null,
  };
}

describe('bestStrategy', () => {
  test('returns the highest objective even when total_return is lower', () => {
    const a = strategy('a', 0.20, 0.05);
    const b = strategy('b', 0.10, 0.50);
    expect(bestStrategy([a, b])?.run_id).toBe('b');
  });

  test('falls back to total_return when objective is missing', () => {
    const a = strategy('a', 0.30, null);
    const b = strategy('b', 0.10, null);
    expect(bestStrategy([a, b])?.run_id).toBe('a');
  });

  test('returns null on an empty list', () => {
    expect(bestStrategy([])).toBeNull();
  });
});
