"""Typed schemas for JSON artifacts consumed by the web surfaces.

The backtest warehouse schemas cover CSV tables under ``data/warehouse``.
This module covers JSON artifacts such as ``price_metrics.json`` that are not
warehouse tables but still form a public data contract for Vercel/Pages.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict


class PriceMetricRow(BaseModel):
    """Row schema for ``data/price_metrics.json``.

    This artifact is the project-facing baseline-band contract: ``smic_follower_*``
    is the naive report-publication strategy, and ``oracle_*`` is the future-informed
    upper bound used to frame realistic strategy research.
    """

    model_config = ConfigDict(extra="forbid", title="PriceMetric")

    semantic_version: ClassVar[str] = "1.0"
    column_nan_policy: ClassVar[dict[str, str]] = {}

    title: str
    company: str
    display_name: str
    ticker: str
    yfinance_symbol: str
    price_currency: str
    target_currency: str
    display_currency: str
    publication_date: str
    publication_buy_price: float | None = None
    current_price: float | None = None
    target_price: float | None = None
    buy_at_publication_return: float | None = None
    publication_to_target_return: float | None = None
    oracle_entry_price: float | None = None
    oracle_exit_price: float | None = None
    oracle_return: float | None = None
    oracle_buy_lag_days: int | None = None
    oracle_holding_days: int | None = None
    smic_follower_entry_price: float | None = None
    smic_follower_exit_price: float | None = None
    smic_follower_return: float | None = None
    smic_follower_holding_days: int | None = None
    smic_follower_status: str
    lowest_price_since_publication: float | None = None
    lowest_price_current_return: float | None = None
    low_to_high_return: float | None = None
    low_to_high_holding_days: int | None = None
    q25_price_since_publication: float | None = None
    q25_price_current_return: float | None = None
    highest_price_since_publication: float | None = None
    highest_price_realized_return: float | None = None
    q75_price_since_publication: float | None = None
    q75_price_realized_return: float | None = None
    q75_price_current_return: float | None = None
    current_price_percentile: float | None = None
    target_upside_remaining: float | None = None
    optimal_buy_lag_days: int | None = None
    optimal_holding_days_net_10pct: int | None = None
    optimal_net_return_10pct: float | None = None
    target_hit: bool | None = None
    first_target_hit_date: str
    target_hit_holding_days: int | None = None
    status: str
    note: str


# Registry consumed by scripts/export_schemas.py + TS codegen. These are JSON
# artifact row schemas, not warehouse CSV tables, so warehouse.read/write_table
# intentionally do not use them.
ARTIFACT_MODELS: dict[str, type[BaseModel]] = {
    "price_metrics": PriceMetricRow,
}


def validate_price_metric_rows(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Validate and normalize ``price_metrics.json`` rows before writing.

    This keeps the web data artifact under the same explicit schema discipline as
    the CSV warehouse without forcing the quant computation code to depend on
    Pydantic models.
    """

    return [PriceMetricRow.model_validate(row).model_dump(mode="json") for row in rows]
