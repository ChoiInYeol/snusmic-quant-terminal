"""Objective scoring for local strategy search."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ObjectiveWeights(BaseModel):
    """Weights from the approved plan."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    max_drawdown: float = Field(default=0.75, ge=0)
    annual_turnover_penalty: float = Field(default=0.10, ge=0)
    concentration_penalty: float = Field(default=0.10, ge=0)


def score_metrics(
    *,
    money_weighted_return: float,
    max_drawdown: float,
    annual_turnover_penalty: float,
    concentration_penalty: float,
    weights: ObjectiveWeights | None = None,
) -> float:
    """Return the scalar objective used to rank strategy trials."""
    w = weights or ObjectiveWeights()
    return (
        money_weighted_return
        - w.max_drawdown * max_drawdown
        - w.annual_turnover_penalty * annual_turnover_penalty
        - w.concentration_penalty * concentration_penalty
    )
