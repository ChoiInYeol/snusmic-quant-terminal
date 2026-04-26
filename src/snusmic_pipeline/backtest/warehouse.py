from __future__ import annotations

import contextlib
import csv
import hashlib
import io
import json
import math
import os
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from pydantic import TypeAdapter

from ..currency import (
    attach_krw_rate,
    convert_value_to_krw,
    currency_for_symbol,
    download_fx_rates,
    normalize_currency,
)
from .engine import run_walk_forward_backtest, stable_run_id
from .schemas import LOOKBACK_WINDOWS, TABLE_DTYPES, TABLE_MODELS, BacktestConfig

WAREHOUSE_TABLES = [
    "reports",
    "fx_rates",
    "daily_prices",
    "signals_daily",
    "candidate_pool_events",
    "execution_events",
    "positions_daily",
    "equity_daily",
    "strategy_runs",
    "optuna_trials",
]


def build_warehouse(data_dir: Path, warehouse_dir: Path) -> dict[str, int]:
    warehouse_dir.mkdir(parents=True, exist_ok=True)
    reports = read_reports(data_dir)
    existing_fx = read_table(warehouse_dir, "fx_rates")
    if not existing_fx.empty:
        reports = apply_report_krw_targets(reports, existing_fx)
    existing_prices = read_table(warehouse_dir, "daily_prices")
    if not existing_prices.empty and not existing_fx.empty:
        existing_prices = apply_daily_price_krw_conversion(existing_prices, reports, existing_fx)
        write_table(warehouse_dir, "daily_prices", existing_prices)
    if not existing_prices.empty:
        reports = fill_report_publication_prices(reports, existing_prices)
    write_table(warehouse_dir, "reports", reports)
    counts = {"reports": len(reports)}
    for table in WAREHOUSE_TABLES:
        path = warehouse_dir / f"{table}.csv"
        if path.exists():
            counts[table] = sum(1 for _ in path.open(encoding="utf-8")) - 1
    sync_duckdb(warehouse_dir)
    return counts


def refresh_price_history(
    data_dir: Path,
    warehouse_dir: Path,
    now: datetime | None = None,
    downloader: Callable[[str, datetime, datetime], pd.DataFrame] | None = None,
    symbols: list[str] | None = None,
    force_full: bool = False,
) -> pd.DataFrame:
    """Refresh ``daily_prices.csv``.

    Phase 3b: per-symbol **incremental** fetch — when the warehouse already
    has bars for a symbol up to ``last_seen``, the downloader is invoked with
    ``start = last_seen + 1 day`` instead of the full publication-window
    start. Symbols whose ``last_seen >= end`` are skipped entirely (zero
    network calls). The merged result re-deduplicates on
    ``(date, symbol)`` so re-running with overlapping windows is idempotent.

    Pass ``force_full=True`` to bypass the incremental path and re-fetch the
    entire window per symbol (used for backfills or when a symbol's history
    needs to be rebuilt from scratch).
    """
    warehouse_dir.mkdir(parents=True, exist_ok=True)
    reports = read_or_build_reports(data_dir, warehouse_dir)
    if reports.empty:
        prices = pd.DataFrame()
        write_table(warehouse_dir, "daily_prices", prices)
        return prices
    now = now or datetime.now(UTC)
    start = pd.to_datetime(reports["publication_date"]).min().to_pydatetime() - timedelta(days=820)
    end = now + timedelta(days=1)
    selected_symbols = symbols or sorted(set(reports["symbol"].dropna().astype(str)))
    downloader = downloader or download_history
    symbol_currencies = {
        str(row["symbol"]): currency_for_symbol(str(row["symbol"]), str(row.get("exchange", "")))
        for row in reports.to_dict("records")
    }
    target_currencies = {
        normalize_currency(str(value))
        for value in reports.get("target_currency", pd.Series(dtype=str)).dropna().astype(str)
    }
    fx_rates = download_fx_rates(set(symbol_currencies.values()) | target_currencies, start, end, downloader)
    write_table(warehouse_dir, "fx_rates", fx_rates)

    # Per-symbol incremental window: fetch only bars after ``last_seen``.
    last_seen: dict[str, datetime] = {}
    existing_full = pd.DataFrame()
    if not force_full:
        existing_full = read_table(warehouse_dir, "daily_prices")
        if not existing_full.empty:
            existing_full = existing_full.copy()
            existing_full["date"] = pd.to_datetime(existing_full["date"])
            for sym, group_max in existing_full.groupby("symbol")["date"].max().items():
                # Pandas may yield the timestamp as Timestamp (not datetime).
                last_seen[str(sym)] = group_max.to_pydatetime()

    frames = []
    for symbol in selected_symbols:
        symbol_start = start
        existing_last = last_seen.get(symbol)
        if existing_last is not None and not force_full:
            candidate = existing_last + timedelta(days=1)
            if candidate.tzinfo is None and start.tzinfo is not None:
                candidate = candidate.replace(tzinfo=start.tzinfo)
            symbol_start = max(start, candidate)
        # Skip entirely when no new bars are possible.
        if symbol_start.date() >= end.date():
            continue
        history = downloader(symbol, symbol_start, end)
        if history.empty:
            continue
        history = history.copy()
        history["symbol"] = symbol
        frames.append(history)
    new_prices = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    # Merge incremental bars with existing on-disk warehouse.
    if symbols:
        # When a caller restricts to a subset, leave other symbols' rows alone.
        existing = read_table(warehouse_dir, "daily_prices") if not force_full else existing_full
        if not existing.empty:
            existing = existing[~existing["symbol"].astype(str).isin(selected_symbols)]
        else:
            existing = pd.DataFrame()
        prices = pd.concat([existing, new_prices], ignore_index=True) if not new_prices.empty else existing
    else:
        # Full-universe refresh: union existing + new_prices, then dedupe.
        if force_full:
            prices = new_prices
        elif not existing_full.empty and not new_prices.empty:
            prices = pd.concat([existing_full, new_prices], ignore_index=True)
        elif not existing_full.empty:
            prices = existing_full
        else:
            prices = new_prices

    if not prices.empty:
        prices["date"] = pd.to_datetime(prices["date"]).dt.date.astype(str)
        prices = apply_daily_price_krw_conversion(prices, reports, fx_rates)
        columns = [
            "date",
            "symbol",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "source_currency",
            "display_currency",
            "krw_per_unit",
        ]
        prices = (
            prices[[column for column in columns if column in prices]]
            .drop_duplicates(["date", "symbol"], keep="last")
            .sort_values(["date", "symbol"])
        )
    write_table(warehouse_dir, "daily_prices", prices)
    reports = apply_report_krw_targets(reports, fx_rates)
    reports = fill_report_publication_prices(reports, prices)
    write_table(warehouse_dir, "reports", reports)
    sync_duckdb(warehouse_dir)
    return prices


