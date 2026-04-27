"""Typed table schemas for the sim warehouse.

Every model here is a Pydantic v2 `BaseModel` with `extra='forbid'`. Models
exposed in :data:`TABLE_MODELS` are used by :mod:`snusmic_pipeline.sim.warehouse`
to validate rows at both read AND write boundaries.

Column-level ClassVar metadata (``semantic_version``, ``nan_policy``) is read
by :mod:`scripts.export_schemas` and :mod:`scripts.check_schema_compat` to enforce
schema additivity ("additive AND semantics-preserving within a minor version").
"""

from __future__ import annotations

from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict

# ---------------------------------------------------------------------------
# Table row models — consumed by warehouse.{read_table,write_table} via TABLE_MODELS.
# Column order here MUST match the CSV column order on disk.
# ---------------------------------------------------------------------------


class DailyPrice(BaseModel):
    """Row schema for ``data/warehouse/daily_prices.csv``."""

    model_config = ConfigDict(extra="forbid")

    semantic_version: ClassVar[str] = "1.0"
    column_nan_policy: ClassVar[dict[str, str]] = {
        "close": "forward_fill_then_flag",
        "open": "drop",
        "high": "drop",
        "low": "drop",
        "volume": "drop",
    }

    date: str
    symbol: str
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    volume: float | None = None
    source_currency: str | None = None
    display_currency: str | None = None
    krw_per_unit: float | None = None


class ReportRow(BaseModel):
    """Row schema for ``data/warehouse/reports.csv``."""

    model_config = ConfigDict(extra="forbid")

    semantic_version: ClassVar[str] = "1.0"
    column_nan_policy: ClassVar[dict[str, str]] = {}

    report_id: str
    page: int | None = None
    ordinal: int | None = None
    publication_date: str
    title: str
    company: str
    ticker: str
    exchange: str
    symbol: str
    pdf_filename: str | None = None
    pdf_url: str | None = None
    report_current_price: float | None = None
    bear_target: float | None = None
    base_target: float | None = None
    bull_target: float | None = None
    target_price_local: float | None = None
    target_price: float | None = None
    target_currency: str | None = None
    price_currency: str | None = None
    display_currency: str | None = None
    markdown_filename: str | None = None
    report_current_price_krw: float | None = None
    bear_target_krw: float | None = None
    base_target_krw: float | None = None
    bull_target_krw: float | None = None
    target_price_krw: float | None = None


# Registry consumed by warehouse.write_table / read_table + scripts/export_schemas.py.
TABLE_MODELS: dict[str, type[BaseModel]] = {
    "daily_prices": DailyPrice,
    "reports": ReportRow,
}

# Pandas must read identifier-like string columns as text before Pydantic sees
# them. Without these hints, values such as KRX ticker "000999" can be inferred
# as integer 999, permanently losing leading zeros before validation.
TABLE_DTYPES: dict[str, dict[str, str]] = {
    "daily_prices": {
        "date": "str",
        "symbol": "str",
        "source_currency": "str",
        "display_currency": "str",
    },
    "reports": {
        "report_id": "str",
        "publication_date": "str",
        "title": "str",
        "company": "str",
        "ticker": "str",
        "exchange": "str",
        "symbol": "str",
        "pdf_filename": "str",
        "pdf_url": "str",
        "target_currency": "str",
        "price_currency": "str",
        "display_currency": "str",
        "markdown_filename": "str",
    },
}


def dataclass_rows(items: list[BaseModel]) -> list[dict[str, Any]]:
    """Back-compat helper. Returns each model dumped as a JSON-mode dict."""
    return [item.model_dump(mode="json") for item in items]
