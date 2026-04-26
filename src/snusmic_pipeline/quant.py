from __future__ import annotations

import contextlib
import io
import math
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from .currency import (
    convert_ohlcv_to_krw,
    convert_value_to_krw,
    currency_for_symbol,
    download_fx_rates,
    normalize_currency,
)
from .models import ExtractedReport

BENCHMARKS = {"KOSPI": "^KS11", "NASDAQ": "^IXIC"}
RISK_FREE_RATES = [0.03, 0.06, 0.08]
SCENARIO_INITIAL_CAPITAL_KRW = 10_000_000.0
SCENARIO_MONTHLY_CONTRIBUTION_KRW = 1_000_000.0


@dataclass(frozen=True)
class PriceMetric:
    title: str
    company: str
    display_name: str
    ticker: str
    yfinance_symbol: str
    price_currency: str
    target_currency: str
    display_currency: str
    publication_date: str
    publication_buy_price: float | None
    current_price: float | None
    target_price: float | None
    buy_at_publication_return: float | None
    publication_to_target_return: float | None
    # Explicit baseline aliases for the project goal:
    # - oracle_* is the future-informed upper bound over this report's price path.
    # - smic_follower_* is the naive report-publication-to-target baseline.
    oracle_entry_price: float | None
    oracle_exit_price: float | None
    oracle_return: float | None
    oracle_buy_lag_days: int | None
    oracle_holding_days: int | None
    smic_follower_entry_price: float | None
    smic_follower_exit_price: float | None
    smic_follower_return: float | None
    smic_follower_holding_days: int | None
    smic_follower_status: str
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
    target_hit_holding_days: int | None
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
    initial_capital_krw: float
    monthly_contribution_krw: float
    contribution_months: int
    total_contributed_krw: float
    final_value_krw: float | None
    money_weighted_return: float | None
    cash_weight: float
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
    if report.exchange in {"HKG", "HKEX"}:
        return [f"{ticker}.HK"]
    if report.exchange == "SZSE":
        return [f"{ticker}.SZ"]
    if report.exchange == "SSE":
        return [f"{ticker}.SS"]
    if report.exchange == "EPA":
        return [f"{ticker}.PA"]
    if report.exchange == "AMS":
        return [f"{ticker}.AS"]
    if report.exchange == "SIX":
        return [f"{ticker}.SW"]
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
        data = yf.download(
            symbol,
            start=start.date().isoformat(),
            end=end.date().isoformat(),
            progress=False,
            auto_adjust=True,
            threads=False,
            timeout=10,
        )
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    if "Close" not in data:
        return pd.DataFrame()
    data = data.dropna(subset=["Close"]).copy()
    data.index = pd.to_datetime(data.index).tz_localize(None)
    return data


def _download_histories(
    symbols: Iterable[str], start: datetime, end: datetime, chunk_size: int = 80
) -> dict[str, pd.DataFrame]:
    import yfinance as yf

    unique_symbols = [symbol for symbol in dict.fromkeys(str(item) for item in symbols if item)]
    histories: dict[str, pd.DataFrame] = {symbol: pd.DataFrame() for symbol in unique_symbols}
    for offset in range(0, len(unique_symbols), chunk_size):
        chunk = unique_symbols[offset : offset + chunk_size]
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            data = yf.download(
                chunk,
                start=start.date().isoformat(),
                end=end.date().isoformat(),
                progress=False,
                auto_adjust=True,
                threads=True,
                group_by="ticker",
                timeout=15,
            )
        if data.empty:
            continue
        for symbol in chunk:
            frame = _extract_symbol_frame(data, symbol)
            if frame.empty or "Close" not in frame:
                continue
            frame = frame.dropna(subset=["Close"]).copy()
            frame.index = pd.to_datetime(frame.index).tz_localize(None)
            histories[symbol] = frame
    return histories