def apply_daily_price_krw_conversion(
    prices: pd.DataFrame, reports: pd.DataFrame, fx_rates: pd.DataFrame
) -> pd.DataFrame:
    if prices.empty:
        return prices
    if (
        "display_currency" in prices.columns
        and prices["display_currency"].astype(str).str.upper().eq("KRW").all()
    ):
        return prices
    symbol_meta = (
        reports[["symbol", "exchange"]]
        .dropna(subset=["symbol"])
        .drop_duplicates("symbol", keep="last")
        .set_index("symbol")
        .to_dict("index")
        if not reports.empty and "symbol" in reports
        else {}
    )
    frames = []
    for symbol, group in prices.copy().groupby(prices["symbol"].astype(str), sort=False):
        group = group.copy()
        exchange = str(symbol_meta.get(symbol, {}).get("exchange", ""))
        source_currency = currency_for_symbol(symbol, exchange)
        group["source_currency"] = source_currency
        group["display_currency"] = "KRW" if source_currency else ""
        if normalize_currency(source_currency) == "KRW":
            group["krw_per_unit"] = 1.0
            frames.append(group)
            continue
        rates = attach_krw_rate(group[["date"]].copy(), source_currency, fx_rates)
        if rates["krw_per_unit"].isna().all():
            group["display_currency"] = source_currency
            group["krw_per_unit"] = pd.NA
            frames.append(group)
            continue
        rate = pd.to_numeric(rates["krw_per_unit"], errors="coerce").to_numpy(dtype=float)
        for column in ["open", "high", "low", "close"]:
            if column in group:
                group[column] = pd.to_numeric(group[column], errors="coerce") * rate
        group["krw_per_unit"] = rate
        frames.append(group)
    return pd.concat(frames, ignore_index=True) if frames else prices


def run_default_backtests(
    data_dir: Path,
    warehouse_dir: Path,
    dry_run: bool = False,
    configs: list[BacktestConfig] | None = None,
) -> dict[str, int]:
    # Phase 2c — dry-run path isolation (plan AC #5). When ``dry_run=True`` we
    # redirect every write to ``{warehouse_dir}/_dry_run/`` so real on-disk
    # warehouse / dashboard artifacts are never clobbered by synthetic data.
    # Reports still load from the real ``warehouse_dir`` so the synthetic
    # run uses the actual report universe.
    real_warehouse_dir = warehouse_dir
    if dry_run:
        warehouse_dir = warehouse_dir / "_dry_run"
    warehouse_dir.mkdir(parents=True, exist_ok=True)
    reports = read_or_build_reports(data_dir, real_warehouse_dir)
    prices = read_table(real_warehouse_dir, "daily_prices")
    if dry_run or prices.empty:
        prices = synthetic_price_history(reports)
        write_table(warehouse_dir, "daily_prices", prices)
    configs = configs or default_configs()
    combined: dict[str, list[pd.DataFrame]] = {
        "signals_daily": [],
        "candidate_pool_events": [],
        "execution_events": [],
        "positions_daily": [],
        "equity_daily": [],
        "strategy_runs": [],
    }
    for config in configs:
        run_id = stable_run_id(config)
        result = run_walk_forward_backtest(reports, prices, config, run_id=run_id)
        for table, frame in result.items():
            if table == "signals_daily" and not frame.empty:
                frame = frame.copy()
                frame["run_id"] = run_id
                frame["strategy_name"] = config.name
            combined.setdefault(table, []).append(frame)
    counts: dict[str, int] = {}
    for table, frames in combined.items():
        data = (
            pd.concat([frame for frame in frames if not frame.empty], ignore_index=True)
            if any(not frame.empty for frame in frames)
            else pd.DataFrame()
        )
        if table == "signals_daily" and not data.empty:
            data = data.sort_values("date").groupby(["run_id", "symbol"], as_index=False).tail(1)
        write_table(warehouse_dir, table, data)
        counts[table] = len(data)
    sync_duckdb(warehouse_dir)
    return counts


