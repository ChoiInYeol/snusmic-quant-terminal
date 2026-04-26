import type { StrategyRun } from '../lib/data';
import { pct } from '../lib/format';

export function StrategyRanking({
  strategies,
  selectedRunId,
  onSelect,
}: {
  strategies: StrategyRun[];
  selectedRunId: string;
  onSelect: (runId: string) => void;
}) {
  return (
    <div className="ranking">
      {[...strategies]
        .sort((a, b) => b.total_return - a.total_return)
        .slice(0, 8)
        .map((strategy, index) => (
          <button key={strategy.run_id} className={strategy.run_id === selectedRunId ? 'rank active' : 'rank'} onClick={() => onSelect(strategy.run_id)}>
            <span>{index + 1}</span>
            <strong>{strategy.strategy_name}</strong>
            <b>{pct(strategy.total_return)}</b>
          </button>
        ))}
    </div>
  );
}