def _extract_symbol_frame(data: pd.DataFrame, symbol: str) -> pd.DataFrame:
    if not isinstance(data.columns, pd.MultiIndex):
        return data.copy()
    if symbol in data.columns.get_level_values(0):
        return data[symbol].copy()
    if symbol in data.columns.get_level_values(1):
        return data.xs(symbol, axis=1, level=1).copy()
    return pd.DataFrame()


def _history_to_ohlcv(history: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": history.index.date.astype(str),
            "open": pd.to_numeric(history.get("Open", history["Close"]), errors="coerce"),
            "high": pd.to_numeric(history.get("High", history["Close"]), errors="coerce"),
            "low": pd.to_numeric(history.get("Low", history["Close"]), errors="coerce"),
            "close": pd.to_numeric(history["Close"], errors="coerce"),
            "volume": pd.to_numeric(history.get("Volume", 0), errors="coerce").fillna(0),
        },
        index=history.index,
    ).dropna(subset=["close"])


def resolve_yfinance_symbol(
    report: ExtractedReport, start: datetime, end: datetime
) -> tuple[str, pd.DataFrame]:
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


@dataclass(frozen=True)
class TargetHitResult:
    hit: bool
    first_hit_date: pd.Timestamp | None
    holding_days: int | None


@dataclass(frozen=True)
class OracleBaseline:
    entry_price: float
    exit_price: float
    return_: float | None
    buy_lag_days: int
    holding_days: int


@dataclass(frozen=True)
class SmicFollowerBaseline:
    entry_price: float
    exit_price: float
    return_: float | None
    holding_days: int | None
    status: str


@dataclass(frozen=True)
class PriceDistributionMetrics:
    publication_price: float
    current_price: float
    lowest_price: float
    lowest_date: pd.Timestamp
    highest_price: float
    highest_date: pd.Timestamp
    best_after_low_price: float
    best_after_low_date: pd.Timestamp
    low_to_high_return: float | None
    low_to_high_holding_days: int
    q25_price: float
    q75_price: float
    current_price_percentile: float


def compute_target_hit(
    close: pd.Series, target: float | None, publication_day: pd.Timestamp | None = None
) -> TargetHitResult:
    """Return first target-hit information for a publication-or-later close path."""

    if target is None:
        return TargetHitResult(hit=False, first_hit_date=None, holding_days=None)
    hit_series = close[close >= target]
    if hit_series.empty:
        return TargetHitResult(hit=False, first_hit_date=None, holding_days=None)
    first_hit_date = pd.Timestamp(hit_series.index[0])
    publication_day = pd.Timestamp(close.index[0] if publication_day is None else publication_day)
    return TargetHitResult(
        hit=True,
        first_hit_date=first_hit_date,
        holding_days=(first_hit_date - publication_day).days,
    )


def compute_oracle_baseline(close: pd.Series, publication_day: pd.Timestamp) -> OracleBaseline:
    """Compute the future-informed upper-bound baseline after publication.

    The oracle may only use publication-or-later prices and chooses the best
    buy/sell pair in chronological order. This is a true long-only upper bound
    for the realized price path; it is intentionally separate from the
    distribution's low-to-later-high descriptive metric.
    """

    values = close.to_numpy(dtype=float)
    best_buy_idx = 0
    best_sell_idx = 0
    min_idx = 0
    best_return = 0.0
    for sell_idx in range(len(values)):
        if values[sell_idx] < values[min_idx]:
            min_idx = sell_idx
        candidate_return = values[sell_idx] / values[min_idx] - 1
        if candidate_return > best_return:
            best_return = float(candidate_return)
            best_buy_idx = min_idx
            best_sell_idx = sell_idx
    entry_date = pd.Timestamp(close.index[best_buy_idx])
    exit_date = pd.Timestamp(close.index[best_sell_idx])
    entry_price = float(values[best_buy_idx])
    exit_price = float(values[best_sell_idx])
    return OracleBaseline(
        entry_price=entry_price,
        exit_price=exit_price,
        return_=best_return,
        buy_lag_days=(entry_date - publication_day).days,
        holding_days=(exit_date - entry_date).days,
    )