def optimize_strategies(
    data_dir: Path,
    warehouse_dir: Path,
    trials: int = 25,
    seed: int = 42,
    dry_run: bool = False,
    study_name: str = "snusmic-default",
    storage_path: Path | None = None,
) -> pd.DataFrame:
    """Run an Optuna search over the strategy space.

    Phase 3a: persists the study to a SQLite database so a killed run can be
    **resumed** from where it stopped (see plan AC #3 — "kill after trial 3,
    restart, reach trial 10 without replay"). Concurrency is **single-writer
    per study** by design (plan line 181); cross-study parallelism is the
    grid-search caller's job.
    """
    import optuna

    reports = read_or_build_reports(data_dir, warehouse_dir)
    prices = read_table(warehouse_dir, "daily_prices")
    if dry_run or prices.empty:
        prices = synthetic_price_history(reports)

    storage_path = storage_path or (warehouse_dir / "optuna.sqlite")
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    storage_url = f"sqlite:///{storage_path}"

    # Cache trial-runtime metrics outside Optuna so resumed sessions still
    # rebuild the full optuna_trials.csv from the on-disk study state.
    trial_metrics: dict[int, dict[str, Any]] = {}

    def objective(trial: optuna.Trial) -> float:
        config = BacktestConfig(
            name=f"optuna_{trial.number:03d}",
            weighting=trial.suggest_categorical(
                "weighting", ["1/N", "max_return", "min_var", "sharpe", "sortino", "cvar", "calmar"]
            ),
            entry_rule=trial.suggest_categorical("entry_rule", ["mtt", "target_only", "mtt_target"]),
            mtt_slope_months=trial.suggest_int("mtt_slope_months", 1, 5),
            max_pool_months=trial.suggest_categorical("max_pool_months", [3, 6, 9, 12]),
            target_hit_multiplier=trial.suggest_float("target_hit_multiplier", 1.0, 1.5, step=0.1),
            stop_loss_pct=trial.suggest_categorical("stop_loss_pct", [0.06, 0.08, 0.10, 0.12]),
            reward_risk=trial.suggest_categorical("reward_risk", [2.0, 3.0, 4.0]),
            rebalance=trial.suggest_categorical("rebalance", ["daily", "weekly", "biweekly", "monthly"]),
            lookback_days=trial.suggest_categorical("lookback_days", list(LOOKBACK_WINDOWS.values())),
            min_target_upside=trial.suggest_categorical("min_target_upside", [0.0, 0.10, 0.20]),
        )
        result = run_walk_forward_backtest(reports, prices, config)
        summary = result["strategy_runs"].iloc[0].to_dict()
        trial_metrics[trial.number] = {**config.to_dict(), **summary}
        return float(summary.get("objective") or 0.0)

    study = optuna.create_study(
        study_name=study_name,
        storage=storage_url,
        direction="maximize",
        sampler=optuna.samplers.TPESampler(seed=seed),
        load_if_exists=True,
    )
    completed = sum(1 for t in study.trials if t.state == optuna.trial.TrialState.COMPLETE)
    remaining = max(0, trials - completed)
    if remaining > 0:
        study.optimize(objective, n_trials=remaining)

    # Rebuild trials_df from the full study so resumed sessions emit a row
    # per completed trial — including ones executed in a previous process.
    rows: list[dict[str, Any]] = []
    for trial in study.trials:
        if trial.state != optuna.trial.TrialState.COMPLETE:
            continue
        cached = trial_metrics.get(trial.number)
        if cached is not None:
            rows.append({"trial": trial.number, **cached})
        else:
            # Trial completed in a prior process — full per-run metrics weren't
            # captured in this session; emit params + Optuna's recorded value
            # under the legacy "objective" column to preserve the contract.
            rows.append(
                {
                    "trial": trial.number,
                    **trial.params,
                    "objective": trial.value,
                }
            )
    trials_df = pd.DataFrame(rows)
    write_table(warehouse_dir, "optuna_trials", trials_df)
    sync_duckdb(warehouse_dir)
    return trials_df


def export_dashboard_data(data_dir: Path, warehouse_dir: Path, output_dir: Path) -> dict[str, int]:
    output_dir.mkdir(parents=True, exist_ok=True)
    tables = {table: read_table(warehouse_dir, table) for table in WAREHOUSE_TABLES}
    exports: dict[str, Any] = {
        "reports.json": _records(tables["reports"]),
        "strategy_runs.json": _records(tables["strategy_runs"]),
        "equity_daily.json": _records(tables["equity_daily"]),
        "candidate_pool_events.json": _records(tables["candidate_pool_events"]),
        "execution_events.json": _records(tables["execution_events"]),
        "positions_daily.json": _records(tables["positions_daily"]),
        "signals_daily.json": _signal_snapshot(tables["signals_daily"]),
        "current_positions.json": _current_positions(tables["positions_daily"]),
        "recent_trades.json": _recent_trades(tables["execution_events"]),
        "optuna_trials.json": _records(tables["optuna_trials"]),
        "pool_timeline.json": _pool_timeline(
            tables["equity_daily"], tables["candidate_pool_events"], tables["execution_events"]
        ),
        "strategy_heatmap.json": _strategy_heatmap(tables["strategy_runs"]),
    }
    counts = {}
    for filename, data in exports.items():
        (output_dir / filename).write_text(
            json.dumps(data, ensure_ascii=False, separators=(",", ":"), default=_json_default) + "\n",
            encoding="utf-8",
        )
        counts[filename] = len(data) if isinstance(data, list) else 1
    counts.update(_export_chart_series(tables, output_dir / "chart_series"))
    return counts


