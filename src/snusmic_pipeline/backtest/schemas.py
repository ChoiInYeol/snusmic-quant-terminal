"""Typed table schemas for the backtest warehouse.

Every model here is a Pydantic v2 `BaseModel` with `extra='forbid'`. Models
exposed in :data:`TABLE_MODELS` are used by :mod:`snusmic_pipeline.backtest.warehouse`
to validate rows at both read AND write boundaries (Principle 2).

Column-level ClassVar metadata (``semantic_version``, ``nan_policy``) is read
by :mod:`scripts.export_schemas` and :mod:`scripts.check_schema_compat` to enforce
Principle 6 ("additive AND semantics-preserving within a minor version").
"""

from __future__ import annotations

from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, field_validator

WEIGHTING_METHODS = ["1/N", "max_return", "min_var", "sharpe", "sortino", "cvar", "calmar"]
ENTRY_RULES = ["mtt", "target_only", "mtt_target"]
REBALANCE_FREQUENCIES = ["daily", "weekly", "biweekly", "monthly"]
LOOKBACK_WINDOWS = {
    "3M": 63,
    "6M": 126,
    "12M": 252,
    "24M": 504,
}


class BacktestConfig(BaseModel):
    """Per-strategy configuration. Frozen so the hash-stable run_id derivation holds."""

    model_config = ConfigDict(frozen=True, extra="forbid", validate_assignment=True)

    name: str = "mtt_equal_weight"
    weighting: str = "1/N"
    entry_rule: str = "mtt"
    mtt_slope_months: int = 1
    max_pool_months: int = 12
    target_hit_multiplier: float = 1.0
    stop_loss_pct: float = 0.08
    reward_risk: float = 3.0
    rebalance: str = "weekly"
    lookback_days: int = 504
    risk_free_rate: float = 0.03
    min_target_upside: float = 0.0
    exit_on_signal_loss: bool = True
    allow_reentry: bool = True
    # Phase 2b legacy escape — when True the backtest reports `objective =
    # total_return` instead of `sortino_oos_tail`. Must travel with the config so
    # the run_id hash diverges between modes (per code-review CRITICAL-4).
    # The phase 2a look-ahead fix is unconditional and is NOT affected.
    legacy_objective: bool = False

    @field_validator("weighting")
    @classmethod
    def _check_weighting(cls, v: str) -> str:
        if v not in WEIGHTING_METHODS:
            raise ValueError(f"Unknown weighting method: {v}")
        return v

    @field_validator("entry_rule")
    @classmethod
    def _check_entry_rule(cls, v: str) -> str:
        if v not in ENTRY_RULES:
            raise ValueError(f"Unknown entry rule: {v}")
        return v

    @field_validator("rebalance")
    @classmethod
    def _check_rebalance(cls, v: str) -> str:
        if v not in REBALANCE_FREQUENCIES:
            raise ValueError(f"Unknown rebalance frequency: {v}")
        return v

    @field_validator("stop_loss_pct")
    @classmethod
    def _check_stop_loss(cls, v: float) -> float:
        if not 0 < v < 1:
            raise ValueError("stop_loss_pct must be between 0 and 1")
        return v

    @field_validator("reward_risk")
    @classmethod
    def _check_reward_risk(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("reward_risk must be positive")
        return v

    @field_validator("max_pool_months")
    @classmethod
    def _check_max_pool(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("max_pool_months must be positive")
        return v

    @field_validator("lookback_days")
    @classmethod
    def _check_lookback(cls, v: int) -> int:
        if v < 20:
            raise ValueError("lookback_days must be at least 20")
        return v

    def normalized(self) -> BacktestConfig:
        """Return self (validators already ran). Retained for call-site compatibility."""
        return self

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class StrategySummary(BaseModel):
    """In-memory summary of a single backtest run. Written to ``strategy_runs.csv``
    (along with :class:`StrategyRun` augmentations like ``open_position_count``)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: str
    strategy_name: str
    weighting: str
    entry_rule: str
    rebalance: str
    stop_loss_pct: float
    reward_risk: float
    max_pool_months: int
    target_hit_multiplier: float
    lookback_days: int
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


# ---------------------------------------------------------------------------
# Table row models — consumed by warehouse.{read_table,write_table} via TABLE_MODELS.
# Column order here MUST match the CSV column order on disk (enforced by the
# schema-drift roundtrip test in ``tests/test_schema_roundtrip.py``).
# ---------------------------------------------------------------------------


class DailyPrice(BaseModel):
    """Row schema for ``data/warehouse/daily_prices.csv``."""

    model_config = ConfigDict(extra="forbid")

    # Phase 2b bumps close.nan_policy from "drop" → "forward_fill_then_flag"
    # (per .omc/plans/consensus-full-overhaul.md). The semantic shift is
    # guarded by scripts/check_schema_compat.py and companion sidecar
    # docs/schemas/daily_prices.v2.schema.json. Other columns stay on "drop".
    semantic_version: ClassVar[str] = "1.0"
    column_nan_policy: ClassVar[dict[str, str]] = {
        "close": "forward_fill_then_flag",
        "open": "drop",
        "high": "drop",
        "low": "drop",
        "volume": "drop",
    }

    date: str
    symbol: str
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    volume: float | None = None
    source_currency: str | None = None
    display_currency: str | None = None
    krw_per_unit: float | None = None


class ReportRow(BaseModel):
    """Row schema for ``data/warehouse/reports.csv``."""

    model_config = ConfigDict(extra="forbid")

    semantic_version: ClassVar[str] = "1.0"
    column_nan_policy: ClassVar[dict[str, str]] = {}

    report_id: str
    page: int | None = None
    ordinal: int | None = None
    publication_date: str
    title: str
    company: str
    ticker: str
    exchange: str
    symbol: str
    pdf_filename: str | None = None
    pdf_url: str | None = None
    report_current_price: float | None = None
    bear_target: float | None = None
    base_target: float | None = None
    bull_target: float | None = None
    target_price_local: float | None = None
    target_price: float | None = None
    target_currency: str | None = None
    price_currency: str | None = None
    display_currency: str | None = None
    markdown_filename: str | None = None
    report_current_price_krw: float | None = None
    bear_target_krw: float | None = None
    base_target_krw: float | None = None
    bull_target_krw: float | None = None
    target_price_krw: float | None = None


class ExecutionEvent(BaseModel):
    """Row schema for ``data/warehouse/execution_events.csv``.

    Phase 2 adds `signal_date`, `decision_price`, `fill_price`, `fill_rule`
    (additive per Principle 6 — no v2 sidecar needed)."""

    model_config = ConfigDict(extra="forbid")

    semantic_version: ClassVar[str] = "1.0"
    column_nan_policy: ClassVar[dict[str, str]] = {}

    run_id: str
    date: str
    symbol: str
    company: str | None = None
    report_id: str | None = None
    event_type: str
    reason: str | None = None
    price: float | None = None
    weight: float | None = None
    entry_date: str | None = None
    entry_price: float | None = None
    target_price: float | None = None
    gross_return: float | None = None
    realized_return: float | None = None
    holding_days: float | None = None
    # Phase 2a lookahead-safe columns (additive per Principle 6):
    # * signal_date      — t-1 (or last observation before the trading day)
    # * decision_price   — price observed at signal_date used to gate the trade
    # * fill_price       — price at execution (next-open by default)
    # * fill_rule        — "open" | "close_fallback" | "same_day_close"
    signal_date: str | None = None
    decision_price: float | None = None
    fill_price: float | None = None
    fill_rule: str | None = None


class StrategyRun(BaseModel):
    """Row schema for ``data/warehouse/strategy_runs.csv``.

    Phase 2 will introduce ``{primary_objective}_in_sample`` /
    ``_oos_tail`` columns (additive; kept through 2026-Q4 per ADR)."""

    model_config = ConfigDict(extra="forbid")

    semantic_version: ClassVar[str] = "1.0"
    column_nan_policy: ClassVar[dict[str, str]] = {}

    run_id: str
    strategy_name: str
    weighting: str
    entry_rule: str
    rebalance: str
    stop_loss_pct: float
    reward_risk: float
    max_pool_months: int
    target_hit_multiplier: float
    lookback_days: int
    final_wealth: float
    total_return: float
    cagr: float | None = None
    annualized_volatility: float | None = None
    sharpe: float | None = None
    sortino: float | None = None
    max_drawdown: float
    calmar: float | None = None
    realized_return: float
    live_return: float
    exposure_ratio: float
    average_positions: float
    max_positions: int
    turnover_events: int
    trade_count: int
    win_rate: float | None = None
    target_hit_rate: float | None = None
    stop_loss_hit_rate: float | None = None
    average_holding_days: float | None = None
    objective: float
    open_position_count: int = 0
    status: str
    # Phase 2b additive columns (3-segment OOS-tail diagnostics — see
    # docs/decisions/phase-2-objective.md for the primary_objective contract).
    # A true per-fold walk-forward backtest replay is a future follow-up.
    # All are optional because existing rows written pre-Phase-2b do not carry
    # them; validators accept None and downstream consumers should treat
    # missing values as "not computed for this run".
    sortino_in_sample: float | None = None
    sortino_oos_tail: float | None = None
    sharpe_oos_tail: float | None = None
    max_drawdown_oos_tail: float | None = None
    fold_count: int | None = None


# Registry consumed by warehouse.write_table / read_table + scripts/export_schemas.py.
# Principle 2: every table whose write must be typed is listed here.
TABLE_MODELS: dict[str, type[BaseModel]] = {
    "daily_prices": DailyPrice,
    "reports": ReportRow,
    "execution_events": ExecutionEvent,
    "strategy_runs": StrategyRun,
}

# Pandas must read identifier-like string columns as text before Pydantic sees
# them. Without these hints, values such as KRX ticker "000999" can be inferred
# as integer 999, permanently losing leading zeros before validation.
TABLE_DTYPES: dict[str, dict[str, str]] = {
    "daily_prices": {
        "date": "str",
        "symbol": "str",
        "source_currency": "str",
        "display_currency": "str",
    },
    "reports": {
        "report_id": "str",
        "publication_date": "str",
        "title": "str",
        "company": "str",
        "ticker": "str",
        "exchange": "str",
        "symbol": "str",
        "pdf_filename": "str",
        "pdf_url": "str",
        "target_currency": "str",
        "price_currency": "str",
        "display_currency": "str",
        "markdown_filename": "str",
    },
    "execution_events": {
        "run_id": "str",
        "date": "str",
        "symbol": "str",
        "company": "str",
        "report_id": "str",
        "event_type": "str",
        "reason": "str",
        "entry_date": "str",
        "signal_date": "str",
        "fill_rule": "str",
    },
    "strategy_runs": {
        "run_id": "str",
        "strategy_name": "str",
        "weighting": "str",
        "entry_rule": "str",
        "rebalance": "str",
        "status": "str",
    },
}


def dataclass_rows(items: list[BaseModel]) -> list[dict[str, Any]]:
    """Back-compat helper. Kept under the legacy name so call sites in
    ``snusmic_pipeline.cli`` keep working; internally dispatches to
    ``model_dump(mode='json')``."""
    return [item.model_dump(mode="json") for item in items]
