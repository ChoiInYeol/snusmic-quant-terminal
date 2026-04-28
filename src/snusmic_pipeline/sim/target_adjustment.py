"""Helpers for putting report targets on the same price scale as market data."""

from __future__ import annotations

from datetime import date
from typing import Any, cast

import pandas as pd

from .market import PriceBoard

SPLIT_SCALE_THRESHOLD = 4.0
RAW_TARGET_PLAUSIBLE_MULTIPLE = 4.0


def coerce_positive_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if parsed != parsed or parsed <= 0:  # NaN or non-positive
        return None
    return parsed


def target_price_krw(record: dict[str, Any]) -> float | None:
    for key in ("target_price_krw", "target_price", "base_target_krw"):
        parsed = coerce_positive_float(record.get(key))
        if parsed is not None:
            return parsed
    return None


def market_scale_factor(
    record: dict[str, Any],
    board: PriceBoard,
    pub_day: date,
    end_day: date,
    *,
    threshold: float = SPLIT_SCALE_THRESHOLD,
) -> float:
    """Return target multiplier needed to align report quotes with market prices.

    SMIC reports quote targets in the price unit visible on publication day, but
    yfinance sometimes returns a post-split/post-spinoff scale for historical
    OHLC. When the first tradable close differs from the report's quoted current
    price by a very large factor, scale the target by the same market/report
    ratio. This keeps the return path on market-data units while preserving the
    report's intended upside.
    """
    quoted_close = coerce_positive_float(record.get("report_current_price_krw"))
    symbol = str(record.get("symbol") or "")
    if quoted_close is None or not symbol:
        return 1.0
    market_close = first_close_on_or_after(board, pub_day, end_day, symbol)
    if market_close is None:
        return 1.0

    target = target_price_krw(record)
    if target is not None:
        raw_target_multiple = target / market_close
        if 1 / RAW_TARGET_PLAUSIBLE_MULTIPLE <= raw_target_multiple <= RAW_TARGET_PLAUSIBLE_MULTIPLE:
            return 1.0

    ratio = market_close / quoted_close
    if ratio >= threshold or ratio <= 1 / threshold:
        return ratio
    return 1.0


def adjusted_target_price_krw(
    record: dict[str, Any],
    board: PriceBoard,
    pub_day: date,
    end_day: date,
) -> float | None:
    target = target_price_krw(record)
    if target is None:
        return None
    # ``align_report_targets_to_market_scale`` materializes the adjusted
    # target and records this factor. Do not apply the scale twice when a
    # prepared reports frame is passed into report-stat helpers.
    if "target_price_scale_factor" in record:
        return target
    return target * market_scale_factor(record, board, pub_day, end_day)


def first_close_on_or_after(board: PriceBoard, start: date, end: date, symbol: str) -> float | None:
    if board.is_empty or symbol not in board.close.columns:
        return None
    col = board.close[symbol]
    window = col.loc[(col.index >= pd.Timestamp(start)) & (col.index <= pd.Timestamp(end))].dropna()
    if window.empty:
        return None
    first = float(window.iloc[0])
    return first if first > 0 else None


def align_report_targets_to_market_scale(
    reports: pd.DataFrame, board: PriceBoard, end_day: date
) -> pd.DataFrame:
    """Return reports with target columns scaled to the warehouse price board.

    Adds ``target_price_scale_factor`` for diagnostics. The public simulation
    contracts keep using ``target_price_krw``; downstream target-hit and strategy
    logic therefore receives adjusted targets automatically.
    """
    if reports.empty:
        return reports
    frame = reports.copy()
    factors: list[float] = []
    targets: list[float | None] = []
    existing_target = (
        frame["target_price"]
        if "target_price" in frame.columns
        else pd.Series([pd.NA] * len(frame), index=frame.index)
    )
    for raw_record in frame.to_dict("records"):
        record = cast(dict[str, Any], raw_record)
        pub_raw = record.get("_pub") or record.get("publication_date")
        if pub_raw is None:
            factors.append(1.0)
            targets.append(target_price_krw(record))
            continue
        pub_day = pub_raw if isinstance(pub_raw, date) else pd.Timestamp(str(pub_raw)).date()
        factor = market_scale_factor(record, board, pub_day, end_day)
        target = target_price_krw(record)
        factors.append(factor)
        targets.append(target * factor if target is not None else None)
    frame["target_price_scale_factor"] = factors
    frame["target_price_krw"] = targets
    frame["target_price"] = frame["target_price_krw"].combine_first(existing_target)
    return frame