def _export_chart_series(tables: dict[str, pd.DataFrame], chart_dir: Path) -> dict[str, int]:
    prices = tables["daily_prices"]
    reports = tables["reports"]
    if prices.empty or reports.empty:
        return {}
    chart_dir.mkdir(parents=True, exist_ok=True)
    for old_file in chart_dir.glob("*.json"):
        old_file.unlink()

    prices = prices.copy()
    prices["date"] = pd.to_datetime(prices["date"]).dt.date.astype(str)
    reports = reports.copy()
    reports["publication_date"] = pd.to_datetime(reports["publication_date"]).dt.date.astype(str)
    executions = tables["execution_events"].copy()
    if not executions.empty:
        executions["date"] = pd.to_datetime(executions["date"]).dt.date.astype(str)
    signals = tables["signals_daily"].copy()
    if not signals.empty:
        signals["date"] = pd.to_datetime(signals["date"]).dt.date.astype(str)

    index_rows: list[dict[str, Any]] = []
    report_symbols = sorted(set(reports["symbol"].dropna().astype(str)))
    for symbol in report_symbols:
        symbol_prices = prices[prices["symbol"].astype(str) == symbol].copy().sort_values("date")
        if symbol_prices.empty or pd.to_numeric(symbol_prices["close"], errors="coerce").dropna().empty:
            continue
        symbol_reports = (
            reports[reports["symbol"].astype(str) == symbol].copy().sort_values("publication_date")
        )
        symbol_executions = (
            executions[executions["symbol"].astype(str) == symbol].copy()
            if not executions.empty
            else pd.DataFrame()
        )
        symbol_signals = (
            signals[signals["symbol"].astype(str) == symbol].copy() if not signals.empty else pd.DataFrame()
        )
        payload = _chart_payload_for_symbol(
            symbol, symbol_prices, symbol_reports, symbol_executions, symbol_signals
        )
        filename = f"{_safe_symbol_filename(symbol)}.json"
        (chart_dir / filename).write_text(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=_json_default) + "\n",
            encoding="utf-8",
        )
        index_rows.append(
            {
                "symbol": symbol,
                "company": payload["meta"]["company"],
                "file": filename,
                "last_date": payload["meta"]["last_date"],
                "last_close": payload["meta"]["last_close"],
                "report_count": len(payload["report_markers"]),
                "trade_count": len(payload["trade_markers"]),
            }
        )
    (chart_dir / "index.json").write_text(
        json.dumps(index_rows, ensure_ascii=False, separators=(",", ":"), default=_json_default) + "\n",
        encoding="utf-8",
    )
    return {"chart_series/index.json": len(index_rows), "chart_series/*.json": len(index_rows)}


def _chart_payload_for_symbol(
    symbol: str,
    prices: pd.DataFrame,
    reports: pd.DataFrame,
    executions: pd.DataFrame,
    signals: pd.DataFrame,
) -> dict[str, Any]:
    prices = prices.copy()
    for column in ["open", "high", "low", "close", "volume"]:
        prices[column] = pd.to_numeric(prices[column], errors="coerce")
    prices = prices.dropna(subset=["close"])
    close = prices["close"]
    ohlc = [
        {
            "time": row["date"],
            "open": _finite_float(row["open"]) or _finite_float(row["close"]),
            "high": _finite_float(row["high"]) or _finite_float(row["close"]),
            "low": _finite_float(row["low"]) or _finite_float(row["close"]),
            "close": _finite_float(row["close"]),
        }
        for row in prices.to_dict("records")
    ]
    ma = {
        f"ma{window}": [
            {"time": str(date), "value": _finite_float(value)}
            for date, value in zip(prices["date"], close.rolling(window).mean(), strict=True)
            if _finite_float(value) is not None
        ]
        for window in [50, 150, 200]
    }
    latest_report = reports.iloc[-1].to_dict() if not reports.empty else {}
    company = str(latest_report.get("company") or symbol)
    price_lines = _price_lines_for_report(latest_report)
    report_markers = [
        {
            "time": row["publication_date"],
            "position": "belowBar",
            "shape": "circle",
            "color": "#334155",
            "text": "R",
            "report_id": row.get("report_id", ""),
            "title": row.get("title", ""),
            "target_price": _finite_float(row.get("target_price")),
            "publication_price": _finite_float(row.get("report_current_price_krw"))
            or _finite_float(row.get("report_current_price")),
        }
        for row in reports.to_dict("records")
    ]
    trade_markers = []
    if not executions.empty:
        for row in executions.sort_values("date").to_dict("records"):
            event_type = str(row.get("event_type", ""))
            is_sell = event_type == "sell"
            trade_markers.append(
                {
                    "run_id": row.get("run_id", ""),
                    "time": row.get("date", ""),
                    "position": "aboveBar" if is_sell else "belowBar",
                    "shape": "arrowDown" if is_sell else "arrowUp",
                    "color": "#dc2626" if is_sell else "#059669",
                    "text": _trade_marker_text(row),
                    "event_type": event_type,
                    "reason": row.get("reason", ""),
                    "price": _finite_float(row.get("price")),
                    "weight": _finite_float(row.get("weight")),
                    "gross_return": _finite_float(row.get("gross_return")),
                    "realized_return": _finite_float(row.get("realized_return")),
                }
            )
    signal_snapshot = []
    if not signals.empty:
        latest = signals.sort_values("date").groupby("run_id", as_index=False).tail(1)
        signal_snapshot = _records(latest)
    last_row = prices.iloc[-1].to_dict()
    return {
        "meta": {
            "symbol": symbol,
            "company": company,
            "last_date": last_row.get("date", ""),
            "last_close": _finite_float(last_row.get("close")),
            "display_currency": str(
                latest_report.get("display_currency") or latest_report.get("price_currency") or ""
            ),
            "report_count": len(reports),
        },
        "ohlc": ohlc,
        **ma,
        "report_markers": report_markers,
        "trade_markers": trade_markers,
        "price_lines": price_lines,
        "signals": signal_snapshot,
    }