def compute_smic_follower_baseline(
    close: pd.Series,
    publication_day: pd.Timestamp,
    target: float | None,
    target_hit: TargetHitResult | None = None,
) -> SmicFollowerBaseline:
    """Compute the naive SMIC follower baseline.

    The follower buys at publication, exits at the target when hit, otherwise
    remains open and is marked at the latest available close.
    """

    entry_price = float(close.iloc[0])
    hit = target_hit or compute_target_hit(close, target)
    exit_price = float(target) if hit.hit and target is not None else float(close.iloc[-1])
    exit_date = hit.first_hit_date if hit.hit else pd.Timestamp(close.index[-1])
    return SmicFollowerBaseline(
        entry_price=entry_price,
        exit_price=exit_price,
        return_=pct_return(exit_price, entry_price),
        holding_days=(exit_date - publication_day).days if exit_date is not None else None,
        status="target_hit" if hit.hit else "open",
    )


def compute_price_distribution_metrics(close: pd.Series) -> PriceDistributionMetrics:
    """Compute path-distribution metrics reused by baseline and UI artifacts."""

    publication_price = float(close.iloc[0])
    current_price = float(close.iloc[-1])
    low_date = pd.Timestamp(close.idxmin())
    high_date = pd.Timestamp(close.idxmax())
    lowest_price = float(close.loc[low_date])
    highest_price = float(close.loc[high_date])
    post_low = close[close.index >= low_date]
    best_after_low_date = pd.Timestamp(post_low.idxmax())
    best_after_low_price = float(post_low.loc[best_after_low_date])
    return PriceDistributionMetrics(
        publication_price=publication_price,
        current_price=current_price,
        lowest_price=lowest_price,
        lowest_date=low_date,
        highest_price=highest_price,
        highest_date=high_date,
        best_after_low_price=best_after_low_price,
        best_after_low_date=best_after_low_date,
        low_to_high_return=pct_return(best_after_low_price, lowest_price),
        low_to_high_holding_days=(best_after_low_date - low_date).days,
        q25_price=float(close.quantile(0.25)),
        q75_price=float(close.quantile(0.75)),
        current_price_percentile=float((close <= current_price).mean()),
    )


