from datetime import date

import pandas as pd

from snusmic_pipeline.sim.market import PriceBoard
from snusmic_pipeline.sim.report_stats import compute_report_performance


def test_upside_target_hit_uses_intraday_high_touch():
    board = PriceBoard(
        close=pd.DataFrame({"A": [100.0, 120.0]}, index=pd.to_datetime(["2024-01-02", "2024-01-03"])),
        open=pd.DataFrame({"A": [100.0, 100.0]}, index=pd.to_datetime(["2024-01-02", "2024-01-03"])),
        high=pd.DataFrame({"A": [100.0, 151.0]}, index=pd.to_datetime(["2024-01-02", "2024-01-03"])),
        low=pd.DataFrame({"A": [100.0, 99.0]}, index=pd.to_datetime(["2024-01-02", "2024-01-03"])),
    )
    reports = pd.DataFrame(
        [
            {
                "report_id": "r1",
                "symbol": "A",
                "company": "A",
                "publication_date": "2024-01-02",
                "target_price_krw": 150.0,
            }
        ]
    )

    [perf] = compute_report_performance(reports, board, date(2024, 1, 3))

    assert perf.target_hit is True
    assert perf.target_hit_date == date(2024, 1, 3)


def test_downside_target_hit_uses_intraday_low_touch():
    board = PriceBoard(
        close=pd.DataFrame({"A": [100.0, 90.0]}, index=pd.to_datetime(["2024-01-02", "2024-01-03"])),
        open=pd.DataFrame({"A": [100.0, 100.0]}, index=pd.to_datetime(["2024-01-02", "2024-01-03"])),
        high=pd.DataFrame({"A": [100.0, 101.0]}, index=pd.to_datetime(["2024-01-02", "2024-01-03"])),
        low=pd.DataFrame({"A": [100.0, 79.0]}, index=pd.to_datetime(["2024-01-02", "2024-01-03"])),
    )
    reports = pd.DataFrame(
        [
            {
                "report_id": "r1",
                "symbol": "A",
                "company": "A",
                "publication_date": "2024-01-02",
                "target_price_krw": 80.0,
            }
        ]
    )

    [perf] = compute_report_performance(reports, board, date(2024, 1, 3))

    assert perf.target_hit is True
    assert perf.target_hit_date == date(2024, 1, 3)
