"""Warehouse IO layer for the persona simulation.

Salvaged from the legacy ``snusmic_pipeline.backtest.warehouse`` module so the
sim has its own canonical IO surface (read/write CSV tables, FX-aware KRW
conversion, yfinance OHLCV downloader). Only the helpers the sim consumes are
kept; weight-based backtest exports were dropped.
"""

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
from .schemas import TABLE_DTYPES, TABLE_MODELS

WAREHOUSE_TABLES = ["reports", "fx_rates", "daily_prices"]

COMPANY_SYMBOL_OVERRIDES = {
    "Bili bili": ("BILI", "NASDAQ", "BILI", "USD"),
    "Bilibili": ("BILI", "NASDAQ", "BILI", "USD"),
    "Cyber Agent": ("4751", "TYO", "4751.T", "JPY"),
    "CyberAgent Inc.": ("4751", "TYO", "4751.T", "JPY"),
    "쿠쿠홈시스": ("284740", "KRX", "284740.KS", "KRW"),
    "한화솔루션": ("009830", "KRX", "009830.KS", "KRW"),
}

KOSDAQ_TICKERS = {
    "033500",
    "035900",
    "036930",
    "041830",
    "043650",
    "044490",
    "049720",
    "053030",
    "054210",
    "054780",
    "060150",
    "067160",
    "089600",
    "089860",
    "089890",
    "090460",
    "098120",
    "099430",
    "100840",
    "101160",
    "101490",
    "108490",
    "114810",
    "119610",
    "119850",
    "122640",
    "131970",
    "148150",
    "159010",
    "166090",
    "170790",
    "182360",
    "189300",
    "192400",
    "194480",
    "196170",
    "200710",
    "204620",
    "211050",
    "214450",
    "215000",
    "218410",
    "228670",
    "234300",
    "237690",
    "259960",
    "263750",
    "280360",
    "285490",
    "287410",
    "293490",
    "294570",
    "298020",
    "310200",
    "328130",
    "344820",
    "348210",
    "348370",
    "353810",
    "356860",
    "363250",
    "366030",
    "368600",
    "376980",
    "403870",
    "408920",
    "420770",
    "440110",
    "453340",
    "456160",
    "461300",
    "472850",
    "473980",
    "475960",
    "476830",
    "950160",
    "950170",
}


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

    Per-symbol incremental fetch — when the warehouse already has bars for a
    symbol up to ``last_seen``, the downloader is invoked with
    ``start = last_seen + 1 day`` instead of the full publication-window
    start. Symbols whose ``last_seen >= end`` are skipped entirely (zero
    network calls). The merged result re-deduplicates on ``(date, symbol)``
    so re-running with overlapping windows is idempotent.

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
        if symbol_start.date() >= end.date():
            continue
        history = downloader(symbol, symbol_start, end)
        if history.empty:
            continue
        history = history.copy()
        history["symbol"] = symbol
        frames.append(history)
    new_prices = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    if symbols:
        existing = read_table(warehouse_dir, "daily_prices") if not force_full else existing_full
        if not existing.empty:
            existing = existing[~existing["symbol"].astype(str).isin(selected_symbols)]
        else:
            existing = pd.DataFrame()
        prices = pd.concat([existing, new_prices], ignore_index=True) if not new_prices.empty else existing
    else:
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
        if (
            "display_currency" in group.columns
            and group["display_currency"].dropna().astype(str).str.upper().eq("KRW").all()
            and group["display_currency"].notna().any()
        ):
            frames.append(group)
            continue
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


def read_reports(data_dir: Path) -> pd.DataFrame:
    csv_path = data_dir / "extracted_reports.csv"
    metrics = {item.get("title", ""): item for item in read_json(data_dir / "price_metrics.json")}
    rows: list[dict[str, Any]] = []
    if not csv_path.exists():
        return pd.DataFrame()
    with csv_path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            metric = metrics.get(row.get("리포트명", ""), {})
            company = row.get("종목명", "") or metric.get("company", "")
            override = COMPANY_SYMBOL_OVERRIDES.get(company)
            ticker = str(row.get("티커", ""))
            exchange = str(row.get("거래소", ""))
            target_currency = row.get("목표가 통화", "")
            if override:
                ticker, exchange, symbol, target_currency = override
            else:
                symbol = metric.get("yfinance_symbol") or infer_yfinance_symbol(ticker, exchange)
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
                    "company": company,
                    "ticker": ticker,
                    "exchange": exchange,
                    "symbol": symbol,
                    "pdf_filename": row.get("PDF 파일명", ""),
                    "pdf_url": row.get("PDF URL", ""),
                    "report_current_price": _float_or_none(row.get("리포트 현재주가")),
                    "bear_target": _float_or_none(row.get("Bear 목표가")),
                    "base_target": _float_or_none(row.get("Base 목표가")),
                    "bull_target": _float_or_none(row.get("Bull 목표가")),
                    "target_price_local": target,
                    "target_price": target,
                    "target_currency": target_currency,
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
            market_close = float(symbol_prices.iloc[0]["close"])
            quoted_close = _float_or_none(row.get("report_current_price_krw"))
            if quoted_close and market_close > 0:
                ratio = market_close / quoted_close
                if ratio > 4 or ratio < 0.25:
                    publication_prices.append(quoted_close)
                    continue
            publication_prices.append(market_close)
    frame["report_current_price_krw"] = publication_prices
    return frame


def read_or_build_reports(data_dir: Path, warehouse_dir: Path) -> pd.DataFrame:
    reports = read_table(warehouse_dir, "reports")
    if reports.empty:
        build_warehouse(data_dir, warehouse_dir)
        reports = read_table(warehouse_dir, "reports")
    return reports


def download_history(symbol: str, start: datetime, end: datetime) -> pd.DataFrame:
    import yfinance as yf

    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        data = yf.download(
            symbol,
            start=start.date().isoformat(),
            end=end.date().isoformat(),
            progress=False,
            # auto_adjust=False so OHLC matches the **actual market price**
            # users (and SMIC reports) reference. With auto_adjust=True yfinance
            # back-adjusts historical OHLC for cumulative dividends, which on
            # high-yield Korean stocks (e.g. 고려신용정보 049720) drags the
            # historical price 10–60% below the price the report quoted.
            # Returns understate dividend reinvestment as a result; that's
            # the correct trade-off for this product because the brokerage
            # ledger already accounts for cash separately.
            auto_adjust=False,
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


def _use_pydantic_v2() -> bool:
    """Feature-flag escape — set ``SNUSMIC_USE_PYDANTIC_V2=0`` to fall back to
    raw ``pd.read_csv`` / ``to_csv`` (pre-migration path). Kept inline as a
    one-env-var rollback."""
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
    if exchange == "KRX" and ticker in KOSDAQ_TICKERS:
        return f"{ticker}.KQ"
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
    return hashlib.sha1(f"{date}|{title}".encode()).hexdigest()[:16]


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
