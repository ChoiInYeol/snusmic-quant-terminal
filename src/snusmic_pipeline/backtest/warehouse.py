from __future__ import annotations

import contextlib
import csv
import hashlib
import io
import json
import math
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd

from .engine import run_walk_forward_backtest, stable_run_id
from .schemas import BacktestConfig

WAREHOUSE_TABLES = [
    "reports",
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
) -> pd.DataFrame:
    warehouse_dir.mkdir(parents=True, exist_ok=True)
    reports = read_or_build_reports(data_dir, warehouse_dir)
    if reports.empty:
        prices = pd.DataFrame()
        write_table(warehouse_dir, "daily_prices", prices)
        return prices
    now = now or datetime.now(timezone.utc)
    start = pd.to_datetime(reports["publication_date"]).min().to_pydatetime() - timedelta(days=820)
    end = now + timedelta(days=1)
    selected_symbols = symbols or sorted(set(reports["symbol"].dropna().astype(str)))
    downloader = downloader or download_history
    frames = []
    for symbol in selected_symbols:
        history = downloader(symbol, start, end)
        if history.empty:
            continue
        history = history.copy()
        history["symbol"] = symbol
        frames.append(history)
    prices = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if symbols:
        existing = read_table(warehouse_dir, "daily_prices")
        if not existing.empty:
            existing = existing[~existing["symbol"].astype(str).isin(selected_symbols)]
            prices = pd.concat([existing, prices], ignore_index=True) if not prices.empty else existing
    if not prices.empty:
        prices["date"] = pd.to_datetime(prices["date"]).dt.date.astype(str)
        prices = prices[["date", "symbol", "open", "high", "low", "close", "volume"]].drop_duplicates(["date", "symbol"], keep="last").sort_values(["date", "symbol"])
    write_table(warehouse_dir, "daily_prices", prices)
    sync_duckdb(warehouse_dir)
    return prices


def run_default_backtests(
    data_dir: Path,
    warehouse_dir: Path,
    dry_run: bool = False,
    configs: list[BacktestConfig] | None = None,
) -> dict[str, int]:
    warehouse_dir.mkdir(parents=True, exist_ok=True)
    reports = read_or_build_reports(data_dir, warehouse_dir)
    prices = read_table(warehouse_dir, "daily_prices")
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
        data = pd.concat([frame for frame in frames if not frame.empty], ignore_index=True) if any(not frame.empty for frame in frames) else pd.DataFrame()
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
) -> pd.DataFrame:
    import optuna

    reports = read_or_build_reports(data_dir, warehouse_dir)
    prices = read_table(warehouse_dir, "daily_prices")
    if dry_run or prices.empty:
        prices = synthetic_price_history(reports)

    trial_rows: list[dict[str, Any]] = []

    def objective(trial: optuna.Trial) -> float:
        config = BacktestConfig(
            name=f"optuna_{trial.number:03d}",
            weighting=trial.suggest_categorical("weighting", ["1/N", "max_return", "min_var", "sharpe", "sortino", "cvar", "calmar"]),
            entry_rule=trial.suggest_categorical("entry_rule", ["mtt_or_rs", "mtt_and_rs", "target_only", "hybrid_score"]),
            rs_threshold=trial.suggest_float("rs_threshold", 60, 95, step=5),
            mtt_slope_months=trial.suggest_int("mtt_slope_months", 1, 5),
            max_pool_months=trial.suggest_categorical("max_pool_months", [3, 6, 9, 12]),
            target_hit_multiplier=trial.suggest_float("target_hit_multiplier", 1.0, 1.5, step=0.1),
            stop_loss_pct=trial.suggest_categorical("stop_loss_pct", [0.06, 0.08, 0.10, 0.12]),
            reward_risk=trial.suggest_categorical("reward_risk", [2.0, 3.0, 4.0]),
            rebalance=trial.suggest_categorical("rebalance", ["daily", "weekly", "biweekly", "monthly"]),
            lookback_days=504,
            min_target_upside=trial.suggest_categorical("min_target_upside", [0.0, 0.10, 0.20]),
        )
        result = run_walk_forward_backtest(reports, prices, config)
        summary = result["strategy_runs"].iloc[0].to_dict()
        trial_rows.append({"trial": trial.number, **config.to_dict(), **summary})
        return float(summary.get("objective") or 0.0)

    study = optuna.create_study(direction="maximize", sampler=optuna.samplers.TPESampler(seed=seed))
    study.optimize(objective, n_trials=trials)
    trials_df = pd.DataFrame(trial_rows)
    write_table(warehouse_dir, "optuna_trials", trials_df)
    sync_duckdb(warehouse_dir)
    return trials_df


