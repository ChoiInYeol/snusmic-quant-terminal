"""Top-level simulation runner.

Reads :class:`SimulationConfig` + the warehouse on disk and produces a
:class:`SimulationResult` covering every requested persona. Network I/O is
limited to the All-Weather benchmark loader (which caches on disk).
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from .contracts import (
    AllWeatherConfig,
    MonthlyHolding,
    PersonaConfig,
    ProphetConfig,
    SimulationConfig,
    SimulationResult,
    SmicFollowerConfig,
    SmicFollowerV2Config,
    WeakProphetConfig,
)
from .holdings import (
    compute_current_holdings,
    compute_monthly_holdings,
    compute_position_episodes,
    compute_symbol_stats,
)
from .market import PriceBoard, load_benchmark_dividends, load_benchmark_prices
from .personas import (
    PersonaRunOutput,
    simulate_all_weather,
    simulate_prophet,
    simulate_smic_follower,
    simulate_smic_follower_v2,
    simulate_weak_prophet,
)
from .personas.base import DividendIndex
from .report_stats import aggregate_report_stats, compute_report_performance
from .savings import build_cash_flow_schedule
from .warehouse import read_table


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
    benchmark_dividends_df: pd.DataFrame | None = None
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
        benchmark_dividends_df = load_benchmark_dividends(
            warehouse_dir,
            symbols_needed,
            config.start_date,
            config.end_date,
            refresh=refresh_benchmark,
        )

    snusmic_dividends = _build_dividend_index(read_table(warehouse_dir, "dividends"))
    benchmark_dividends = _build_dividend_index(benchmark_dividends_df)

    outputs: list[PersonaRunOutput] = []
    for persona in config.personas:
        outputs.append(
            _dispatch(
                persona,
                config,
                board,
                benchmark_board,
                reports,
                cashflows,
                trading_dates,
                snusmic_dividends,
                benchmark_dividends,
            )
        )

    summaries = tuple(o.summary for o in outputs)
    equity_points = tuple(p for o in outputs for p in o.equity_points)
    trades = tuple(t for o in outputs for t in o.account.trades)

    # Holdings reports — single source of truth is the trade ledger, which is
    # how a brokerage app reconstructs past positions from statements. Each
    # persona's episodes are marked against its own price board (SNUSMIC
    # universe for the four research personas; All-Weather basket for the
    # benchmark) so the unrealized PnL on still-open positions is correct.
    company_by_symbol = _company_lookup(reports)
    last_day = trading_dates[-1]
    episodes = list(
        compute_position_episodes(
            (t for t in trades if t.persona != "all_weather"),
            board,
            last_day,
            company_by_symbol,
        )
    )
    if benchmark_board is not None:
        episodes.extend(
            compute_position_episodes(
                (t for t in trades if t.persona == "all_weather"),
                benchmark_board,
                last_day,
                _ALL_WEATHER_LABELS,
            )
        )
    episodes_tuple = tuple(episodes)
    current_holdings = tuple(compute_current_holdings(episodes_tuple, board=None, end_date=last_day))
    symbol_stats = tuple(compute_symbol_stats(episodes_tuple))

    # Month-end portfolio composition. Each persona is marked against its
    # own price board; All-Weather goes to the benchmark board.
    boards_by_persona: dict[str, PriceBoard] = {p.persona_name: board for p in config.personas}
    if benchmark_board is not None and not benchmark_board.is_empty:
        boards_by_persona["all_weather"] = benchmark_board
    monthly_df = compute_monthly_holdings(trades, boards_by_persona, last_day, company_by_symbol)
    monthly_holdings = (
        tuple(MonthlyHolding(**row) for row in monthly_df.to_dict("records")) if not monthly_df.empty else ()
    )

    # Persona-agnostic SMIC report statistics.
    report_perf = tuple(compute_report_performance(reports, board, last_day))
    report_stats_obj = aggregate_report_stats(report_perf) if report_perf else None

    return SimulationResult(
        config=config,
        summaries=summaries,
        equity_points=equity_points,
        trades=trades,
        position_episodes=episodes_tuple,
        current_holdings=current_holdings,
        symbol_stats=symbol_stats,
        monthly_holdings=monthly_holdings,
        report_performance=report_perf,
        report_stats=report_stats_obj,
    )


_ALL_WEATHER_LABELS: dict[str, str] = {
    "GLD": "Gold (GLD)",
    "QQQ": "NASDAQ-100 (QQQ)",
    "SPY": "S&P 500 (SPY)",
    "069500.KS": "KOSPI 200 (069500.KS)",
}


def _company_lookup(reports: pd.DataFrame) -> dict[str, str]:
    if reports.empty or "symbol" not in reports.columns or "company" not in reports.columns:
        return {}
    out: dict[str, str] = {}
    for record in reports.to_dict("records"):
        symbol = str(record.get("symbol") or "").strip()
        company = str(record.get("company") or "").strip()
        if symbol and company and symbol not in out:
            out[symbol] = company
    return out


def _dispatch(
    persona: PersonaConfig,
    config: SimulationConfig,
    board: PriceBoard,
    benchmark_board: PriceBoard | None,
    reports: pd.DataFrame,
    cashflows,
    trading_dates: list[date],
    snusmic_dividends: DividendIndex,
    benchmark_dividends: DividendIndex,
) -> PersonaRunOutput:
    if isinstance(persona, ProphetConfig):
        return simulate_prophet(
            persona, config.savings_plan, config.fees, board, reports, cashflows, trading_dates,
            dividends_by_date=snusmic_dividends,
        )
    if isinstance(persona, WeakProphetConfig):
        return simulate_weak_prophet(
            persona, config.savings_plan, config.fees, board, reports, cashflows, trading_dates,
            dividends_by_date=snusmic_dividends,
        )
    if isinstance(persona, SmicFollowerConfig):
        return simulate_smic_follower(
            persona, config.savings_plan, config.fees, board, reports, cashflows, trading_dates,
            dividends_by_date=snusmic_dividends,
        )
    if isinstance(persona, SmicFollowerV2Config):
        return simulate_smic_follower_v2(
            persona, config.savings_plan, config.fees, board, reports, cashflows, trading_dates,
            dividends_by_date=snusmic_dividends,
        )
    if isinstance(persona, AllWeatherConfig):
        if benchmark_board is None or benchmark_board.is_empty:
            raise RuntimeError("All-Weather persona requested but benchmark prices unavailable.")
        return simulate_all_weather(
            persona, config.savings_plan, config.fees, benchmark_board, cashflows, trading_dates,
            dividends_by_date=benchmark_dividends,
        )
    raise TypeError(f"unknown persona config: {type(persona).__name__}")


def _build_dividend_index(df: pd.DataFrame | None) -> DividendIndex:
    """Pivot the warehouse dividend table into ``ex_date → [(symbol, dps_krw)]``.

    Returns an empty dict (not ``None``) when the dataframe is missing or
    empty, so the persona helper's no-op path stays cheap and the runner
    can pass the result unconditionally.
    """
    if df is None or df.empty or "dps_krw" not in df.columns:
        return {}
    out: DividendIndex = {}
    sub = df.dropna(subset=["dps_krw"])
    sub = sub[sub["dps_krw"] > 0]
    for record in sub.to_dict("records"):
        try:
            ex_date = pd.to_datetime(record["date"]).date()
        except (TypeError, ValueError):
            continue
        out.setdefault(ex_date, []).append((str(record["symbol"]), float(record["dps_krw"])))
    return out


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
