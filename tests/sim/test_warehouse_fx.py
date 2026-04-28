import pandas as pd

from snusmic_pipeline.sim.warehouse import apply_daily_price_krw_conversion


def test_partial_incremental_fx_rows_are_converted_without_double_converting_existing_rows():
    prices = pd.DataFrame(
        [
            {
                "date": "2026-04-24",
                "symbol": "ROKU",
                "open": 170000.0,
                "high": 171000.0,
                "low": 169000.0,
                "close": 170500.0,
                "display_currency": "KRW",
                "source_currency": "USD",
                "krw_per_unit": 1475.0,
            },
            {
                "date": "2026-04-27",
                "symbol": "ROKU",
                "open": 100.0,
                "high": 110.0,
                "low": 90.0,
                "close": 105.0,
                "display_currency": "",
                "source_currency": "",
                "krw_per_unit": "",
            },
        ]
    )
    reports = pd.DataFrame([{"symbol": "ROKU", "exchange": "NASDAQ"}])
    fx_rates = pd.DataFrame(
        [
            {"date": "2026-04-24", "currency": "USD", "krw_per_unit": 1475.0},
            {"date": "2026-04-27", "currency": "USD", "krw_per_unit": 1480.0},
        ]
    )

    converted = apply_daily_price_krw_conversion(prices, reports, fx_rates).sort_values("date")

    assert converted.iloc[0]["close"] == 170500.0
    assert converted.iloc[1]["close"] == 105.0 * 1480.0
    assert converted.iloc[1]["display_currency"] == "KRW"
    assert converted.iloc[1]["krw_per_unit"] == 1480.0
