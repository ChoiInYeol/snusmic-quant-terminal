"""Deterministic local strategy evaluator and fallback random search."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any

import pandas as pd
from pydantic import BaseModel, ConfigDict

from .configs import ParametricSmicFollowerConfig
from .objective import score_metrics


class StrategyMetrics(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    score: float
    final_equity_krw: float
    net_profit_krw: float
    money_weighted_return: float
    cagr: float | None = None
    max_drawdown: float
    trade_count: int
    turnover: float
    average_holding_days: float | None = None
    win_rate: float | None = None
    hit_rate: float | None = None
    max_single_position_weight: float
    open_positions: int
    excess_return_vs_smic_follower: float | None = None
    excess_return_vs_smic_follower_v2: float | None = None
    excess_return_vs_all_weather: float | None = None


@dataclass(frozen=True)
class BaselineReturns:
    smic_follower: float | None = None
    smic_follower_v2: float | None = None
    all_weather: float | None = None


def baseline_returns_from_summary(summary: pd.DataFrame | None) -> BaselineReturns:
    if summary is None or summary.empty or "persona" not in summary.columns:
        return BaselineReturns()

    def _get(persona: str) -> float | None:
        rows = summary[summary["persona"].astype(str) == persona]
        if rows.empty or "money_weighted_return" not in rows.columns:
            return None
        value = pd.to_numeric(rows.iloc[0]["money_weighted_return"], errors="coerce")
        return None if pd.isna(value) else float(value)

    return BaselineReturns(
        smic_follower=_get("smic_follower"),
        smic_follower_v2=_get("smic_follower_v2"),
        all_weather=_get("all_weather"),
    )


def evaluate_strategy(
    config: ParametricSmicFollowerConfig,
    report_performance: pd.DataFrame,
    *,
    baseline_summary: pd.DataFrame | None = None,
    initial_capital_krw: float = 10_000_000.0,
) -> StrategyMetrics:
    """Evaluate a parametric follower from report-performance artifacts."""
    selected = _select_reports(report_performance, config)
    baselines = baseline_returns_from_summary(baseline_summary)
    if selected.empty:
        return StrategyMetrics(
            score=-1.0,
            final_equity_krw=initial_capital_krw,
            net_profit_krw=0.0,
            money_weighted_return=0.0,
            cagr=0.0,
            max_drawdown=0.0,
            trade_count=0,
            turnover=0.0,
            average_holding_days=None,
            win_rate=None,
            hit_rate=None,
            max_single_position_weight=0.0,
            open_positions=0,
            excess_return_vs_smic_follower=_excess(0.0, baselines.smic_follower),
            excess_return_vs_smic_follower_v2=_excess(0.0, baselines.smic_follower_v2),
            excess_return_vs_all_weather=_excess(0.0, baselines.all_weather),
        )

    returns = _strategy_returns(selected, config)
    weights = _position_weights(selected, config)
    weighted_return = float((returns * weights).sum())
    hit_rate = float(selected["target_hit"].astype(bool).mean()) if "target_hit" in selected else None
    wins = returns > 0
    win_rate = float(wins.mean()) if len(wins) else None
    avg_holding_days = _avg_holding_days(selected)
    max_weight = float(weights.max()) if len(weights) else 0.0
    rebalance_factor = 12 if config.rebalance == "monthly" else 4
    turnover = min(4.0, (len(selected) / max(config.max_positions, 1)) * (rebalance_factor / 12))
    max_drawdown = min(0.95, max(0.0, float((-returns[returns < 0]).mean() if (returns < 0).any() else 0.0)))
    concentration_penalty = max(0.0, max_weight - 0.20)
    annual_turnover_penalty = max(0.0, turnover - 1.0)
    mwr = weighted_return
    score = score_metrics(
        money_weighted_return=mwr,
        max_drawdown=max_drawdown,
        annual_turnover_penalty=annual_turnover_penalty,
        concentration_penalty=concentration_penalty,
    )
    final_equity = initial_capital_krw * (1.0 + mwr)
    return StrategyMetrics(
        score=score,
        final_equity_krw=final_equity,
        net_profit_krw=final_equity - initial_capital_krw,
        money_weighted_return=mwr,
        cagr=mwr,
        max_drawdown=max_drawdown,
        trade_count=int(len(selected) * 2),
        turnover=turnover,
        average_holding_days=avg_holding_days,
        win_rate=win_rate,
        hit_rate=hit_rate,
        max_single_position_weight=max_weight,
        open_positions=min(len(selected), config.max_positions),
        excess_return_vs_smic_follower=_excess(mwr, baselines.smic_follower),
        excess_return_vs_smic_follower_v2=_excess(mwr, baselines.smic_follower_v2),
        excess_return_vs_all_weather=_excess(mwr, baselines.all_weather),
    )


def run_random_search(
    report_performance: pd.DataFrame,
    *,
    baseline_summary: pd.DataFrame | None = None,
    trials: int = 20,
    seed: int = 42,
) -> list[dict[str, Any]]:
    """Run deterministic fallback search without Optuna."""
    rng = random.Random(seed)
    rows: list[dict[str, Any]] = []
    for trial_number in range(trials):
        config = _sample_config(rng)
        metrics = evaluate_strategy(config, report_performance, baseline_summary=baseline_summary)
        rows.append(_trial_row(trial_number, config, metrics, sampler="random-fallback"))
    return sorted(rows, key=lambda row: float(row["score"]), reverse=True)


def _select_reports(frame: pd.DataFrame, config: ParametricSmicFollowerConfig) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    selected = frame.copy()
    if config.require_publication_price and "entry_price_krw" in selected.columns:
        selected = selected[pd.to_numeric(selected["entry_price_krw"], errors="coerce").notna()]
    if "target_upside_at_pub" in selected.columns:
        upside = pd.to_numeric(selected["target_upside_at_pub"], errors="coerce")
        selected = selected[
            (upside >= config.min_target_upside_at_pub) & (upside <= config.max_target_upside_at_pub)
        ]
    if "days_to_target" in selected.columns:
        days = pd.to_numeric(selected["days_to_target"], errors="coerce")
        selected = selected[days.isna() | (days <= config.max_report_age_days)]
    if config.universe != "all" and "symbol" in selected.columns:
        is_domestic = selected["symbol"].astype(str).str.endswith(".KS") | selected["symbol"].astype(
            str
        ).str.endswith(".KQ")
        selected = selected[is_domestic] if config.universe == "domestic" else selected[~is_domestic]
    if config.exclude_missing_confidence_rows:
        selected = selected.dropna(subset=["target_upside_at_pub", "current_return"])
    sort_cols = [col for col in ["publication_date", "report_id"] if col in selected.columns]
    if sort_cols:
        selected = selected.sort_values(sort_cols)
    return selected.head(config.max_positions).reset_index(drop=True)


def _strategy_returns(selected: pd.DataFrame, config: ParametricSmicFollowerConfig) -> pd.Series:
    current = pd.to_numeric(
        selected.get("current_return", pd.Series(0.0, index=selected.index)), errors="coerce"
    ).fillna(0.0)
    upside = pd.to_numeric(
        selected.get("target_upside_at_pub", pd.Series(0.0, index=selected.index)), errors="coerce"
    ).fillna(0.0)
    target_return = (upside * config.target_hit_multiplier).clip(upper=config.take_profit_pct)
    hit = selected.get("target_hit", pd.Series(False, index=selected.index)).astype(bool)
    returns = current.where(~hit, target_return)
    returns = returns.clip(lower=-config.stop_loss_pct, upper=config.take_profit_pct)
    if "days_to_target" in selected.columns:
        days = pd.to_numeric(selected["days_to_target"], errors="coerce")
        stale_loss = days.fillna(config.time_loss_days + 1) >= config.time_loss_days
        returns = returns.where(~(stale_loss & (returns < 0)), returns.clip(lower=-config.stop_loss_pct))
    return returns.astype(float)


def _position_weights(selected: pd.DataFrame, config: ParametricSmicFollowerConfig) -> pd.Series:
    if selected.empty:
        return pd.Series(dtype=float)
    if config.weighting == "equal":
        raw = pd.Series(1.0, index=selected.index)
    elif config.weighting in {"target_upside", "capped_target_upside"}:
        raw = (
            pd.to_numeric(
                selected.get("target_upside_at_pub", pd.Series(1.0, index=selected.index)), errors="coerce"
            )
            .fillna(0.0)
            .clip(lower=0.01)
        )
        if config.weighting == "capped_target_upside":
            raw = raw.clip(upper=1.0)
    else:
        trough = (
            pd.to_numeric(
                selected.get("trough_return", pd.Series(-0.2, index=selected.index)), errors="coerce"
            )
            .abs()
            .fillna(0.2)
        )
        raw = 1.0 / trough.clip(lower=0.05)
    total = float(raw.sum())
    if total <= 0:
        return pd.Series(1.0 / len(selected), index=selected.index)
    return raw / total


def _avg_holding_days(selected: pd.DataFrame) -> float | None:
    if "days_to_target" not in selected.columns:
        return None
    days = pd.to_numeric(selected["days_to_target"], errors="coerce").dropna()
    return None if days.empty else float(days.mean())


def _excess(value: float, baseline: float | None) -> float | None:
    return None if baseline is None else value - baseline


def _sample_config(rng: random.Random) -> ParametricSmicFollowerConfig:
    min_upside = _sample_step(rng, 0.05, 0.60, 0.01)
    max_upside = _sample_step(rng, max(0.20, min_upside), 5.0, 0.01)
    return ParametricSmicFollowerConfig(
        target_hit_multiplier=_sample_step(rng, 0.7, 1.2, 0.01),
        min_target_upside_at_pub=min_upside,
        max_target_upside_at_pub=max_upside,
        max_report_age_days=rng.randint(90, 1500),
        time_loss_days=rng.randint(60, 1000),
        stop_loss_pct=_sample_step(rng, 0.05, 0.50, 0.01),
        take_profit_pct=_sample_step(rng, 0.05, 3.0, 0.01),
        rebalance=rng.choice(["monthly", "quarterly"]),
        max_positions=rng.randint(5, 80),
        weighting=rng.choice(["equal", "target_upside", "inverse_volatility", "capped_target_upside"]),
        universe=rng.choice(["all", "domestic", "overseas"]),
        exclude_missing_confidence_rows=rng.choice([False, True]),
        require_publication_price=rng.choice([False, True]),
    )


def _sample_step(rng: random.Random, low: float, high: float, step: float) -> float:
    """Sample a discrete decimal grid and return values rounded to 2 decimals."""
    units_low = round(low / step)
    units_high = round(high / step)
    return round(rng.randint(units_low, units_high) * step, 2)


def _trial_row(
    trial_number: int, config: ParametricSmicFollowerConfig, metrics: StrategyMetrics, *, sampler: str
) -> dict[str, Any]:
    return {
        "trial_number": trial_number,
        "sampler": sampler,
        "scope": "in-sample",
        **config.model_dump(mode="json"),
        **metrics.model_dump(mode="json"),
    }
