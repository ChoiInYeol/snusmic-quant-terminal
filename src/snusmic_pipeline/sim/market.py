"""Market data adapter for the persona simulation.

Two responsibilities:

1. **PriceBoard** — wraps the KRW-converted ``daily_prices.csv`` warehouse
   table in a date-indexed wide pivot for fast ``(date, symbol) → close``
   lookups. Adds asof helpers and a forward-window slice the prophet
   personas need.

2. **Benchmark loader** — downloads (and caches) the All-Weather basket's
   USD ETFs and KOSPI ETF in KRW, reusing the existing
   :mod:`snusmic_pipeline.currency` FX pipeline.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from ..backtest.warehouse import (
    apply_daily_price_krw_conversion,
    download_history,
    read_table,
    write_table,
)
from ..currency import download_fx_rates

# ---------------------------------------------------------------------------
# PriceBoard — fast lookups for the SNUSMIC report universe.
# ---------------------------------------------------------------------------


@dataclass
class PriceBoard:
    """Date-indexed wide pivot of close prices in KRW.

    Build via :func:`PriceBoard.from_warehouse`. Empty boards are legal —
    callers must check ``board.is_empty`` before driving the engine.
    """

    close: pd.DataFrame  # index = pd.DatetimeIndex (UTC-naive midnight), columns = symbol
    open: pd.DataFrame  # may be the same as close if no opens were captured

    @classmethod
    def from_warehouse(cls, warehouse_dir: Path) -> PriceBoard:
        prices = read_table(warehouse_dir, "daily_prices")
        if prices.empty:
            return cls(close=pd.DataFrame(), open=pd.DataFrame())
        prices = prices.copy()
        prices["date"] = pd.to_datetime(prices["date"]).dt.tz_localize(None)
        prices["symbol"] = prices["symbol"].astype(str)
        prices["close"] = pd.to_numeric(prices["close"], errors="coerce")
        prices = prices.dropna(subset=["date", "symbol", "close"]).sort_values(["symbol", "date"])
        close = prices.pivot_table(
            index="date", columns="symbol", values="close", aggfunc="last"
        ).sort_index()
        if "open" in prices.columns:
            prices["open"] = pd.to_numeric(prices["open"], errors="coerce")
            open_pivot = (
                prices.pivot_table(index="date", columns="symbol", values="open", aggfunc="last")
                .reindex(index=close.index, columns=close.columns)
                .fillna(close)
            )
        else:
            open_pivot = close
        return cls(close=close, open=open_pivot)

    @property
    def is_empty(self) -> bool:
        return self.close.empty

    def trading_dates(self, start: date | None = None, end: date | None = None) -> list[date]:
        if self.close.empty:
            return []
        idx = self.close.index
        if start is not None:
            idx = idx[idx >= pd.Timestamp(start)]
        if end is not None:
            idx = idx[idx <= pd.Timestamp(end)]
        return [ts.date() for ts in idx]

    def close_on(self, day: date) -> dict[str, float]:
        """Closes available on ``day``. Symbols missing a close are omitted."""
        ts = pd.Timestamp(day)
        if self.close.empty or ts not in self.close.index:
            return {}
        row = self.close.loc[ts]
        return {sym: float(val) for sym, val in row.items() if pd.notna(val) and float(val) > 0}

    def asof(self, day: date, symbol: str) -> float | None:
        """Latest known close for ``symbol`` on or before ``day``."""
        if self.close.empty or symbol not in self.close.columns:
            return None
        ts = pd.Timestamp(day)
        col = self.close[symbol]
        slice_ = col.loc[col.index <= ts].dropna()
        if slice_.empty:
            return None
        last = slice_.iloc[-1]
        return float(last) if last > 0 else None

    def returns_window(
        self,
        start: date,
        end: date,
        symbols: Iterable[str],
    ) -> pd.DataFrame:
        """Daily simple returns over ``[start, end]`` for ``symbols``.

        Symbols missing entirely from the window are dropped from the output;
        the caller decides what to do with the survivors.
        """
        if self.close.empty:
            return pd.DataFrame()
        ts_start = pd.Timestamp(start)
        ts_end = pd.Timestamp(end)
        cols = [s for s in symbols if s in self.close.columns]
        if not cols:
            return pd.DataFrame()
        slice_ = self.close.loc[(self.close.index >= ts_start) & (self.close.index <= ts_end), cols].copy()
        if slice_.empty or len(slice_) < 2:
            return pd.DataFrame()
        rets = slice_.pct_change().replace([np.inf, -np.inf], np.nan).dropna(how="all")
        return rets.dropna(axis=1, how="all")

    def cumulative_return(self, start: date, end: date, symbol: str) -> float | None:
        """Realised total return between ``start`` and ``end`` (inclusive close
        anchors). Returns ``None`` when either anchor lacks a close."""
        anchor_start = self.asof(start, symbol)
        anchor_end = self.asof(end, symbol)
        if anchor_start is None or anchor_end is None or anchor_start <= 0:
            return None
        return anchor_end / anchor_start - 1.0

    def peak_return_after(self, start: date, end: date, symbol: str) -> float | None:
        """Maximum close/start - 1 over ``(start, end]``.

        Used by the prophet to score "best realised path after publication".
        Returns ``None`` if no future closes exist in the window.
        """
        if self.close.empty or symbol not in self.close.columns:
            return None
        anchor = self.asof(start, symbol)
        if anchor is None or anchor <= 0:
            return None
        ts_start = pd.Timestamp(start)
        ts_end = pd.Timestamp(end)
        col = self.close[symbol]
        future = col.loc[(col.index > ts_start) & (col.index <= ts_end)].dropna()
        if future.empty:
            return None
        peak = float(future.max())
        return peak / anchor - 1.0

    def peak_date_after(self, start: date, end: date, symbol: str) -> date | None:
        if self.close.empty or symbol not in self.close.columns:
            return None
        ts_start = pd.Timestamp(start)
        ts_end = pd.Timestamp(end)
        col = self.close[symbol]
        future = col.loc[(col.index > ts_start) & (col.index <= ts_end)].dropna()
        if future.empty:
            return None
        return future.idxmax().date()


# ---------------------------------------------------------------------------
# Benchmark loader (All-Weather basket).
# ---------------------------------------------------------------------------


_BENCHMARK_TABLE = "benchmark_prices"


def load_benchmark_prices(
    warehouse_dir: Path,
    symbols: Iterable[str],
    start: date,
    end: date,
    *,
    refresh: bool = False,
) -> PriceBoard:
    """Load KRW-converted closes for benchmark ETFs, downloading as needed.

    The result is cached at ``{warehouse_dir}/benchmark_prices.csv`` so
    repeated runs are network-free.
    """
    cached = read_table(warehouse_dir, _BENCHMARK_TABLE)
    needed = set(symbols)
    have = set(cached["symbol"].astype(str)) if not cached.empty else set()
    missing = needed - have
    if refresh or missing:
        frames: list[pd.DataFrame] = []
        for symbol in sorted(needed):
            if not refresh and symbol in have:
                continue
            history = download_history(
                symbol,
                datetime.combine(start, datetime.min.time(), tzinfo=UTC),
                datetime.combine(end + timedelta(days=1), datetime.min.time(), tzinfo=UTC),
            )
            if history.empty:
                continue
            history = history.copy()
            history["symbol"] = symbol
            frames.append(history)
        if frames:
            new_prices = pd.concat(frames, ignore_index=True)
            currencies = {_currency_for_benchmark_symbol(s) for s in symbols}
            fx = download_fx_rates(
                currencies,
                datetime.combine(start, datetime.min.time(), tzinfo=UTC),
                datetime.combine(end + timedelta(days=1), datetime.min.time(), tzinfo=UTC),
                download_history,
            )
            reports = pd.DataFrame(
                [{"symbol": s, "exchange": "KRX" if s.endswith(".KS") else "NYSE"} for s in symbols]
            )
            new_prices = apply_daily_price_krw_conversion(new_prices, reports, fx)
            if not cached.empty:
                cached = cached[~cached["symbol"].astype(str).isin([str(s) for s in needed])]
                cached = pd.concat([cached, new_prices], ignore_index=True)
            else:
                cached = new_prices
            write_table(warehouse_dir, _BENCHMARK_TABLE, cached)
    if cached.empty:
        return PriceBoard(close=pd.DataFrame(), open=pd.DataFrame())
    cached = cached.copy()
    cached["date"] = pd.to_datetime(cached["date"]).dt.tz_localize(None)
    cached["symbol"] = cached["symbol"].astype(str)
    cached["close"] = pd.to_numeric(cached["close"], errors="coerce")
    cached = cached.dropna(subset=["date", "symbol", "close"]).sort_values(["symbol", "date"])
    cached = cached[cached["symbol"].isin([str(s) for s in needed])]
    close = cached.pivot_table(index="date", columns="symbol", values="close", aggfunc="last").sort_index()
    if "open" in cached.columns:
        cached["open"] = pd.to_numeric(cached["open"], errors="coerce")
        open_pivot = (
            cached.pivot_table(index="date", columns="symbol", values="open", aggfunc="last")
            .reindex(index=close.index, columns=close.columns)
            .fillna(close)
        )
    else:
        open_pivot = close
    return PriceBoard(close=close, open=open_pivot)


def _currency_for_benchmark_symbol(symbol: str) -> str:
    """All-Weather defaults: yfinance ``.KS`` suffix → KRW; otherwise USD."""
    return "KRW" if symbol.endswith(".KS") else "USD"
