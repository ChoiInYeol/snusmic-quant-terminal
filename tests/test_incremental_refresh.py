"""Phase 3b — ``refresh_price_history`` must only fetch bars newer than the
last on-disk observation per symbol (plan AC #4).

The test passes a mock downloader that records every ``(symbol, start, end)``
invocation. The first call must hit the network for the full window; the
second call (with the warehouse already populated) must call the downloader
**zero times** for the existing symbols.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

from snusmic_pipeline.backtest.warehouse import refresh_price_history


def _seed_reports(warehouse: Path) -> pd.DataFrame:
    warehouse.mkdir(parents=True, exist_ok=True)
    reports = pd.DataFrame(
        [
            {
                "report_id": "r1",
                "publication_date": "2024-06-01",
                "title": "AAA report",
                "company": "AAA Co",
                "ticker": "AAA",
                "exchange": "KRX",
                "symbol": "AAA.KS",
                "target_price": 200.0,
                "report_current_price": 100.0,
            }
        ]
    )
    reports.to_csv(warehouse / "reports.csv", index=False)
    return reports


class _RecordingDownloader:
    def __init__(self) -> None:
        self.calls: list[tuple[str, datetime, datetime]] = []

    def __call__(self, symbol: str, start: datetime, end: datetime) -> pd.DataFrame:
        self.calls.append((symbol, start, end))
        # Return a minimal frame from start..end with one bar per business day.
        if "=" in symbol:
            # FX symbol — empty FX response is fine for this test.
            return pd.DataFrame()
        dates = pd.bdate_range(start.date(), end.date() - timedelta(days=1))
        if len(dates) == 0:
            return pd.DataFrame()
        rows = []
        for i, d in enumerate(dates):
            price = 100.0 + i * 0.5
            rows.append(
                {
                    "date": d.date().isoformat(),
                    "open": price * 0.998,
                    "high": price * 1.01,
                    "low": price * 0.99,
                    "close": price,
                    "volume": 1000,
                }
            )
        return pd.DataFrame(rows)


def test_second_refresh_with_no_new_bars_fetches_zero_times(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    warehouse = data_dir / "warehouse"
    _seed_reports(warehouse)
    downloader = _RecordingDownloader()
    now = datetime(2024, 7, 5)

    refresh_price_history(data_dir, warehouse, now=now, downloader=downloader, symbols=["AAA.KS"])
    first_round_equity_calls = [c for c in downloader.calls if c[0] == "AAA.KS"]
    assert first_round_equity_calls, "first refresh did not fetch the equity symbol at all"

    downloader.calls.clear()

    refresh_price_history(data_dir, warehouse, now=now, downloader=downloader, symbols=["AAA.KS"])
    equity_calls = [c for c in downloader.calls if c[0] == "AAA.KS"]
    assert equity_calls == [], (
        f"second refresh (no new bars) hit the network: {equity_calls} — "
        "incremental refresh regressed."
    )


def test_second_refresh_after_one_day_fetches_only_new_window(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    warehouse = data_dir / "warehouse"
    _seed_reports(warehouse)
    downloader = _RecordingDownloader()

    refresh_price_history(
        data_dir,
        warehouse,
        now=datetime(2024, 7, 5),
        downloader=downloader,
        symbols=["AAA.KS"],
    )
    downloader.calls.clear()

    # One business day later — refresh must hit the network for exactly one
    # bar (start = last_seen + 1 day) instead of the full ~820-day backfill.
    refresh_price_history(
        data_dir,
        warehouse,
        now=datetime(2024, 7, 8),
        downloader=downloader,
        symbols=["AAA.KS"],
    )
    equity_calls = [c for c in downloader.calls if c[0] == "AAA.KS"]
    assert len(equity_calls) == 1, equity_calls
    _, fetched_start, fetched_end = equity_calls[0]
    # The incremental window should be tight: at most a couple of weeks.
    span_days = (fetched_end - fetched_start).days
    assert span_days < 30, (
        f"incremental refresh fetched a {span_days}-day window — expected ≤ 30 days. "
        "If this is intentional (new universe member), use force_full=True."
    )


def test_force_full_flag_bypasses_incremental_path(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    warehouse = data_dir / "warehouse"
    _seed_reports(warehouse)
    downloader = _RecordingDownloader()

    refresh_price_history(data_dir, warehouse, now=datetime(2024, 7, 5), downloader=downloader, symbols=["AAA.KS"])
    downloader.calls.clear()

    refresh_price_history(
        data_dir,
        warehouse,
        now=datetime(2024, 7, 8),
        downloader=downloader,
        symbols=["AAA.KS"],
        force_full=True,
    )
    equity_calls = [c for c in downloader.calls if c[0] == "AAA.KS"]
    assert len(equity_calls) == 1
    _, fetched_start, fetched_end = equity_calls[0]
    span_days = (fetched_end - fetched_start).days
    assert span_days > 200, f"force_full should re-fetch the full window; got {span_days} days"
