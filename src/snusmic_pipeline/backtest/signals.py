from __future__ import annotations

import numpy as np
import pandas as pd


def _ols_log_slope_raw(values: np.ndarray) -> float:
    """OLS slope of ``log(values)`` against the in-window step index.

    Operates on a raw numpy array (``rolling(...).apply(raw=True)`` path)
    so pandas does not wrap each window in a Series — the per-cell overhead
    drops by an order of magnitude.

    NaN handling: drop NaN entries first (not their positions), then refuse
    to compute when the window has fewer than ``max(5, len(window)//2)``
    valid points or when any positive-value precondition for ``log`` fails.
    Matches the pre-Phase-3c per-symbol implementation byte-for-byte.
    """
    valid_mask = ~np.isnan(values)
    valid = values[valid_mask]
    if valid.size < max(5, values.size // 2):
        return float("nan")
    if (valid <= 0).any():
        return float("nan")
    x = np.arange(valid.size, dtype=np.float64)
    y = np.log(valid)
    return float(np.polyfit(x, y, 1)[0])


def compute_signals_daily(
    prices: pd.DataFrame,
    reports: pd.DataFrame,
    mtt_slope_months: int = 1,
    min_ma200_slope: float = 0.0,
) -> pd.DataFrame:
    """Compute MTT signals without using post-date data.

    Phase 3c — vectorised wide-form rewrite. The previous implementation
    iterated symbol-by-symbol via ``groupby``; this version pivots to a
    ``date × symbol`` wide frame, runs each rolling op once across all
    columns, and stacks the result back to the long form. Verified
    bit-identical against the per-symbol version on the Phase-2 integration
    fixture (see ``tests/test_signals_vectorisation_parity.py``).

    Phase 2b semantics for ``ma200_ols_log_slope`` and the ``min_ma200_slope``
    magnitude gate are preserved unchanged.
    """
    if prices.empty:
        return pd.DataFrame()
    frame = prices.copy()
    frame["date"] = pd.to_datetime(frame["date"])
    frame["symbol"] = frame["symbol"].astype(str)
    frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
    frame = frame.dropna(subset=["date", "symbol", "close"]).sort_values(["symbol", "date"])

    # Wide pivots — one cell per (date, symbol). ``aggfunc='last'`` matches
    # the legacy groupby semantics when multiple bars share a (date, symbol).
    wide_close = frame.pivot_table(index="date", columns="symbol", values="close", aggfunc="last").sort_index()

    slope_days = max(21, int(mtt_slope_months) * 21)
    slope_min_periods = max(5, slope_days // 2)

    ma50 = wide_close.rolling(50, min_periods=50).mean()
    ma150 = wide_close.rolling(150, min_periods=150).mean()
    ma200 = wide_close.rolling(200, min_periods=200).mean()
    low_52w = wide_close.rolling(252, min_periods=60).min()
    high_52w = wide_close.rolling(252, min_periods=60).max()
    pct_above_52w_low = wide_close / low_52w - 1.0
    pct_below_52w_high = wide_close / high_52w - 1.0

    ma200_ols_log_slope = ma200.rolling(slope_days, min_periods=slope_min_periods).apply(
        _ols_log_slope_raw, raw=True
    )
    ma200_slope_positive = ma200_ols_log_slope > min_ma200_slope

    mtt_pass = (
        (wide_close > ma150)
        & (wide_close > ma200)
        & (ma150 > ma200)
        & ma200_slope_positive
        & (ma50 > ma150)
        & (ma50 > ma200)
        & (wide_close > ma50)
        & (wide_close >= low_52w * 1.30)
        & (wide_close >= high_52w * 0.75)
    ).fillna(False)

    # Candidate universe activates on each symbol's first publication date.
    if not reports.empty:
        first_pub = pd.to_datetime(reports.groupby("symbol")["publication_date"].min())
    else:
        first_pub = pd.Series(dtype="datetime64[ns]")
    candidate_universe_active = pd.DataFrame(
        False, index=wide_close.index, columns=wide_close.columns
    )
    for symbol in wide_close.columns:
        cutoff = first_pub.get(symbol)
        if cutoff is not None and pd.notna(cutoff):
            candidate_universe_active[symbol] = wide_close.index >= cutoff

    # Melt back to long form with the legacy column order.
    def _to_long(df: pd.DataFrame, name: str) -> pd.DataFrame:
        # ``df.stack(future_stack=True)`` returns a Series at runtime when
        # ``df`` has a single column-level index (which is the case here);
        # pandas-stubs widens the return to ``DataFrame | Series`` so the
        # ``.reset_index()`` rename below is uniformly column-positional
        # rather than name-based to avoid touching ``.name`` on the union.
        out: pd.DataFrame = df.stack(future_stack=True).reset_index()  # type: ignore[union-attr]
        out.columns = ["date", "symbol", name]
        return out

    pieces = {
        "close": wide_close,
        "ma50": ma50,
        "ma150": ma150,
        "ma200": ma200,
        "ma200_slope_positive": ma200_slope_positive,
        "ma200_ols_log_slope": ma200_ols_log_slope,
        "low_52w": low_52w,
        "high_52w": high_52w,
        "pct_above_52w_low": pct_above_52w_low,
        "pct_below_52w_high": pct_below_52w_high,
        "candidate_universe_active": candidate_universe_active,
        "mtt_pass": mtt_pass,
    }
    long_pieces = [_to_long(df, name).set_index(["date", "symbol"]) for name, df in pieces.items()]
    result = pd.concat(long_pieces, axis=1).reset_index()
    # Drop rows that don't exist in the input (the wide pivot generates a row
    # for every (date, symbol) combination; restrict back to observed pairs).
    observed = frame[["date", "symbol"]].drop_duplicates()
    result = result.merge(observed, on=["date", "symbol"], how="inner")

    # Match the legacy column order so the integration SHA stays unchanged.
    return result[
        [
            "date",
            "symbol",
            "close",
            "ma50",
            "ma150",
            "ma200",
            "ma200_slope_positive",
            "ma200_ols_log_slope",
            "low_52w",
            "high_52w",
            "pct_above_52w_low",
            "pct_below_52w_high",
            "candidate_universe_active",
            "mtt_pass",
        ]
    ].sort_values(["symbol", "date"]).reset_index(drop=True)


def signal_lookup(signals: pd.DataFrame) -> dict[tuple[pd.Timestamp, str], dict]:
    if signals.empty:
        return {}
    rows = {}
    for item in signals.to_dict("records"):
        rows[(pd.Timestamp(item["date"]), str(item["symbol"]))] = item
    return rows
