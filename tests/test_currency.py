from datetime import datetime

import pandas as pd

from snusmic_pipeline.currency import convert_ohlcv_to_krw, convert_value_to_krw, currency_for_symbol, download_fx_rates, yfinance_fx_symbol


def fake_downloader(symbol: str, start: datetime, end: datetime) -> pd.DataFrame:
    rates = {
        "KRW=X": [1300.0, 1310.0],
        "JPYKRW=X": [9.0, 9.1],
    }[symbol]
    return pd.DataFrame(
        {
            "date": ["2024-01-02", "2024-01-03"],
            "open": rates,
            "high": rates,
            "low": rates,
            "close": rates,
            "volume": [0, 0],
        }
    )


def test_yfinance_fx_symbols_match_requested_pairs():
    assert yfinance_fx_symbol("USD") == "KRW=X"
    assert yfinance_fx_symbol("JPY") == "JPYKRW=X"


def test_currency_for_symbol_uses_exchange_and_suffix():
    assert currency_for_symbol("306200.KS", "KRX") == "KRW"
    assert currency_for_symbol("6857.T", "TYO") == "JPY"
    assert currency_for_symbol("IRMD", "NASDAQ") == "USD"


def test_convert_foreign_prices_to_krw_with_asof_rates():
    fx = download_fx_rates({"USD", "JPY"}, datetime(2024, 1, 1), datetime(2024, 1, 5), fake_downloader)
    history = pd.DataFrame({"date": ["2024-01-03"], "open": [10.0], "high": [11.0], "low": [9.0], "close": [10.0], "volume": [100]})

    converted = convert_ohlcv_to_krw(history, "USD", fx)

    assert converted.iloc[0]["close"] == 13100.0
    assert convert_value_to_krw(100.0, "JPY", "2024-01-03", fx) == 910.0
