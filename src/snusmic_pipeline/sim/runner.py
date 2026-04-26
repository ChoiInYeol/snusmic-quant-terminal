"""Top-level simulation runner.

Reads :class:`SimulationConfig` + the warehouse on disk and produces a
:class:`SimulationResult` covering every requested persona. Network I/O is
limited to the All-Weather benchmark loader (which caches on disk).
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from ..backtest.warehouse import read_table
from .contracts import (
    AllWeatherConfig,
    PersonaConfig,
    ProphetConfig,
    SimulationConfig,
    SimulationResult,
    SmicFollowerConfig,
    SmicFollowerV2Config,
    WeakProphetConfig,
)
from .market import PriceBoard, load_benchmark_prices
from .personas import (
    PersonaRunOutput,
    simulate_all_weather,
    simulate_prophet,
    simulate_smic_follower,
    simulate_smic_follower_v2,
    simulate_weak_prophet,
)
from .savings import build_cash_flow_schedule


def run_simulation(
    config: SimulationConfig,
    warehouse_dir: Path,
    *,
    refresh_benchmark: bool = False,
) -> SimulationResult:
    """Run every persona in ``config.personas`` and return a result bundle."""
    board = PriceBoard.from_warehouse(warehouse_dir)
    if board.is_empty:
        raise RuntimeError(f"Warehouse {warehouse_dir} has no daily_prices rows; nothing to simulate.")

    trading_dates = board.trading_dates(start=config.start_date, end=config.end_date)
    if not trading_dates:
        raise RuntimeError(
            f"No trading dates in warehouse between {config.start_date} and {config.end_date}."
        )

    cashflows = build_cash_flow_schedule(trading_dates, config.savings_plan)
    reports = read_table(warehouse_dir, "reports")
    reports = _prepare_reports(reports, config.start_date, config.end_date)

    benchmark_board: PriceBoard | None = None
    if any(isinstance(p, AllWeatherConfig) for p in config.personas):
        symbols_needed: set[str] = set()
        for p in config.personas:
            if isinstance(p, AllWeatherConfig):
                symbols_needed.update(a.symbol for a in p.assets)
        benchmark_board = load_benchmark_prices(
            warehouse_dir,
            symbols_needed,
            config.start_date,
            config.end_date,
            refresh=refresh_benchmark,
        )

    outputs: list[PersonaRunOutput] = []
    for persona in config.personas:
        outputs.append(_dispatch(persona, config, board, benchmark_board, reports, cashflows, trading_dates))

    summaries = tuple(o.summary for o in outputs)
    equity_points = tuple(p for o in outputs for p in o.equity_points)
    trades = tuple(t for o in outputs for t in o.account.trades)
    return SimulationResult(
        config=config,
        summaries=summaries,
        equity_points=equity_points,
        trades=trades,
    )


def _dispatch(
    persona: PersonaConfig,
    config: SimulationConfig,
    board: PriceBoard,
    benchmark_board: PriceBoard | None,
    reports: pd.DataFrame,
    cashflows,
    trading_dates: list[date],
) -> PersonaRunOutput:
    if isinstance(persona, ProphetConfig):
        return simulate_prophet(
            persona, config.savings_plan, config.fees, board, reports, cashflows, trading_dates
        )
    if isinstance(persona, WeakProphetConfig):
        return simulate_weak_prophet(
            persona, config.savings_plan, config.fees, board, reports, cashflows, trading_dates
        )
    if isinstance(persona, SmicFollowerConfig):
        return simulate_smic_follower(
            persona, config.savings_plan, config.fees, board, reports, cashflows, trading_dates
        )
    if isinstance(persona, SmicFollowerV2Config):
        return simulate_smic_follower_v2(
            persona, config.savings_plan, config.fees, board, reports, cashflows, trading_dates
        )
    if isinstance(persona, AllWeatherConfig):
        if benchmark_board is None or benchmark_board.is_empty:
            raise RuntimeError("All-Weather persona requested but benchmark prices unavailable.")
        return simulate_all_weather(
            persona, config.savings_plan, config.fees, benchmark_board, cashflows, trading_dates
        )
    raise TypeError(f"unknown persona config: {type(persona).__name__}")


def _prepare_reports(reports: pd.DataFrame, start: date, end: date) -> pd.DataFrame:
    if reports.empty:
        return reports
    frame = reports.copy()
    frame["publication_date"] = pd.to_datetime(frame["publication_date"], errors="coerce")
    frame = frame.dropna(subset=["symbol", "publication_date"])
    frame = frame[frame["symbol"].astype(str) != ""]
    # Drop reports past the sim window — they can't be acted on.
    frame = frame[frame["publication_date"] <= pd.Timestamp(end)]
    # Use the KRW target preferentially.
    if "target_price_krw" in frame.columns:
        frame["target_price"] = frame["target_price_krw"].combine_first(frame.get("target_price"))
    frame = frame.sort_values("publication_date").reset_index(drop=True)
    return frame
