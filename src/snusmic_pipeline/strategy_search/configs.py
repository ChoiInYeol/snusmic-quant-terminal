"""Config contracts for local-only strategy search."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Rebalance = Literal["monthly", "quarterly"]
Weighting = Literal["equal", "target_upside", "inverse_volatility", "capped_target_upside"]
UniverseFilter = Literal["all", "domestic", "overseas"]


class _StrictModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", validate_assignment=True)


class ParametricSmicFollowerConfig(_StrictModel):
    """Searchable first strategy family derived from SMIC Follower v2."""

    target_hit_multiplier: float = Field(default=1.0, ge=0.7, le=1.2)
    min_target_upside_at_pub: float = Field(default=0.05, ge=0.05, le=1.5)
    max_target_upside_at_pub: float = Field(default=5.0, ge=0.2, le=5.0)
    max_report_age_days: int = Field(default=730, ge=90, le=1500)
    time_loss_days: int = Field(default=365, ge=60, le=1000)
    stop_loss_pct: float = Field(default=0.20, ge=0.05, le=0.50)
    take_profit_pct: float = Field(default=1.0, ge=0.05, le=3.0)
    rebalance: Rebalance = "monthly"
    max_positions: int = Field(default=30, ge=5, le=80)
    weighting: Weighting = "equal"
    universe: UniverseFilter = "all"
    exclude_missing_confidence_rows: bool = False
    require_publication_price: bool = True

    @model_validator(mode="after")
    def _check_ranges(self) -> ParametricSmicFollowerConfig:
        if self.max_target_upside_at_pub < self.min_target_upside_at_pub:
            raise ValueError("max_target_upside_at_pub must be >= min_target_upside_at_pub")
        return self


class SearchSpace(_StrictModel):
    """Documented search bounds for scripts and tests."""

    seed: int = 42
    trials: int = Field(default=20, ge=1)
    study_name: str = "smic-follower-v1"
