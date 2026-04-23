from __future__ import annotations

import math
import contextlib
import io
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from .models import ExtractedReport

BENCHMARKS = {"KOSPI": "^KS11", "NASDAQ": "^IXIC"}
RISK_FREE_RATES = [0.03, 0.06, 0.08]


@dataclass(frozen=True)
class PriceMetric:
    title: str
    company: str
    display_name: str
    ticker: str
    yfinance_symbol: str
    publication_date: str
    publication_buy_price: float | None
    current_price: float | None
    buy_at_publication_return: float | None
    lowest_price_since_publication: float | None
    lowest_price_current_return: float | None
    low_to_high_return: float | None
    low_to_high_holding_days: int | None
    q25_price_since_publication: float | None
    q25_price_current_return: float | None
    highest_price_since_publication: float | None
    highest_price_realized_return: float | None
    q75_price_since_publication: float | None
    q75_price_realized_return: float | None
    q75_price_current_return: float | None
    current_price_percentile: float | None
    target_upside_remaining: float | None
    optimal_buy_lag_days: int | None
    optimal_holding_days_net_10pct: int | None
    optimal_net_return_10pct: float | None
    target_hit: bool | None
    first_target_hit_date: str
    status: str
    note: str


@dataclass(frozen=True)
class PortfolioResult:
    cohort_month: str
    rebalance_date: str
    strategy: str
    risk_free_rate: float
    symbols: str
    display_symbols: str
    weights: str
    expected_return: float | None
    expected_volatility: float | None
    expected_sharpe: float | None
    realized_return: float | None
    kospi_return: float | None
    nasdaq_return: float | None
    status: str


def yfinance_candidates(report: ExtractedReport) -> list[str]:
    ticker = report.ticker.strip().upper()
    if not ticker:
        return []
    if report.exchange == "KRX" and ticker.isdigit():
        return [f"{ticker}.KS", f"{ticker}.KQ"]
    if report.exchange == "TYO":
        return [f"{ticker}.T"]
    return [ticker]


def clean_report_title(title: str) -> str:
    return title.replace("Equity Research,", "").strip()


def display_name_for_report(report: ExtractedReport) -> str:
    if report.exchange in {"KRX", "TYO"}:
        return report.meta.company or clean_report_title(report.meta.title)
    return report.ticker or report.meta.company or clean_report_title(report.meta.title)


def _download_history(symbol: str, start: datetime, end: datetime) -> pd.DataFrame:
    import yfinance as yf

    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        data = yf.download(symbol, start=start.date().isoformat(), end=end.date().isoformat(), progress=False, auto_adjust=True, threads=False)
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    if "Close" not in data:
        return pd.DataFrame()
    data = data.dropna(subset=["Close"]).copy()
    data.index = pd.to_datetime(data.index).tz_localize(None)
    return data


def resolve_yfinance_symbol(report: ExtractedReport, start: datetime, end: datetime) -> tuple[str, pd.DataFrame]:
    candidates = yfinance_candidates(report)
    best_symbol = ""
    best_data = pd.DataFrame()
    best_score = math.inf
    for symbol in candidates:
        data = _download_history(symbol, start, end)
        if data.empty:
            continue
        score = 0.0
        if report.report_current_price:
            around = data[data.index >= pd.to_datetime(report.meta.date[:10])]
            if not around.empty:
                score = abs(float(around["Close"].iloc[0]) - report.report_current_price)
        if score < best_score:
            best_score = score
            best_symbol = symbol
            best_data = data
    return best_symbol, best_data


def pct_return(sell: float | None, buy: float | None) -> float | None:
    if sell is None or buy in (None, 0):
        return None
    return sell / buy - 1


def optimal_net_holding(close: pd.Series, annual_cost: float = 0.10) -> tuple[int | None, float | None]:
    values = close.to_numpy(dtype=float)
    if len(values) < 2:
        return None, None
    best_return = -math.inf
    best_days = 0
    for buy_idx in range(len(values) - 1):
        future = values[buy_idx + 1 :]
        sell_offset = int(np.argmax(future)) + 1
        sell_idx = buy_idx + sell_offset
        days = max(1, (close.index[sell_idx] - close.index[buy_idx]).days)
        gross = values[sell_idx] / values[buy_idx] - 1
        net = gross - annual_cost * days / 365
        if net > best_return:
            best_return = float(net)
            best_days = days
    return best_days, best_return if best_return > -math.inf else None


