import numpy as np
import pandas as pd

from snusmic_pipeline.quant import display_name_for_report, optimize_weights, pct_return, portfolio_expected_stats, realized_forward_return, yfinance_candidates
from snusmic_pipeline.models import ExtractedReport, ReportMeta


def make_report(ticker="005930", exchange="KRX"):
    return ExtractedReport(
        meta=ReportMeta(1, 1, "2026-01-01T00:00:00", "Equity Research, Test", "Test", "test", "http://post", "http://pdf"),
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
    expected_return, expected_volatility, expected_sharpe = portfolio_expected_stats(returns, np.array([0.5, 0.5]), 0.03)

    assert expected_return is not None
    assert expected_volatility is not None
    assert expected_sharpe is not None