def compute_price_metrics(reports: list[ExtractedReport], now: datetime | None = None) -> list[PriceMetric]:
    now = now or datetime.now(UTC)
    if not reports:
        return []
    publication_dates = [
        datetime.fromisoformat(report.meta.date[:10]) for report in reports if report.meta.date
    ]
    fx_start = (min(publication_dates) if publication_dates else now.replace(tzinfo=None)) - timedelta(
        days=10
    )
    fx_end = now + timedelta(days=1)
    target_currencies = {
        normalize_currency(report.target_currency) for report in reports if report.target_currency
    }
    price_currencies = {
        currency_for_symbol(yfinance_candidates(report)[0], report.exchange)
        for report in reports
        if yfinance_candidates(report)
    }
    fx_rates = download_fx_rates(
        target_currencies | price_currencies,
        fx_start,
        fx_end,
        lambda fx_symbol, fx_start_arg, fx_end_arg: _history_to_ohlcv(
            _download_history(fx_symbol, fx_start_arg, fx_end_arg)
        ),
    )
    candidate_symbols = [symbol for report in reports for symbol in yfinance_candidates(report)]
    history_cache = _download_histories(candidate_symbols, fx_start, fx_end)

    metrics: list[PriceMetric] = []
    for report in reports:
        symbol, history = resolve_yfinance_symbol_cached(
            report, lambda symbol: history_cache.get(symbol, pd.DataFrame())
        )
        price_currency = currency_for_symbol(symbol, report.exchange)
        target_currency = normalize_currency(report.target_currency) or price_currency
        if not symbol or history.empty:
            metrics.append(
                empty_price_metric(
                    report, symbol, price_currency, target_currency, "no_price_history", "No yfinance history"
                )
            )
            continue
        history_krw = convert_ohlcv_to_krw(_history_to_ohlcv(history), price_currency, fx_rates)
        history_krw.index = pd.to_datetime(history_krw["date"])
        post = history_krw[history_krw.index >= pd.to_datetime(report.meta.date[:10])].copy()
        if post.empty:
            metrics.append(
                empty_price_metric(
                    report, symbol, price_currency, target_currency, "no_post_publication_prices", ""
                )
            )
            continue
        close = post["close"].dropna()
        distribution = compute_price_distribution_metrics(close)
        target = convert_value_to_krw(report.base_target, target_currency, report.meta.date[:10], fx_rates)
        publication_day = pd.to_datetime(report.meta.date[:10])
        target_hit = compute_target_hit(close, target, publication_day)
        oracle = compute_oracle_baseline(close, publication_day)
        follower = compute_smic_follower_baseline(close, publication_day, target, target_hit)
        holding_days, net_return = optimal_net_holding(close)
        metrics.append(
            PriceMetric(
                title=report.meta.title,
                company=report.meta.company,
                display_name=display_name_for_report(report),
                ticker=report.ticker,
                yfinance_symbol=symbol,
                price_currency=price_currency,
                target_currency=target_currency,
                display_currency="KRW",
                publication_date=report.meta.date[:10],
                publication_buy_price=distribution.publication_price,
                current_price=distribution.current_price,
                target_price=target,
                buy_at_publication_return=pct_return(
                    distribution.current_price, distribution.publication_price
                ),
                publication_to_target_return=pct_return(target, distribution.publication_price)
                if target
                else None,
                oracle_entry_price=oracle.entry_price,
                oracle_exit_price=oracle.exit_price,
                oracle_return=oracle.return_,
                oracle_buy_lag_days=oracle.buy_lag_days,
                oracle_holding_days=oracle.holding_days,
                smic_follower_entry_price=follower.entry_price,
                smic_follower_exit_price=follower.exit_price,
                smic_follower_return=follower.return_,
                smic_follower_holding_days=follower.holding_days,
                smic_follower_status=follower.status,
                lowest_price_since_publication=distribution.lowest_price,
                lowest_price_current_return=pct_return(distribution.current_price, distribution.lowest_price),
                low_to_high_return=distribution.low_to_high_return,
                low_to_high_holding_days=distribution.low_to_high_holding_days,
                q25_price_since_publication=distribution.q25_price,
                q25_price_current_return=pct_return(distribution.current_price, distribution.q25_price),
                highest_price_since_publication=distribution.highest_price,
                highest_price_realized_return=pct_return(
                    distribution.highest_price, distribution.publication_price
                ),
                q75_price_since_publication=distribution.q75_price,
                q75_price_realized_return=pct_return(distribution.q75_price, distribution.publication_price),
                q75_price_current_return=pct_return(distribution.current_price, distribution.q75_price),
                current_price_percentile=distribution.current_price_percentile,
                target_upside_remaining=pct_return(target, distribution.current_price) if target else None,
                optimal_buy_lag_days=oracle.buy_lag_days,
                optimal_holding_days_net_10pct=holding_days,
                optimal_net_return_10pct=net_return,
                target_hit=target_hit.hit,
                first_target_hit_date=""
                if target_hit.first_hit_date is None
                else target_hit.first_hit_date.date().isoformat(),
                target_hit_holding_days=target_hit.holding_days,
                status="ok",
                note="",
            )
        )
    return metrics


def resolve_yfinance_symbol_cached(
    report: ExtractedReport, get_history: Callable[[str], pd.DataFrame]
) -> tuple[str, pd.DataFrame]:
    best_symbol = ""
    best_data = pd.DataFrame()
    best_score = math.inf
    for symbol in yfinance_candidates(report):
        data = get_history(symbol)
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