def _price_lines_for_report(report: dict[str, Any]) -> list[dict[str, Any]]:
    specs = [
        ("report_current_price_krw", "발간가", "#64748b"),
        ("bear_target_krw", "Bear", "#ea580c"),
        ("base_target_krw", "Base", "#2563eb"),
        ("bull_target_krw", "Bull", "#16a34a"),
    ]
    lines = []
    for column, title, color in specs:
        price = _finite_float(report.get(column))
        if price is None and column == "report_current_price_krw":
            price = _finite_float(report.get("report_current_price"))
        if price is None:
            continue
        lines.append({"title": title, "price": price, "color": color})
    return lines


def _trade_marker_text(row: dict[str, Any]) -> str:
    event = str(row.get("event_type", ""))
    reason = str(row.get("reason", ""))
    if event == "buy":
        return "B"
    if event == "rebalance":
        return "R"
    return {
        "stop_loss": "SL",
        "take_profit": "TP",
        "take_profit_rr": "TP",
        "target_hit": "TG",
        "signal_loss": "S",
        "candidate_aging_out": "EX",
        "candidate_expired": "EX",
        "candidate_target_hit": "TG",
    }.get(reason, "S" if event == "sell" else event[:2].upper())


def _safe_symbol_filename(symbol: str) -> str:
    return "".join(char if char.isalnum() or char in "._-" else "_" for char in symbol)


def _finite_float(value: Any) -> float | None:
    parsed = _float_or_none(value)
    if parsed is None or not math.isfinite(parsed):
        return None
    return float(parsed)


def read_reports(data_dir: Path) -> pd.DataFrame:
    csv_path = data_dir / "extracted_reports.csv"
    metrics = {item.get("title", ""): item for item in read_json(data_dir / "price_metrics.json")}
    rows: list[dict[str, Any]] = []
    if not csv_path.exists():
        return pd.DataFrame()
    with csv_path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            metric = metrics.get(row.get("리포트명", ""), {})
            symbol = metric.get("yfinance_symbol") or infer_yfinance_symbol(
                row.get("티커", ""), row.get("거래소", "")
            )
            if not symbol:
                continue
            target = (
                _float_or_none(row.get("Base 목표가"))
                or _float_or_none(row.get("Bull 목표가"))
                or _float_or_none(row.get("Bear 목표가"))
            )
            publication = format_date(row.get("게시일", ""))
            report_id = stable_report_id(row.get("게시일", ""), row.get("리포트명", ""), symbol)
            rows.append(
                {
                    "report_id": report_id,
                    "page": int(row.get("페이지") or 0),
                    "ordinal": int(row.get("순번") or 0),
                    "publication_date": publication,
                    "title": row.get("리포트명", ""),
                    "company": row.get("종목명", "") or metric.get("company", ""),
                    "ticker": row.get("티커", ""),
                    "exchange": row.get("거래소", ""),
                    "symbol": symbol,
                    "pdf_filename": row.get("PDF 파일명", ""),
                    "pdf_url": row.get("PDF URL", ""),
                    "report_current_price": _float_or_none(row.get("리포트 현재주가")),
                    "bear_target": _float_or_none(row.get("Bear 목표가")),
                    "base_target": _float_or_none(row.get("Base 목표가")),
                    "bull_target": _float_or_none(row.get("Bull 목표가")),
                    "target_price_local": target,
                    "target_price": target,
                    "target_currency": row.get("목표가 통화", ""),
                    "price_currency": "",
                    "display_currency": "",
                    "markdown_filename": Path(row.get("PDF 파일명", "")).with_suffix(".md").name
                    if row.get("PDF 파일명", "")
                    else "",
                }
            )
    return pd.DataFrame(rows).sort_values(["publication_date", "symbol"])


