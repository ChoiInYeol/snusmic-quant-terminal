"""Phase 1a AC #6 — ``write_table`` rejects rows that violate the table model.

This is the write-side half of Principle 2 (typed SSOT at both boundaries).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from pydantic import ValidationError

from snusmic_pipeline.backtest.warehouse import write_table


def _minimal_daily_prices() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "date": "2025-01-02",
                "symbol": "005930.KS",
                "open": 70000.0,
                "high": 71000.0,
                "low": 69500.0,
                "close": 70500.0,
                "volume": 1234567.0,
                "source_currency": "KRW",
                "display_currency": "KRW",
                "krw_per_unit": 1.0,
            }
        ]
    )


def test_write_table_accepts_valid_rows(tmp_path: Path) -> None:
    write_table(tmp_path, "daily_prices", _minimal_daily_prices())
    assert (tmp_path / "daily_prices.csv").exists()


def test_write_table_rejects_missing_required_column(tmp_path: Path) -> None:
    bad = _minimal_daily_prices().drop(columns=["date"])
    with pytest.raises(ValidationError):
        write_table(tmp_path, "daily_prices", bad)


def test_write_table_rejects_unknown_column(tmp_path: Path) -> None:
    bad = _minimal_daily_prices()
    bad["unexpected_column"] = "oops"
    with pytest.raises(ValidationError):
        write_table(tmp_path, "daily_prices", bad)


def test_write_table_rejects_type_mismatch(tmp_path: Path) -> None:
    bad = _minimal_daily_prices()
    # `close` is typed Optional[float]; a non-numeric str should not coerce.
    # Force the column to object dtype so pandas doesn't reject the str upcast
    # at assignment time — the validation must happen inside write_table.
    bad["close"] = bad["close"].astype(object)
    bad.loc[0, "close"] = "not_a_number"
    with pytest.raises(ValidationError):
        write_table(tmp_path, "daily_prices", bad)


def test_write_table_feature_flag_escape(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Pre-mortem Scenario 1: SNUSMIC_USE_PYDANTIC_V2=0 bypasses validation."""
    monkeypatch.setenv("SNUSMIC_USE_PYDANTIC_V2", "0")
    bad = _minimal_daily_prices()
    bad["unexpected_column"] = "oops"  # would raise under v2
    write_table(tmp_path, "daily_prices", bad)
    # File exists despite extra column — legacy path skipped validation.
    assert (tmp_path / "daily_prices.csv").exists()


def test_write_table_skips_unknown_table(tmp_path: Path) -> None:
    """Tables not in TABLE_MODELS (e.g. fx_rates, positions_daily) are written
    without validation for now — those migrate in later phases."""
    write_table(
        tmp_path,
        "fx_rates",
        pd.DataFrame(
            [{"date": "2025-01-02", "currency": "USD", "fx_symbol": "USDKRW=X", "krw_per_unit": 1300.0}]
        ),
    )
    assert (tmp_path / "fx_rates.csv").exists()