def empty_price_metric(
    report: ExtractedReport, symbol: str, price_currency: str, target_currency: str, status: str, note: str
) -> PriceMetric:
    return PriceMetric(
        title=report.meta.title,
        company=report.meta.company,
        display_name=display_name_for_report(report),
        ticker=report.ticker,
        yfinance_symbol=symbol,
        price_currency=price_currency,
        target_currency=target_currency,
        display_currency="KRW",
        publication_date=report.meta.date[:10],
        publication_buy_price=None,
        current_price=None,
        target_price=None,
        buy_at_publication_return=None,
        publication_to_target_return=None,
        oracle_entry_price=None,
        oracle_exit_price=None,
        oracle_return=None,
        oracle_buy_lag_days=None,
        oracle_holding_days=None,
        smic_follower_entry_price=None,
        smic_follower_exit_price=None,
        smic_follower_return=None,
        smic_follower_holding_days=None,
        smic_follower_status="unavailable",
        lowest_price_since_publication=None,
        lowest_price_current_return=None,
        low_to_high_return=None,
        low_to_high_holding_days=None,
        q25_price_since_publication=None,
        q25_price_current_return=None,
        highest_price_since_publication=None,
        highest_price_realized_return=None,
        q75_price_since_publication=None,
        q75_price_realized_return=None,
        q75_price_current_return=None,
        current_price_percentile=None,
        target_upside_remaining=None,
        optimal_buy_lag_days=None,
        optimal_holding_days_net_10pct=None,
        optimal_net_return_10pct=None,
        target_hit=False,
        first_target_hit_date="",
        target_hit_holding_days=None,
        status=status,
        note=note,
    )


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


def oracle_forward_weights(price_frame: pd.DataFrame) -> np.ndarray:
    if price_frame.empty:
        return np.array([])
    returns = (price_frame.iloc[-1] / price_frame.iloc[0] - 1.0).replace([np.inf, -np.inf], np.nan)
    valid = returns.dropna()
    if valid.empty:
        return np.ones(price_frame.shape[1]) / price_frame.shape[1]
    weights = np.zeros(price_frame.shape[1])
    weights[price_frame.columns.get_loc(valid.idxmax())] = 1.0
    return weights


@dataclass(frozen=True)
class ScenarioWealth:
    contribution_months: int
    total_contributed_krw: float
    final_value_krw: float
    money_weighted_return: float


def scenario_wealth_from_forward_returns(
    price_frame: pd.DataFrame,
    weights: np.ndarray,
    *,
    initial_capital_krw: float = SCENARIO_INITIAL_CAPITAL_KRW,
    monthly_contribution_krw: float = SCENARIO_MONTHLY_CONTRIBUTION_KRW,
) -> ScenarioWealth | None:
    if price_frame.empty or len(weights) == 0:
        return None
    usable = price_frame.dropna(axis=1)
    if usable.empty:
        return None
    valid = [price_frame.columns.get_loc(column) for column in usable.columns]
    w = _normalize(weights[valid])
    returns = usable.pct_change().fillna(0.0)
    account_value = float(initial_capital_krw)
    contributed = float(initial_capital_krw)
    contribution_months = 0
    current_month: tuple[int, int] | None = None
    for date, row in returns.iterrows():
        month = (pd.Timestamp(date).year, pd.Timestamp(date).month)
        if current_month is None:
            current_month = month
        elif month != current_month:
            account_value += float(monthly_contribution_krw)
            contributed += float(monthly_contribution_krw)
            contribution_months += 1
            current_month = month
        account_value *= max(0.0, 1.0 + float(np.dot(row.to_numpy(dtype=float), w)))
    return ScenarioWealth(
        contribution_months=contribution_months,
        total_contributed_krw=contributed,
        final_value_krw=account_value,
        money_weighted_return=account_value / contributed - 1.0 if contributed > 0 else 0.0,
    )


def portfolio_expected_stats(
    returns: pd.DataFrame, weights: np.ndarray, risk_free_rate: float
) -> tuple[float | None, float | None, float | None]:
    if returns.empty or len(weights) == 0:
        return None, None, None
    mean = _annualized_returns(returns).to_numpy(dtype=float)
    cov = _annualized_cov(returns).to_numpy(dtype=float)
    expected_return = float(weights @ mean)
    expected_volatility = math.sqrt(max(float(weights @ cov @ weights), 0.0))
    expected_sharpe = (
        None if expected_volatility == 0 else (expected_return - risk_free_rate) / expected_volatility
    )
    return expected_return, expected_volatility, expected_sharpe