def export_dashboard_data(data_dir: Path, warehouse_dir: Path, output_dir: Path) -> dict[str, int]:
    output_dir.mkdir(parents=True, exist_ok=True)
    tables = {table: read_table(warehouse_dir, table) for table in WAREHOUSE_TABLES}
    exports: dict[str, Any] = {
        "strategy_runs.json": _records(tables["strategy_runs"]),
        "equity_daily.json": _records(tables["equity_daily"]),
        "candidate_pool_events.json": _records(tables["candidate_pool_events"]),
        "execution_events.json": _records(tables["execution_events"]),
        "positions_daily.json": _records(tables["positions_daily"]),
        "signals_daily.json": _signal_snapshot(tables["signals_daily"]),
        "optuna_trials.json": _records(tables["optuna_trials"]),
        "pool_timeline.json": _pool_timeline(tables["equity_daily"], tables["candidate_pool_events"], tables["execution_events"]),
        "strategy_heatmap.json": _strategy_heatmap(tables["strategy_runs"]),
    }
    counts = {}
    for filename, data in exports.items():
        (output_dir / filename).write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":"), default=_json_default) + "\n", encoding="utf-8")
        counts[filename] = len(data) if isinstance(data, list) else 1
    return counts


def read_reports(data_dir: Path) -> pd.DataFrame:
    csv_path = data_dir / "extracted_reports.csv"
    metrics = {item.get("title", ""): item for item in read_json(data_dir / "price_metrics.json")}
    rows: list[dict[str, Any]] = []
    if not csv_path.exists():
        return pd.DataFrame()
    with csv_path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            metric = metrics.get(row.get("리포트명", ""), {})
            symbol = metric.get("yfinance_symbol") or infer_yfinance_symbol(row.get("티커", ""), row.get("거래소", ""))
            if not symbol:
                continue
            target = _float_or_none(row.get("Base 목표가")) or _float_or_none(row.get("Bull 목표가")) or _float_or_none(row.get("Bear 목표가"))
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
                    "target_price": target,
                    "target_currency": row.get("목표가 통화", ""),
                    "markdown_filename": Path(row.get("PDF 파일명", "")).with_suffix(".md").name if row.get("PDF 파일명", "") else "",
                }
            )
    return pd.DataFrame(rows).sort_values(["publication_date", "symbol"])


def read_or_build_reports(data_dir: Path, warehouse_dir: Path) -> pd.DataFrame:
    reports = read_table(warehouse_dir, "reports")
    if reports.empty:
        build_warehouse(data_dir, warehouse_dir)
        reports = read_table(warehouse_dir, "reports")
    return reports


def default_configs() -> list[BacktestConfig]:
    return [
        BacktestConfig(name="MTT or RS / 1N / weekly", weighting="1/N", entry_rule="mtt_or_rs", rebalance="weekly"),
        BacktestConfig(name="MTT or RS / Sharpe / weekly", weighting="sharpe", entry_rule="mtt_or_rs", rebalance="weekly"),
        BacktestConfig(name="MTT and RS / Sortino / weekly", weighting="sortino", entry_rule="mtt_and_rs", rebalance="weekly"),
        BacktestConfig(name="Hybrid target / CVaR / biweekly", weighting="cvar", entry_rule="hybrid_score", rebalance="biweekly", min_target_upside=0.10),
        BacktestConfig(name="Target only / Calmar / monthly", weighting="calmar", entry_rule="target_only", rebalance="monthly", min_target_upside=0.20),
        BacktestConfig(name="MTT or RS / Max return / monthly", weighting="max_return", entry_rule="mtt_or_rs", rebalance="monthly"),
        BacktestConfig(name="MTT or RS / Min var / weekly", weighting="min_var", entry_rule="mtt_or_rs", rebalance="weekly"),
    ]


def download_history(symbol: str, start: datetime, end: datetime) -> pd.DataFrame:
    import yfinance as yf

    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        data = yf.download(symbol, start=start.date().isoformat(), end=end.date().isoformat(), progress=False, auto_adjust=True, threads=False)
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
    end = pd.Timestamp(datetime.now(timezone.utc).date())
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


def write_table(warehouse_dir: Path, table: str, frame: pd.DataFrame) -> None:
    warehouse_dir.mkdir(parents=True, exist_ok=True)
    path = warehouse_dir / f"{table}.csv"
    frame.to_csv(path, index=False, encoding="utf-8")


def read_table(warehouse_dir: Path, table: str) -> pd.DataFrame:
    path = warehouse_dir / f"{table}.csv"
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame()
    return pd.read_csv(path)


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
                con.execute(f"CREATE OR REPLACE TABLE {table} AS SELECT * FROM read_csv_auto(?)", [str(csv_path)])
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
    return ticker


def stable_report_id(date: str, title: str, symbol: str) -> str:
    return hashlib.sha1(f"{date}|{title}|{symbol}".encode("utf-8")).hexdigest()[:16]


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


def _pool_timeline(equity: pd.DataFrame, candidate_events: pd.DataFrame, execution_events: pd.DataFrame) -> list[dict[str, Any]]:
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
    rows[["candidate_events", "execution_events"]] = rows[["candidate_events", "execution_events"]].fillna(0).astype(int)
    return _records(rows)


def _strategy_heatmap(strategy_runs: pd.DataFrame) -> list[dict[str, Any]]:
    if strategy_runs.empty:
        return []
    rows = strategy_runs.copy()
    rows["bucket"] = rows["entry_rule"].astype(str) + " / " + rows["weighting"].astype(str)
    return _records(rows[["run_id", "strategy_name", "bucket", "rebalance", "final_wealth", "total_return", "max_drawdown", "sharpe", "calmar"]])


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