def apply_report_krw_targets(reports: pd.DataFrame, fx_rates: pd.DataFrame) -> pd.DataFrame:
    if reports.empty:
        return reports
    frame = reports.copy()
    for column in ["report_current_price", "bear_target", "base_target", "bull_target", "target_price_local"]:
        if column not in frame:
            frame[column] = pd.NA
    converted_rows = []
    for row in frame.to_dict("records"):
        target_currency = normalize_currency(str(row.get("target_currency", ""))) or currency_for_symbol(
            str(row.get("symbol", "")), str(row.get("exchange", ""))
        )
        price_currency = currency_for_symbol(str(row.get("symbol", "")), str(row.get("exchange", "")))
        date = str(row.get("publication_date", ""))
        converted_rows.append(
            {
                "report_current_price_krw": convert_value_to_krw(
                    _float_or_none(row.get("report_current_price")), price_currency, date, fx_rates
                ),
                "bear_target_krw": convert_value_to_krw(
                    _float_or_none(row.get("bear_target")), target_currency, date, fx_rates
                ),
                "base_target_krw": convert_value_to_krw(
                    _float_or_none(row.get("base_target")), target_currency, date, fx_rates
                ),
                "bull_target_krw": convert_value_to_krw(
                    _float_or_none(row.get("bull_target")), target_currency, date, fx_rates
                ),
                "target_price_krw": convert_value_to_krw(
                    _float_or_none(row.get("target_price_local") or row.get("target_price")),
                    target_currency,
                    date,
                    fx_rates,
                ),
                "price_currency": price_currency,
                "target_currency": target_currency,
                "display_currency": "KRW",
            }
        )
    converted = pd.DataFrame(converted_rows)
    for column in converted.columns:
        frame[column] = converted[column].to_numpy()
    frame["target_price"] = frame["target_price_krw"].combine_first(frame.get("target_price"))
    return frame


def fill_report_publication_prices(reports: pd.DataFrame, prices: pd.DataFrame) -> pd.DataFrame:
    """Use the first available KRW close on or after publication as report publication price."""
    if reports.empty or prices.empty or "symbol" not in reports or "symbol" not in prices:
        return reports
    frame = reports.copy()
    price_frame = prices.copy()
    price_frame["date"] = pd.to_datetime(price_frame["date"], errors="coerce")
    price_frame["close"] = pd.to_numeric(price_frame["close"], errors="coerce")
    price_frame = price_frame.dropna(subset=["date", "symbol", "close"]).sort_values(["symbol", "date"])
    if "report_current_price_krw" not in frame:
        frame["report_current_price_krw"] = pd.NA
    publication_prices: list[float | None] = []
    for row in frame.to_dict("records"):
        symbol = str(row.get("symbol", ""))
        pub_date = pd.to_datetime(row.get("publication_date"), errors="coerce")
        if not symbol or pd.isna(pub_date):
            publication_prices.append(_float_or_none(row.get("report_current_price_krw")))
            continue
        symbol_prices = price_frame[
            (price_frame["symbol"].astype(str) == symbol) & (price_frame["date"] >= pub_date)
        ]
        if symbol_prices.empty:
            publication_prices.append(_float_or_none(row.get("report_current_price_krw")))
        else:
            publication_prices.append(float(symbol_prices.iloc[0]["close"]))
    frame["report_current_price_krw"] = publication_prices
    return frame


def read_or_build_reports(data_dir: Path, warehouse_dir: Path) -> pd.DataFrame:
    reports = read_table(warehouse_dir, "reports")
    if reports.empty:
        build_warehouse(data_dir, warehouse_dir)
        reports = read_table(warehouse_dir, "reports")
    return reports


def default_configs() -> list[BacktestConfig]:
    return [
        BacktestConfig(
            name="MTT / 1N / 24M",
            weighting="1/N",
            entry_rule="mtt",
            rebalance="weekly",
            lookback_days=LOOKBACK_WINDOWS["24M"],
        ),
        BacktestConfig(
            name="MTT / Sharpe / 24M",
            weighting="sharpe",
            entry_rule="mtt",
            rebalance="weekly",
            lookback_days=LOOKBACK_WINDOWS["24M"],
        ),
        BacktestConfig(
            name="MTT / Sortino / 24M",
            weighting="sortino",
            entry_rule="mtt",
            rebalance="weekly",
            lookback_days=LOOKBACK_WINDOWS["24M"],
        ),
        BacktestConfig(
            name="MTT+목표 / CVaR / 24M",
            weighting="cvar",
            entry_rule="mtt_target",
            rebalance="biweekly",
            min_target_upside=0.10,
            lookback_days=LOOKBACK_WINDOWS["24M"],
        ),
        BacktestConfig(
            name="Target only / Calmar / 24M",
            weighting="calmar",
            entry_rule="target_only",
            rebalance="monthly",
            min_target_upside=0.20,
            lookback_days=LOOKBACK_WINDOWS["24M"],
        ),
        BacktestConfig(
            name="MTT / Max return / 24M",
            weighting="max_return",
            entry_rule="mtt",
            rebalance="monthly",
            lookback_days=LOOKBACK_WINDOWS["24M"],
        ),
        BacktestConfig(
            name="MTT / Min var / 24M",
            weighting="min_var",
            entry_rule="mtt",
            rebalance="weekly",
            lookback_days=LOOKBACK_WINDOWS["24M"],
        ),
    ]


