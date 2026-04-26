"""Single source of truth for the persona simulation.

Every contract that crosses a module boundary in :mod:`snusmic_pipeline.sim`
is a frozen Pydantic v2 model with ``extra='forbid'``. This guarantees:

* missing or extra fields raise immediately at the boundary,
* a config hashed with ``model_dump_json(sort_keys=True)`` is reproducible,
* downstream consumers (engine, viz, JSON export) never disagree on shape.

The runner reads ``SimulationConfig`` and never relies on globals — to add a
new knob, extend the relevant config model. See ``docs/decisions/persona-simulation.md``
for the methodology.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

# ---------------------------------------------------------------------------
# Frozen-config base.
# ``frozen=True``  → immutable after construction (run-id stability).
# ``extra='forbid'`` → unknown keys raise (SSOT enforcement).
# ``validate_assignment=True`` → catches mutation attempts.
# ---------------------------------------------------------------------------


class _FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", validate_assignment=True)


# ---------------------------------------------------------------------------
# Money / fee primitives.
# ---------------------------------------------------------------------------


class SavingsPlan(_FrozenModel):
    """User's savings ladder.

    The plan starts with ``initial_capital_krw`` on day 0, then deposits
    ``monthly_contribution_krw`` on the first trading day of every later
    month. The contribution steps up by ``escalation_step_krw`` every
    ``escalation_period_years`` years (so ``2y → +500k`` makes month-25's
    deposit 1.5M, month-49's deposit 2.0M, etc.)."""

    initial_capital_krw: Annotated[float, Field(ge=0)] = 10_000_000.0
    monthly_contribution_krw: Annotated[float, Field(ge=0)] = 1_000_000.0
    escalation_step_krw: Annotated[float, Field(ge=0)] = 500_000.0
    escalation_period_years: Annotated[int, Field(ge=1, le=10)] = 2
    max_escalations: Annotated[int, Field(ge=0, le=20)] = 10


class BrokerageFees(_FrozenModel):
    """Korean retail brokerage costs, in basis points (bps = 1/10000)."""

    commission_bps: Annotated[float, Field(ge=0, le=200)] = 1.5
    sell_tax_bps: Annotated[float, Field(ge=0, le=200)] = 18.0
    slippage_bps: Annotated[float, Field(ge=0, le=200)] = 5.0


# ---------------------------------------------------------------------------
# Benchmark (all-weather) asset spec.
# ---------------------------------------------------------------------------


class BenchmarkAsset(_FrozenModel):
    """One slot of the all-weather basket.

    ``symbol`` is a yfinance ticker (``GLD``, ``QQQ``, ``SPY``, ``069500.KS``).
    ``weight`` must be in (0, 1] and the sum across all assets in an
    :class:`AllWeatherConfig` must equal 1.0 within 1e-6 (validated below).
    """

    name: str
    symbol: str
    weight: Annotated[float, Field(gt=0.0, le=1.0)]


class AllWeatherConfig(_FrozenModel):
    """Buy-and-hold all-weather portfolio with monthly rebalance."""

    persona_name: Literal["all_weather"] = "all_weather"
    assets: tuple[BenchmarkAsset, ...] = (
        BenchmarkAsset(name="Gold", symbol="GLD", weight=0.25),
        BenchmarkAsset(name="NASDAQ-100", symbol="QQQ", weight=0.25),
        BenchmarkAsset(name="S&P 500", symbol="SPY", weight=0.25),
        BenchmarkAsset(name="KOSPI 200", symbol="069500.KS", weight=0.25),
    )
    rebalance: Literal["monthly", "quarterly", "yearly"] = "monthly"

    @model_validator(mode="after")
    def _check_weights(self) -> AllWeatherConfig:
        total = sum(asset.weight for asset in self.assets)
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"AllWeather weights must sum to 1.0; got {total:.6f}")
        if len({a.symbol for a in self.assets}) != len(self.assets):
            raise ValueError("AllWeather asset symbols must be unique")
        return self


# ---------------------------------------------------------------------------
# Persona configs. Each carries its own knobs; a discriminator union via
# ``persona_name`` lets the runner dispatch without isinstance().
# ---------------------------------------------------------------------------


class _PersonaBase(_FrozenModel):
    label: str  # human-readable label for legends / tables


class ProphetConfig(_PersonaBase):
    """Full-lookahead oracle. Picks the post-publication realized winner.

    ``dominance_threshold`` controls when the prophet concentrates 100% on
    the top symbol vs. spreading across a basket: if the top symbol's
    realized peak return is ``>= dominance_threshold × runner-up`` it goes
    all-in, otherwise weights are proportional to realized return capped at
    ``max_weight``."""

    persona_name: Literal["oracle"] = "oracle"
    label: str = "Prophet"
    dominance_threshold: Annotated[float, Field(ge=1.0, le=10.0)] = 1.5
    max_weight: Annotated[float, Field(gt=0.0, le=1.0)] = 1.0
    rebalance: Literal["monthly", "quarterly"] = "monthly"