def compute_price_metrics(reports: list[ExtractedReport], now: datetime | None = None) -> list[PriceMetric]:
    now = now or datetime.now(timezone.utc)
    metrics: list[PriceMetric] = []
    for report in reports:
        publication = datetime.fromisoformat(report.meta.date[:10])
        start = publication - timedelta(days=10)
        end = now + timedelta(days=1)
        symbol, history = resolve_yfinance_symbol(report, start, end)
        if not symbol or history.empty:
            metrics.append(
                PriceMetric(report.meta.title, report.meta.company, display_name_for_report(report), report.ticker, symbol, report.meta.date[:10], None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, False, "", "no_price_history", "No yfinance history")
            )
            continue
        post = history[history.index >= pd.to_datetime(report.meta.date[:10])].copy()
        if post.empty:
            metrics.append(
                PriceMetric(report.meta.title, report.meta.company, display_name_for_report(report), report.ticker, symbol, report.meta.date[:10], None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, False, "", "no_post_publication_prices", "")
            )
            continue
        close = post["Close"].dropna()
        pub_price = float(close.iloc[0])
        current = float(close.iloc[-1])
        low_idx = close.idxmin()
        high_idx = close.idxmax()
        low = float(close.loc[low_idx])
        high = float(close.loc[high_idx])
        post_low = close[close.index >= low_idx]
        best_after_low_idx = post_low.idxmax()
        best_after_low = float(post_low.loc[best_after_low_idx])
        q25 = float(close.quantile(0.25))
        q75 = float(close.quantile(0.75))
        target = report.base_target
        hit_series = close[close >= target] if target else pd.Series(dtype=float)
        holding_days, net_return = optimal_net_holding(close)
        low_to_high_holding_days = (best_after_low_idx - low_idx).days
        current_percentile = float((close <= current).mean())
        metrics.append(
            PriceMetric(
                title=report.meta.title,
                company=report.meta.company,
                display_name=display_name_for_report(report),
                ticker=report.ticker,
                yfinance_symbol=symbol,
                publication_date=report.meta.date[:10],
                publication_buy_price=pub_price,
                current_price=current,
                buy_at_publication_return=pct_return(current, pub_price),
                lowest_price_since_publication=low,
                lowest_price_current_return=pct_return(current, low),
                low_to_high_return=pct_return(best_after_low, low),
                low_to_high_holding_days=low_to_high_holding_days,
                q25_price_since_publication=q25,
                q25_price_current_return=pct_return(current, q25),
                highest_price_since_publication=high,
                highest_price_realized_return=pct_return(high, pub_price),
                q75_price_since_publication=q75,
                q75_price_realized_return=pct_return(q75, pub_price),
                q75_price_current_return=pct_return(current, q75),
                current_price_percentile=current_percentile,
                target_upside_remaining=pct_return(target, current) if target else None,
                optimal_buy_lag_days=(low_idx - pd.to_datetime(report.meta.date[:10])).days,
                optimal_holding_days_net_10pct=holding_days,
                optimal_net_return_10pct=net_return,
                target_hit=bool(not hit_series.empty),
                first_target_hit_date="" if hit_series.empty else hit_series.index[0].date().isoformat(),
                status="ok",
                note="",
            )
        )
    return metrics


def _annualized_returns(returns: pd.DataFrame) -> pd.Series:
    return returns.mean() * 252


def _annualized_cov(returns: pd.DataFrame) -> pd.DataFrame:
    return returns.cov() * 252


def _normalize(weights: np.ndarray) -> np.ndarray:
    weights = np.maximum(weights, 0)
    total = weights.sum()
    if total <= 0:
        return np.ones_like(weights) / len(weights)
    return weights / total


def optimize_weights(returns: pd.DataFrame, strategy: str, risk_free_rate: float) -> np.ndarray:
    n = returns.shape[1]
    if n == 0:
        return np.array([])
    if n == 1 or strategy == "1/N":
        return np.ones(n) / n
    mean = _annualized_returns(returns).to_numpy(dtype=float)
    cov = _annualized_cov(returns).to_numpy(dtype=float)
    if strategy == "momentum":
        momentum = (1 + returns).prod().to_numpy(dtype=float) - 1
        return _normalize(momentum)
    if strategy == "max_return":
        weights = np.zeros(n)
        weights[int(np.argmax(mean))] = 1
        return weights
    bounds = [(0, 1)] * n
    constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1}]
    init = np.ones(n) / n

    def variance(w: np.ndarray) -> float:
        return float(w @ cov @ w)

    def sharpe_loss(w: np.ndarray) -> float:
        vol = math.sqrt(max(variance(w), 1e-12))
        return -float((w @ mean - risk_free_rate) / vol)

    def sortino_loss(w: np.ndarray) -> float:
        port = returns.to_numpy(dtype=float) @ w
        downside = port[port < 0]
        down_vol = np.std(downside) * math.sqrt(252) if len(downside) else 1e-6
        return -float((w @ mean - risk_free_rate) / max(down_vol, 1e-6))

    def calmar_loss(w: np.ndarray) -> float:
        port = pd.Series(returns.to_numpy(dtype=float) @ w, index=returns.index)
        equity = (1 + port).cumprod()
        drawdown = equity / equity.cummax() - 1
        max_dd = abs(float(drawdown.min()))
        return -float((w @ mean - risk_free_rate) / max(max_dd, 1e-6))

    objective = {
        "min_var": variance,
        "max_sharpe": sharpe_loss,
        "sortino": sortino_loss,
        "calmar": calmar_loss,
    }.get(strategy, sharpe_loss)
    result = minimize(objective, init, method="SLSQP", bounds=bounds, constraints=constraints)
    return _normalize(result.x if result.success else init)


