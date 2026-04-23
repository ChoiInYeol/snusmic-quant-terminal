from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


WEIGHTING_METHODS = ["1/N", "max_return", "min_var", "sharpe", "sortino", "cvar", "calmar"]
ENTRY_RULES = ["mtt_or_rs", "mtt_and_rs", "target_only", "hybrid_score"]
REBALANCE_FREQUENCIES = ["daily", "weekly", "biweekly", "monthly"]


@dataclass(frozen=True)
class BacktestConfig:
    name: str = "mtt_or_rs_equal_weight"
    weighting: str = "1/N"
    entry_rule: str = "mtt_or_rs"
    rs_threshold: float = 70.0
    mtt_slope_months: int = 1
    max_pool_months: int = 12
    target_hit_multiplier: float = 1.0
    stop_loss_pct: float = 0.08
    reward_risk: float = 3.0
    rebalance: str = "weekly"
    lookback_days: int = 252
    risk_free_rate: float = 0.03
    min_target_upside: float = 0.0
    exit_on_signal_loss: bool = True
    allow_reentry: bool = True

    def normalized(self) -> "BacktestConfig":
        if self.weighting not in WEIGHTING_METHODS:
            raise ValueError(f"Unknown weighting method: {self.weighting}")
        if self.entry_rule not in ENTRY_RULES:
            raise ValueError(f"Unknown entry rule: {self.entry_rule}")
        if self.rebalance not in REBALANCE_FREQUENCIES:
            raise ValueError(f"Unknown rebalance frequency: {self.rebalance}")
        if not 0 < self.stop_loss_pct < 1:
            raise ValueError("stop_loss_pct must be between 0 and 1")
        if self.reward_risk <= 0:
            raise ValueError("reward_risk must be positive")
        if self.max_pool_months <= 0:
            raise ValueError("max_pool_months must be positive")
        if self.lookback_days < 20:
            raise ValueError("lookback_days must be at least 20")
        return self

    def to_dict(self) -> dict[str, Any]:
        return asdict(self.normalized())


@dataclass(frozen=True)
class StrategySummary:
    run_id: str
    strategy_name: str
    weighting: str
    entry_rule: str
    rebalance: str
    rs_threshold: float
    stop_loss_pct: float
    reward_risk: float
    max_pool_months: int
    target_hit_multiplier: float
    final_wealth: float
    total_return: float
    cagr: float | None
    annualized_volatility: float | None
    sharpe: float | None
    sortino: float | None
    max_drawdown: float
    calmar: float | None
    realized_return: float
    live_return: float
    exposure_ratio: float
    average_positions: float
    max_positions: int
    turnover_events: int
    trade_count: int
    win_rate: float | None
    target_hit_rate: float | None
    stop_loss_hit_rate: float | None
    average_holding_days: float | None
    objective: float
    status: str


def dataclass_rows(items: list[object]) -> list[dict[str, Any]]:
    return [asdict(item) for item in items]