class WeakProphetConfig(_PersonaBase):
    """6-month look-ahead max-Sharpe."""

    persona_name: Literal["weak_oracle"] = "weak_oracle"
    label: str = "Weak Prophet (6M look-ahead)"
    lookahead_months: Annotated[int, Field(ge=1, le=24)] = 6
    risk_free_rate: Annotated[float, Field(ge=0.0, le=0.20)] = 0.03
    max_weight: Annotated[float, Field(gt=0.0, le=1.0)] = 0.40
    rebalance: Literal["monthly", "quarterly"] = "monthly"
    min_history_days: Annotated[int, Field(ge=20, le=252)] = 60


class SmicFollowerConfig(_PersonaBase):
    """Pure 1/N true-believer: never sells at a loss."""

    persona_name: Literal["smic_follower"] = "smic_follower"
    label: str = "SMIC Follower (1/N)"
    target_hit_multiplier: Annotated[float, Field(gt=0.0, le=2.0)] = 1.0
    rebalance: Literal["monthly", "quarterly"] = "monthly"


class SmicFollowerV2Config(_PersonaBase):
    """1/N follower with three stop-loss escape hatches."""

    persona_name: Literal["smic_follower_v2"] = "smic_follower_v2"
    label: str = "SMIC Follower v2 (with stop-loss)"
    target_hit_multiplier: Annotated[float, Field(gt=0.0, le=2.0)] = 1.0
    rebalance: Literal["monthly", "quarterly"] = "monthly"

    # Stop-loss rule (a): held this many days AND still at unrealized loss.
    time_loss_days: Annotated[int, Field(ge=30, le=2000)] = 365

    # Stop-loss rule (b): an averaged-down position with unrealized return below this.
    averaged_down_stop_pct: Annotated[float, Field(gt=0.0, lt=1.0)] = 0.20

    # Stop-loss rule (c): days past report publication after which we give up.
    report_age_stop_days: Annotated[int, Field(ge=30, le=3650)] = 730


PersonaConfig = (
    ProphetConfig | WeakProphetConfig | SmicFollowerConfig | SmicFollowerV2Config | AllWeatherConfig
)

PersonaName = Literal[
    "oracle",
    "weak_oracle",
    "smic_follower",
    "smic_follower_v2",
    "all_weather",
]


# ---------------------------------------------------------------------------
# Root simulation config.
# ---------------------------------------------------------------------------


class SimulationConfig(_FrozenModel):
    """Root config consumed by :func:`snusmic_pipeline.sim.runner.run_simulation`."""

    start_date: date
    end_date: date
    savings_plan: SavingsPlan = SavingsPlan()
    fees: BrokerageFees = BrokerageFees()
    personas: tuple[PersonaConfig, ...] = (
        ProphetConfig(),
        WeakProphetConfig(),
        SmicFollowerConfig(),
        SmicFollowerV2Config(),
        AllWeatherConfig(),
    )
    seed: int = 42  # used only for tie-breaking; the engine itself is deterministic.

    @model_validator(mode="after")
    def _check_dates(self) -> SimulationConfig:
        if self.end_date <= self.start_date:
            raise ValueError(f"end_date {self.end_date} must be after start_date {self.start_date}")
        names = [p.persona_name for p in self.personas]
        if len(set(names)) != len(names):
            raise ValueError(f"persona_name must be unique; got {names}")
        return self


# ---------------------------------------------------------------------------
# Per-event records.
# ---------------------------------------------------------------------------


TradeSide = Literal["buy", "sell"]
TradeReason = Literal[
    "deposit_buy",
    "rebalance_buy",
    "rebalance_sell",
    "target_hit",
    "stop_loss_time",
    "stop_loss_average_down",
    "stop_loss_report_age",
    "end_of_sim",
]


class Trade(_FrozenModel):
    """One executed fill. Quantity is integer shares; cash effect is signed."""

    persona: str
    date: date
    symbol: str
    side: TradeSide
    qty: Annotated[int, Field(ge=0)]
    fill_price_krw: Annotated[float, Field(gt=0.0)]
    gross_krw: float  # qty × fill_price (no sign)
    commission_krw: Annotated[float, Field(ge=0)]
    tax_krw: Annotated[float, Field(ge=0)]
    cash_after_krw: float
    reason: TradeReason
    report_id: str | None = None


class EquityPoint(_FrozenModel):
    """Daily mark-to-market snapshot for one persona."""

    persona: str
    date: date
    cash_krw: float
    holdings_value_krw: float
    equity_krw: float
    contributed_capital_krw: float
    net_profit_krw: float
    open_positions: int


class PositionEpisode(_FrozenModel):
    """One contiguous holding period for a (persona, symbol) pair.

    An "episode" opens when ``qty`` goes from 0 → >0 and closes when ``qty``
    returns to 0. A partial sell that does NOT fully close the position
    stays inside the same episode. Symbols that the persona buys, sells
    fully, then buys again will produce two distinct episodes.

    ``status`` is ``"closed"`` once ``close_date`` is set, otherwise
    ``"open"`` (still held at the end of the simulation).
    """

    persona: str
    symbol: str
    company: str | None
    open_date: date
    close_date: date | None
    holding_days: int
    buy_fills: int
    sell_fills: int
    total_qty_bought: int
    total_qty_sold: int
    avg_entry_price_krw: float
    avg_exit_price_krw: float | None
    realized_pnl_krw: float
    unrealized_pnl_krw: float | None  # only when status == "open"
    last_close_krw: float | None
    status: Literal["open", "closed"]
    exit_reasons: tuple[str, ...]