def download_history(symbol: str, start: datetime, end: datetime) -> pd.DataFrame:
    import yfinance as yf

    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        data = yf.download(
            symbol,
            start=start.date().isoformat(),
            end=end.date().isoformat(),
            progress=False,
            auto_adjust=True,
            threads=False,
            timeout=10,
        )
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    if data.empty or "Close" not in data:
        return pd.DataFrame()
    data = data.reset_index()
    date_col = "Date" if "Date" in data else data.columns[0]
    return pd.DataFrame(
        {
            "date": pd.to_datetime(data[date_col]).dt.date.astype(str),
            "open": pd.to_numeric(data.get("Open", data["Close"]), errors="coerce"),
            "high": pd.to_numeric(data.get("High", data["Close"]), errors="coerce"),
            "low": pd.to_numeric(data.get("Low", data["Close"]), errors="coerce"),
            "close": pd.to_numeric(data["Close"], errors="coerce"),
            "volume": pd.to_numeric(data.get("Volume", 0), errors="coerce").fillna(0),
        }
    ).dropna(subset=["close"])


def synthetic_price_history(reports: pd.DataFrame) -> pd.DataFrame:
    if reports.empty:
        return pd.DataFrame()
    start = pd.to_datetime(reports["publication_date"]).min() - pd.Timedelta(days=820)
    end = pd.Timestamp(datetime.now(UTC).date())
    dates = pd.bdate_range(start, end)
    frames = []
    for i, report in enumerate(reports.drop_duplicates("symbol").to_dict("records")):
        symbol = str(report["symbol"])
        seed = int(hashlib.sha1(symbol.encode("utf-8")).hexdigest()[:8], 16)
        rng = np.random.default_rng(seed)
        drift = 0.00015 + (i % 7) * 0.00003
        noise = rng.normal(0, 0.012, len(dates))
        trend = np.sin(np.arange(len(dates)) / (45 + i % 15)) * 0.0015
        log_path = np.cumsum(drift + noise + trend)
        base = float(report.get("report_current_price") or 100.0)
        close = np.maximum(1.0, base * np.exp(log_path - log_path[-1]))
        frame = pd.DataFrame(
            {
                "date": dates.date.astype(str),
                "symbol": symbol,
                "open": close,
                "high": close * 1.01,
                "low": close * 0.99,
                "close": close,
                "volume": 100000 + i * 100,
            }
        )
        frames.append(frame)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def _use_pydantic_v2() -> bool:
    """Principle-1a feature-flag escape per pre-mortem Scenario 1.

    Set ``SNUSMIC_USE_PYDANTIC_V2=0`` to fall back to raw ``pd.read_csv`` /
    ``to_csv`` (pre-migration path), kept inline for one release cycle to
    give us a one-env-var rollback.
    TODO(phase-1a): remove this escape hatch after one release cycle per plan.
    """
    return os.environ.get("SNUSMIC_USE_PYDANTIC_V2", "1") != "0"


def _validate_rows(table: str, frame: pd.DataFrame) -> None:
    """Validate every row of ``frame`` against ``TABLE_MODELS[table]``.

    Raises ``pydantic.ValidationError`` when:
      * a required column is missing,
      * an unknown column is present (``ConfigDict(extra='forbid')``),
      * a cell fails model-level type coercion.
    """
    model = TABLE_MODELS.get(table)
    if model is None or frame.empty:
        return
    # Pandas stores integer columns with NaN as float64; coerce NaN → None
    # so Pydantic's Optional[int] / Optional[float] validators accept them.
    records: list[dict[str, Any]] = []
    for raw in frame.to_dict(orient="records"):
        cleaned: dict[str, Any] = {}
        for key, value in raw.items():
            str_key = str(key)
            if isinstance(value, float) and math.isnan(value):
                cleaned[str_key] = None
            else:
                cleaned[str_key] = value
        records.append(cleaned)
    TypeAdapter(list[model]).validate_python(records)  # type: ignore[valid-type]


def write_table(warehouse_dir: Path, table: str, frame: pd.DataFrame) -> None:
    """Write a DataFrame to ``{warehouse_dir}/{table}.csv``.

    If ``table`` is registered in :data:`TABLE_MODELS` and the Pydantic-v2
    feature flag is on (default), every row is validated via ``TypeAdapter``
    before ``to_csv`` — unknown or missing columns raise ``ValidationError``.
    This is the write-side half of Principle 2 (typed SSOT at read AND write
    boundaries).
    """
    warehouse_dir.mkdir(parents=True, exist_ok=True)
    path = warehouse_dir / f"{table}.csv"
    if _use_pydantic_v2():
        _validate_rows(table, frame)
    frame.to_csv(path, index=False, encoding="utf-8")


def read_table(warehouse_dir: Path, table: str) -> pd.DataFrame:
    """Read ``{warehouse_dir}/{table}.csv`` into a DataFrame.

    Under the default Pydantic-v2 flag, rows are validated after ``pd.read_csv``
    so downstream callers get a guaranteed-shape DataFrame. With
    ``SNUSMIC_USE_PYDANTIC_V2=0`` we bypass validation (legacy path)."""
    path = warehouse_dir / f"{table}.csv"
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame()
    frame = pd.read_csv(path, dtype=TABLE_DTYPES.get(table))
    if _use_pydantic_v2():
        _validate_rows(table, frame)
    return frame


