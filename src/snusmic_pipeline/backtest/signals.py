from __future__ import annotations

import pandas as pd


RS_WINDOWS = [(252, 0.20), (126, 0.30), (63, 0.30), (21, 0.20)]


def compute_signals_daily(
    prices: pd.DataFrame,
    reports: pd.DataFrame,
    mtt_slope_months: int = 1,
) -> pd.DataFrame:
    """Compute MTT and candidate-universe RS scores without future data."""
    if prices.empty:
        return pd.DataFrame()
    frame = prices.copy()
    frame["date"] = pd.to_datetime(frame["date"])
    frame = frame.sort_values(["symbol", "date"])
    first_pub = reports.groupby("symbol")["publication_date"].min()
    first_pub = pd.to_datetime(first_pub)
    rows: list[pd.DataFrame] = []
    slope_days = max(21, int(mtt_slope_months) * 21)
    for symbol, group in frame.groupby("symbol", sort=False):
        group = group.sort_values("date").copy()
        close = group["close"].astype(float)
        group["ma50"] = close.rolling(50, min_periods=50).mean()
        group["ma150"] = close.rolling(150, min_periods=150).mean()
        group["ma200"] = close.rolling(200, min_periods=200).mean()
        group["ma200_slope_positive"] = group["ma200"].diff(slope_days) > 0
        group["low_52w"] = close.rolling(252, min_periods=60).min()
        group["high_52w"] = close.rolling(252, min_periods=60).max()
        group["pct_above_52w_low"] = close / group["low_52w"] - 1.0
        group["pct_below_52w_high"] = close / group["high_52w"] - 1.0
        group["mtt_pass"] = (
            (close > group["ma150"])
            & (close > group["ma200"])
            & (group["ma150"] > group["ma200"])
            & group["ma200_slope_positive"]
            & (group["ma50"] > group["ma150"])
            & (group["ma50"] > group["ma200"])
            & (close > group["ma50"])
            & (close >= group["low_52w"] * 1.30)
            & (close >= group["high_52w"] * 0.75)
        ).fillna(False)
        weighted = pd.Series(0.0, index=group.index)
        valid_parts = pd.Series(0.0, index=group.index)
        for days, weight in RS_WINDOWS:
            returns = close / close.shift(days) - 1.0
            weighted = weighted + returns.fillna(0.0) * weight
            valid_parts = valid_parts + returns.notna().astype(float) * weight
        group["rs_weighted_return"] = weighted.where(valid_parts > 0)
        group["candidate_universe_active"] = False
        if symbol in first_pub:
            group["candidate_universe_active"] = group["date"] >= first_pub[symbol]
        rows.append(group)
    result = pd.concat(rows, ignore_index=True)
    result["rs_score"] = pd.NA
    active = result["candidate_universe_active"] & result["rs_weighted_return"].notna()
    if active.any():
        ranked = result.loc[active].groupby("date")["rs_weighted_return"].rank(pct=True)
        result.loc[active, "rs_score"] = (ranked * 99).clip(lower=1, upper=99).round(1)
    return result[
        [
            "date",
            "symbol",
            "close",
            "ma50",
            "ma150",
            "ma200",
            "ma200_slope_positive",
            "low_52w",
            "high_52w",
            "pct_above_52w_low",
            "pct_below_52w_high",
            "rs_weighted_return",
            "rs_score",
            "candidate_universe_active",
            "mtt_pass",
        ]
    ].copy()


def signal_lookup(signals: pd.DataFrame) -> dict[tuple[pd.Timestamp, str], dict]:
    if signals.empty:
        return {}
    rows = {}
    for item in signals.to_dict("records"):
        rows[(pd.Timestamp(item["date"]), str(item["symbol"]))] = item
    return rows
