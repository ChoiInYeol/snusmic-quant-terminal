import numpy as np
import pandas as pd
import pytest

from snusmic_pipeline.models import ExtractedReport, ReportMeta
from snusmic_pipeline.quant import (
    compute_oracle_baseline,
    compute_smic_follower_baseline,
    compute_target_hit,
    display_name_for_report,
    optimize_weights,
    pct_return,
    portfolio_expected_stats,
    realized_forward_return,
    yfinance_candidates,
)


def make_report(ticker="005930", exchange="KRX"):
    return ExtractedReport(
        meta=ReportMeta(
            page=1,
            ordinal=1,
            date="2026-01-01T00:00:00",
            title="Equity Research, Test",
            company="Test",
            slug="test",
            post_url="http://post",
            pdf_url="http://pdf",
        ),
        pdf_path=None,
        ticker=ticker,
        exchange=exchange,
    )


def test_yfinance_candidates_for_korean_ticker():
    assert yfinance_candidates(make_report()) == ["005930.KS", "005930.KQ"]


def test_display_name_uses_company_for_numeric_tickers():
    assert display_name_for_report(make_report()) == "Test"
    assert display_name_for_report(make_report("IRMD", "NASDAQ")) == "IRMD"


def test_return_helpers():
    assert abs(pct_return(110, 100) - 0.1) < 1e-12
    prices = pd.DataFrame({"A": [100, 120], "B": [50, 55]})
    assert abs(realized_forward_return(prices, np.array([0.5, 0.5])) - 0.15) < 1e-12


def test_optimizer_returns_normalized_weights():
    returns = pd.DataFrame({"A": [0.01, 0.02, -0.01], "B": [0.0, 0.01, 0.01]})
    weights = optimize_weights(returns, "min_var", 0.03)

    assert abs(weights.sum() - 1) < 1e-9
    assert (weights >= 0).all()


def test_portfolio_expected_stats_has_return_risk_and_sharpe():
    returns = pd.DataFrame({"A": [0.01, 0.02, -0.01], "B": [0.0, 0.01, 0.01]})
    expected_return, expected_volatility, expected_sharpe = portfolio_expected_stats(
        returns, np.array([0.5, 0.5]), 0.03
    )

    assert expected_return is not None
    assert expected_volatility is not None
    assert expected_sharpe is not None


def test_price_metric_dataclass_exposes_low_high_fields():
    from snusmic_pipeline.quant import PriceMetric

    fields = PriceMetric.__dataclass_fields__
    assert "low_to_high_return" in fields
    assert "low_to_high_holding_days" in fields
    assert "q75_price_current_return" in fields
    assert "current_price_percentile" in fields
    assert "publication_to_target_return" in fields
    assert "oracle_entry_price" in fields
    assert "oracle_exit_price" in fields
    assert "oracle_return" in fields
    assert "oracle_buy_lag_days" in fields
    assert "oracle_holding_days" in fields
    assert "smic_follower_entry_price" in fields
    assert "smic_follower_exit_price" in fields
    assert "smic_follower_return" in fields
    assert "smic_follower_holding_days" in fields
    assert "smic_follower_status" in fields
    assert "target_hit_holding_days" in fields
    assert "target_upside_remaining" in fields


def test_baseline_band_synthetic_path_keeps_follower_below_oracle():
    """A simple report path should preserve the project invariant:
    SMIC follower <= oracle upper bound.

    This avoids yfinance/Optuna and locks the baseline-band semantics directly:
    follower buys at publication and exits at target, while oracle buys the
    later low and exits at the later high.
    """

    publication_day = pd.Timestamp("2024-01-01")
    close = pd.Series(
        [100.0, 80.0, 120.0, 150.0],
        index=pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04"]),
    )
    target = 120.0

    pub_price = float(close.iloc[0])
    hit_series = close[close >= target]
    first_hit_date = hit_series.index[0]
    low_idx = close.idxmin()
    post_low = close[close.index >= low_idx]
    best_after_low_idx = post_low.idxmax()

    smic_follower_return = pct_return(target, pub_price)
    oracle_return = pct_return(float(post_low.loc[best_after_low_idx]), float(close.loc[low_idx]))

    assert abs(smic_follower_return - 0.2) < 1e-12
    assert abs(oracle_return - 0.875) < 1e-12
    assert smic_follower_return <= oracle_return
    assert (first_hit_date - publication_day).days == 2
    assert (low_idx - publication_day).days == 1
    assert (best_after_low_idx - low_idx).days == 2


def test_oracle_baseline_uses_publication_or_later_prices_only():
    publication_day = pd.Timestamp("2024-01-01")
    close = pd.Series(
        [10.0, 100.0, 80.0, 150.0],
        index=pd.to_datetime(["2023-12-29", "2024-01-01", "2024-01-02", "2024-01-03"]),
    )

    oracle = compute_oracle_baseline(close[close.index >= publication_day], publication_day)

    assert oracle.entry_price == 80.0
    assert oracle.exit_price == 150.0
    assert oracle.return_ == pytest.approx(0.875)
    assert oracle.buy_lag_days == 1
    assert oracle.holding_days == 1


def test_smic_follower_exits_at_target_hit_or_latest_close():
    publication_day = pd.Timestamp("2024-01-01")
    close = pd.Series(
        [100.0, 110.0, 120.0, 115.0],
        index=pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04"]),
    )

    hit = compute_target_hit(close, 120.0)
    follower = compute_smic_follower_baseline(close, publication_day, 120.0, hit)

    assert hit.hit is True
    assert hit.first_hit_date == pd.Timestamp("2024-01-03")
    assert hit.holding_days == 2
    assert follower.exit_price == 120.0
    assert follower.return_ == pytest.approx(0.2)
    assert follower.status == "target_hit"

    miss = compute_target_hit(close, 130.0)
    open_follower = compute_smic_follower_baseline(close, publication_day, 130.0, miss)

    assert miss.hit is False
    assert open_follower.exit_price == 115.0
    assert open_follower.return_ == pytest.approx(0.15)
    assert open_follower.holding_days == 3
    assert open_follower.status == "open"


def test_target_hit_handles_missing_target_without_false_exit_signal():
    publication_day = pd.Timestamp("2024-01-01")
    close = pd.Series(
        [100.0, 110.0],
        index=pd.to_datetime(["2024-01-01", "2024-01-02"]),
    )

    hit = compute_target_hit(close, None)
    follower = compute_smic_follower_baseline(close, publication_day, None, hit)

    assert hit.hit is False
    assert hit.first_hit_date is None
    assert hit.holding_days is None
    assert follower.exit_price == 110.0
    assert follower.return_ == pytest.approx(0.1)
    assert follower.status == "open"