def compute_portfolio_backtests(
    reports: list[ExtractedReport], price_metrics: list[PriceMetric], now: datetime | None = None
) -> list[PortfolioResult]:
    now = now or datetime.now(UTC)
    by_title = {
        metric.title: metric for metric in price_metrics if metric.status == "ok" and metric.yfinance_symbol
    }
    display_by_symbol = {
        metric.yfinance_symbol: metric.display_name for metric in price_metrics if metric.yfinance_symbol
    }
    rows: list[PortfolioResult] = []
    frame_rows = []
    for report in reports:
        metric = by_title.get(report.meta.title)
        if metric:
            frame_rows.append(
                {
                    "month": report.meta.date[:7],
                    "date": report.meta.date[:10],
                    "symbol": metric.yfinance_symbol,
                }
            )
    if not frame_rows:
        return rows
    all_symbols = sorted({row["symbol"] for row in frame_rows}) + list(BENCHMARKS.values())
    earliest_rebalance = pd.to_datetime(min(row["date"] for row in frame_rows)) + pd.Timedelta(days=1)
    cache_start = (earliest_rebalance - pd.Timedelta(days=730)).to_pydatetime()
    cache_end = (pd.Timestamp(now.date()) + pd.Timedelta(days=1)).to_pydatetime()
    history_cache = _download_histories(all_symbols, cache_start, cache_end)
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
            hist = history_cache.get(symbol, pd.DataFrame())
            if not hist.empty:
                hist = hist[(hist.index >= lookback_start) & (hist.index < end)]
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
            benchmark_history = history_cache.get(symbol, pd.DataFrame())
            if not benchmark_history.empty:
                benchmark_history = benchmark_history[
                    (benchmark_history.index >= forward.index[0]) & (benchmark_history.index < end)
                ]
            benchmark_returns[name] = (
                None
                if benchmark_history.empty
                else pct_return(
                    float(benchmark_history["Close"].iloc[-1]), float(benchmark_history["Close"].iloc[0])
                )
            )
        returns = lookback.pct_change().dropna()
        for rf in RISK_FREE_RATES:
            for strategy in [
                "1/N",
                "smic_follower_1n",
                "oracle",
                "momentum",
                "max_sharpe",
                "sortino",
                "max_return",
                "min_var",
                "calmar",
            ]:
                weights = (
                    oracle_forward_weights(forward[returns.columns])
                    if strategy == "oracle"
                    else optimize_weights(returns, "1/N" if strategy == "smic_follower_1n" else strategy, rf)
                )
                expected_return, expected_volatility, expected_sharpe = portfolio_expected_stats(
                    returns, weights, rf
                )
                scenario = scenario_wealth_from_forward_returns(forward[returns.columns], weights)
                rows.append(
                    PortfolioResult(
                        cohort_month=str(month),
                        rebalance_date=forward.index[0].date().isoformat(),
                        strategy=strategy,
                        risk_free_rate=rf,
                        symbols=",".join(returns.columns),
                        display_symbols=",".join(
                            display_by_symbol.get(symbol, symbol) for symbol in returns.columns
                        ),
                        weights=",".join(f"{w:.4f}" for w in weights),
                        initial_capital_krw=SCENARIO_INITIAL_CAPITAL_KRW,
                        monthly_contribution_krw=SCENARIO_MONTHLY_CONTRIBUTION_KRW,
                        contribution_months=0 if scenario is None else scenario.contribution_months,
                        total_contributed_krw=(
                            SCENARIO_INITIAL_CAPITAL_KRW
                            if scenario is None
                            else scenario.total_contributed_krw
                        ),
                        final_value_krw=None if scenario is None else scenario.final_value_krw,
                        money_weighted_return=None if scenario is None else scenario.money_weighted_return,
                        cash_weight=0.0,
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
