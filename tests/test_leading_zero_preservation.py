from __future__ import annotations

from pathlib import Path

import pandas as pd

from snusmic_pipeline.backtest.warehouse import infer_yfinance_symbol, read_table, write_table


def _report_with_numeric_looking_ticker() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "report_id": "r-leading-zero",
                "publication_date": "2026-01-02",
                "title": "Leading Zero Coverage",
                "company": "Numeric Looking Ticker Co",
                "ticker": "000123",
                "exchange": "KRX",
                "symbol": "000123.KS",
            }
        ]
    )


def test_read_table_preserves_leading_zero_ticker_roundtrip(tmp_path: Path) -> None:
    write_table(tmp_path, "reports", _report_with_numeric_looking_ticker())

    read_back = read_table(tmp_path, "reports")

    assert read_back.loc[0, "ticker"] == "000123"
    assert infer_yfinance_symbol(read_back.loc[0, "ticker"], read_back.loc[0, "exchange"]) == "000123.KS"


def test_raw_read_csv_without_dtype_hint_loses_leading_zero_ticker(tmp_path: Path) -> None:
    write_table(tmp_path, "reports", _report_with_numeric_looking_ticker())

    raw = pd.read_csv(tmp_path / "reports.csv")

    assert raw.loc[0, "ticker"] == 123
    assert str(raw.loc[0, "ticker"]) == "123"