def realized_forward_return(price_frame: pd.DataFrame, weights: np.ndarray) -> float | None:
    if price_frame.empty or len(weights) == 0:
        return None
    first = price_frame.iloc[0].to_numpy(dtype=float)
    last = price_frame.iloc[-1].to_numpy(dtype=float)
    valid = np.isfinite(first) & np.isfinite(last) & (first != 0)
    if not valid.any():
        return None
    w = _normalize(weights[valid])
    returns = last[valid] / first[valid] - 1
    return float(w @ returns)


def portfolio_expected_stats(returns: pd.DataFrame, weights: np.ndarray, risk_free_rate: float) -> tuple[float | None, float | None, float | None]:
    if returns.empty or len(weights) == 0:
        return None, None, None
    mean = _annualized_returns(returns).to_numpy(dtype=float)
    cov = _annualized_cov(returns).to_numpy(dtype=float)
    expected_return = float(weights @ mean)
    expected_volatility = math.sqrt(max(float(weights @ cov @ weights), 0.0))
    expected_sharpe = None if expected_volatility == 0 else (expected_return - risk_free_rate) / expected_volatility
    return expected_return, expected_volatility, expected_sharpe


def compute_portfolio_backtests(reports: list[ExtractedReport], price_metrics: list[PriceMetric], now: datetime | None = None) -> list[PortfolioResult]:
    now = now or datetime.now(timezone.utc)
    by_title = {metric.title: metric for metric in price_metrics if metric.status == "ok" and metric.yfinance_symbol}
    display_by_symbol = {metric.yfinance_symbol: metric.display_name for metric in price_metrics if metric.yfinance_symbol}
    rows: list[PortfolioResult] = []
    frame_rows = []
    for report in reports:
        metric = by_title.get(report.meta.title)
        if metric:
            frame_rows.append({"month": report.meta.date[:7], "date": report.meta.date[:10], "symbol": metric.yfinance_symbol})
    if not frame_rows:
        return rows
    cohorts = pd.DataFrame(frame_rows).groupby("month")
    for month, cohort in cohorts:
        symbols = sorted(set(cohort["symbol"]))
        if not symbols:
            continue
        last_report_date = pd.to_datetime(cohort["date"].max())
        rebalance = last_report_date + pd.Timedelta(days=1)
        lookback_start = rebalance - pd.Timedelta(days=730)
        end = pd.Timestamp(now.date()) + pd.Timedelta(days=1)
        prices = {}
        for symbol in symbols:
            hist = _download_history(symbol, lookback_start.to_pydatetime(), end.to_pydatetime())
            if not hist.empty:
                prices[symbol] = hist["Close"]
        if not prices:
            continue
        price_frame = pd.DataFrame(prices).dropna(how="all").ffill().dropna(axis=1)
        lookback = price_frame[price_frame.index < rebalance]
        forward = price_frame[price_frame.index >= rebalance]
        if lookback.shape[0] < 60 or forward.empty:
            continue
        benchmark_returns = {}
        for name, symbol in BENCHMARKS.items():
            benchmark_history = _download_history(symbol, forward.index[0].to_pydatetime(), end.to_pydatetime())
            benchmark_returns[name] = None if benchmark_history.empty else pct_return(float(benchmark_history["Close"].iloc[-1]), float(benchmark_history["Close"].iloc[0]))
        returns = lookback.pct_change().dropna()
        for rf in RISK_FREE_RATES:
            for strategy in ["1/N", "momentum", "max_sharpe", "sortino", "max_return", "min_var", "calmar"]:
                weights = optimize_weights(returns, strategy, rf)
                expected_return, expected_volatility, expected_sharpe = portfolio_expected_stats(returns, weights, rf)
                rows.append(
                    PortfolioResult(
                        cohort_month=str(month),
                        rebalance_date=forward.index[0].date().isoformat(),
                        strategy=strategy,
                        risk_free_rate=rf,
                        symbols=",".join(returns.columns),
                        display_symbols=",".join(display_by_symbol.get(symbol, symbol) for symbol in returns.columns),
                        weights=",".join(f"{w:.4f}" for w in weights),
                        expected_return=expected_return,
                        expected_volatility=expected_volatility,
                        expected_sharpe=expected_sharpe,
                        realized_return=realized_forward_return(forward[returns.columns], weights),
                        kospi_return=benchmark_returns.get("KOSPI"),
                        nasdaq_return=benchmark_returns.get("NASDAQ"),
                        status="ok",
                    )
                )
    return rows


def dataclass_rows(items: Iterable[object]) -> list[dict]:
    return [asdict(item) for item in items]
