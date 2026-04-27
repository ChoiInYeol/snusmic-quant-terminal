"""Account-level persona simulation.

The canonical (and only) simulation surface in this repo. Simulates a real
Korean brokerage: KRW cash ledger, integer-share holdings, fees and sell-side
tax, and a step-up monthly contribution.

See ``docs/decisions/persona-simulation.md`` for the contract.
"""

from .contracts import (
    AllWeatherConfig,
    BenchmarkAsset,
    BrokerageFees,
    CurrentHolding,
    EquityPoint,
    MonthlyHolding,
    PersonaConfig,
    PersonaName,
    PersonaSummary,
    PositionEpisode,
    ProphetConfig,
    ReportPerformance,
    ReportStats,
    SavingsPlan,
    SimulationConfig,
    SimulationResult,
    SmicFollowerConfig,
    SmicFollowerV2Config,
    SymbolStat,
    Trade,
    WeakProphetConfig,
)

__all__ = [
    "AllWeatherConfig",
    "BenchmarkAsset",
    "BrokerageFees",
    "CurrentHolding",
    "EquityPoint",
    "MonthlyHolding",
    "PersonaConfig",
    "PersonaName",
    "PersonaSummary",
    "PositionEpisode",
    "ProphetConfig",
    "ReportPerformance",
    "ReportStats",
    "SavingsPlan",
    "SimulationConfig",
    "SimulationResult",
    "SmicFollowerConfig",
    "SmicFollowerV2Config",
    "SymbolStat",
    "Trade",
    "WeakProphetConfig",
]