def sync_duckdb(warehouse_dir: Path) -> None:
    try:
        import duckdb
    except ImportError:
        return
    db_path = warehouse_dir / "snusmic.duckdb"
    con = duckdb.connect(str(db_path))
    try:
        for table in WAREHOUSE_TABLES:
            csv_path = warehouse_dir / f"{table}.csv"
            if csv_path.exists() and csv_path.stat().st_size > 0:
                con.execute(
                    f"CREATE OR REPLACE TABLE {table} AS SELECT * FROM read_csv_auto(?, header=true, quote='\"', sample_size=-1)",
                    [str(csv_path)],
                )
    finally:
        con.close()


def infer_yfinance_symbol(ticker: str, exchange: str) -> str:
    ticker = str(ticker or "").strip().upper()
    exchange = str(exchange or "").strip().upper()
    if not ticker:
        return ""
    if exchange == "KRX" and ticker.isdigit():
        return f"{ticker}.KS"
    if exchange == "KOSDAQ" and ticker.isdigit():
        return f"{ticker}.KQ"
    if exchange == "TYO":
        return f"{ticker}.T"
    if exchange in {"HKG", "HKEX"}:
        return f"{ticker}.HK"
    if exchange == "SZSE":
        return f"{ticker}.SZ"
    if exchange == "SSE":
        return f"{ticker}.SS"
    if exchange == "EPA":
        return f"{ticker}.PA"
    if exchange == "AMS":
        return f"{ticker}.AS"
    if exchange == "SIX":
        return f"{ticker}.SW"
    return ticker


def stable_report_id(date: str, title: str, symbol: str) -> str:
    return hashlib.sha1(f"{date}|{title}|{symbol}".encode()).hexdigest()[:16]


def format_date(value: str) -> str:
    if not value:
        return ""
    return value.replace("T", " ")[:10]


def read_json(path: Path) -> Any:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def _records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    if frame.empty:
        return []
    clean = frame.replace({np.nan: None})
    return clean.to_dict("records")


def _signal_snapshot(frame: pd.DataFrame) -> list[dict[str, Any]]:
    if frame.empty:
        return []
    latest_by_run = frame.sort_values("date").groupby(["run_id", "symbol"], as_index=False).tail(1)
    return _records(latest_by_run)


def _current_positions(positions: pd.DataFrame) -> list[dict[str, Any]]:
    if positions.empty:
        return []
    rows = positions.copy()
    rows["date"] = rows["date"].astype(str)
    latest = rows.groupby("run_id")["date"].transform("max")
    rows = rows[rows["date"] == latest].copy()
    last_valid = positions.dropna(subset=["close"]).copy()
    if not last_valid.empty:
        last_valid["date"] = last_valid["date"].astype(str)
        last_valid = last_valid.sort_values("date").groupby(["run_id", "symbol"], as_index=False).tail(1)
        last_valid = last_valid[["run_id", "symbol", "close", "gross_return"]].rename(
            columns={"close": "last_close", "gross_return": "last_gross_return"}
        )
        rows = rows.merge(last_valid, how="left", on=["run_id", "symbol"])
        rows["close"] = rows["close"].fillna(rows["last_close"])
        rows["gross_return"] = rows["gross_return"].fillna(rows["last_gross_return"])
        rows = rows.drop(columns=["last_close", "last_gross_return"])
    rows = rows.sort_values(["run_id", "weight"], ascending=[True, False])
    return _records(rows)


def _recent_trades(execution_events: pd.DataFrame) -> list[dict[str, Any]]:
    if execution_events.empty:
        return []
    rows = execution_events[execution_events["event_type"].isin(["buy", "sell"])].copy()
    if rows.empty:
        return []
    rows["date"] = rows["date"].astype(str)
    rows = rows.sort_values(["run_id", "date"], ascending=[True, False])
    rows = rows.groupby("run_id", as_index=False).head(80)
    return _records(rows)


def _pool_timeline(
    equity: pd.DataFrame, candidate_events: pd.DataFrame, execution_events: pd.DataFrame
) -> list[dict[str, Any]]:
    if equity.empty:
        return []
    rows = equity.copy()
    rows["candidate_events"] = 0
    rows["execution_events"] = 0
    if not candidate_events.empty:
        counts = candidate_events.groupby(["run_id", "date"]).size().rename("candidate_events")
        rows = rows.drop(columns=["candidate_events"]).merge(counts, how="left", on=["run_id", "date"])
    if not execution_events.empty:
        counts = execution_events.groupby(["run_id", "date"]).size().rename("execution_events")
        rows = rows.drop(columns=["execution_events"]).merge(counts, how="left", on=["run_id", "date"])
    rows[["candidate_events", "execution_events"]] = (
        rows[["candidate_events", "execution_events"]].fillna(0).astype(int)
    )
    return _records(rows)


def _strategy_heatmap(strategy_runs: pd.DataFrame) -> list[dict[str, Any]]:
    if strategy_runs.empty:
        return []
    rows = strategy_runs.copy()
    rows["bucket"] = rows["entry_rule"].astype(str) + " / " + rows["weighting"].astype(str)
    return _records(
        rows[
            [
                "run_id",
                "strategy_name",
                "bucket",
                "rebalance",
                "final_wealth",
                "total_return",
                "max_drawdown",
                "sharpe",
                "calmar",
            ]
        ]
    )


def _float_or_none(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        if pd.isna(value):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _json_default(value: Any) -> Any:
    if isinstance(value, (np.integer, np.floating)):
        return value.item()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value