class CurrentHolding(_FrozenModel):
    """A still-open position at the end of the simulation."""

    persona: str
    symbol: str
    company: str | None
    qty: Annotated[int, Field(ge=1)]
    avg_cost_krw: float
    last_close_krw: float | None
    market_value_krw: float
    unrealized_pnl_krw: float
    unrealized_return: float | None  # last_close / avg_cost - 1
    holding_days: int
    first_buy_date: date


class ReportPerformance(_FrozenModel):
    """One SMIC report's realised outcome between publication and ``as_of_date``.

    Persona-agnostic: this is just "how did the price move after the report
    came out". Used by :class:`ReportStats` to aggregate target-hit rates,
    top winners/losers, and target-gap analysis.
    """

    report_id: str
    symbol: str
    company: str
    publication_date: date
    entry_price_krw: float | None  # first close on/after pub_date
    target_price_krw: float | None
    target_upside_at_pub: float | None  # target / entry − 1
    target_hit: bool
    target_hit_date: date | None
    days_to_target: int | None  # None when not hit
    last_close_krw: float | None
    last_close_date: date | None
    current_return: float | None  # last_close / entry − 1
    peak_return: float | None
    trough_return: float | None
    target_gap_pct: float | None  # (last_close − target) / target


class ReportStats(_FrozenModel):
    """Aggregate statistics across the entire SMIC report universe."""

    total_reports: int
    reports_with_prices: int
    target_hit_count: int
    target_hit_rate: float  # 0.0..1.0
    avg_days_to_target: float | None  # only over hit reports
    median_days_to_target: float | None
    avg_current_return: float | None  # mean across reports with prices
    median_current_return: float | None
    avg_target_upside_at_pub: float | None  # implied promised return at pub
    avg_target_gap_pct: float | None  # mean (last − target)/target across not-hit reports
    top_winners: tuple[ReportPerformance, ...]
    top_losers: tuple[ReportPerformance, ...]
    biggest_target_gaps_below: tuple[ReportPerformance, ...]  # furthest below target
    biggest_target_overshoots: tuple[ReportPerformance, ...]  # blew past target the most
    fastest_target_hits: tuple[ReportPerformance, ...]
    slowest_target_hits: tuple[ReportPerformance, ...]
    most_aggressive_targets: tuple[ReportPerformance, ...]  # highest target_upside_at_pub


class MonthlyHolding(_FrozenModel):
    """Month-end snapshot of one (persona, symbol) pair.

    Used to render the portfolio-evolution stacked-area chart and to
    produce the monthly_holdings.csv long-form table.
    """

    persona: str
    month_end: date
    symbol: str
    company: str
    qty: Annotated[int, Field(ge=1)]
    market_value_krw: float
    weight_in_portfolio: float


class SymbolStat(_FrozenModel):
    """Aggregated lifetime stats for a (persona, symbol) pair across all episodes."""

    persona: str
    symbol: str
    company: str | None
    episodes: int
    total_buy_fills: int
    total_sell_fills: int
    total_holding_days: int  # sum across all episodes
    total_realized_pnl_krw: float
    is_currently_held: bool
    current_qty: int
    current_unrealized_pnl_krw: float | None


class PersonaSummary(_FrozenModel):
    """Top-line stats for a persona at the end of the simulation."""

    persona: str
    label: str
    initial_capital_krw: float
    total_contributed_krw: float
    final_equity_krw: float
    final_cash_krw: float
    final_holdings_value_krw: float
    net_profit_krw: float
    money_weighted_return: float  # IRR on the cash-flow stream
    time_weighted_return: float | None  # geometric link of daily returns
    cagr: float | None
    max_drawdown: float
    realized_pnl_krw: float
    trade_count: int
    open_positions: int


class SimulationResult(_FrozenModel):
    """Output bundle written by :func:`runner.run_simulation`."""

    config: SimulationConfig
    summaries: tuple[PersonaSummary, ...]
    equity_points: tuple[EquityPoint, ...]
    trades: tuple[Trade, ...]
    position_episodes: tuple[PositionEpisode, ...] = ()
    current_holdings: tuple[CurrentHolding, ...] = ()
    symbol_stats: tuple[SymbolStat, ...] = ()
    monthly_holdings: tuple[MonthlyHolding, ...] = ()
    report_performance: tuple[ReportPerformance, ...] = ()
    report_stats: ReportStats | None = None


# Discriminator helper so the runner can dispatch by ``persona_name``.
PERSONA_REGISTRY_KEYS: tuple[str, ...] = (
    "oracle",
    "weak_oracle",
    "smic_follower",
    "smic_follower_v2",
    "all_weather",
)
