from __future__ import annotations

import math

import numpy as np
import pandas as pd
from scipy.optimize import minimize


def normalize_weights(weights: np.ndarray) -> np.ndarray:
    weights = np.nan_to_num(weights.astype(float), nan=0.0, posinf=0.0, neginf=0.0)
    weights = np.maximum(weights, 0.0)
    total = float(weights.sum())
    if total <= 0:
        return np.ones_like(weights) / len(weights)
    return weights / total


def _annualized_mean(returns: pd.DataFrame) -> np.ndarray:
    return returns.mean().to_numpy(dtype=float) * 252


def _annualized_cov(returns: pd.DataFrame) -> np.ndarray:
    return returns.cov().to_numpy(dtype=float) * 252


def _portfolio_series(returns: pd.DataFrame, weights: np.ndarray) -> np.ndarray:
    return returns.to_numpy(dtype=float) @ weights


def optimize_execution_weights(
    returns: pd.DataFrame,
    symbols: list[str],
    method: str,
    risk_free_rate: float = 0.03,
) -> dict[str, float]:
    """Return no-short weights using only the supplied historical simple returns."""
    if not symbols:
        return {}
    frame = returns.reindex(columns=symbols).dropna(how="all")
    frame = frame.dropna(axis=1)
    usable_symbols = list(frame.columns)
    if not usable_symbols:
        return {symbol: 1.0 / len(symbols) for symbol in symbols}
    n = len(usable_symbols)
    if n == 1 or method == "1/N":
        weights = np.ones(n) / n
    elif method == "max_return":
        mean = _annualized_mean(frame)
        weights = np.zeros(n)
        weights[int(np.argmax(mean))] = 1.0
    elif method == "momentum":
        momentum = np.exp(frame.sum().to_numpy(dtype=float)) - 1.0
        weights = normalize_weights(momentum)
    else:
        weights = _optimize(frame, method, risk_free_rate)
    result = {symbol: 0.0 for symbol in symbols}
    for symbol, weight in zip(usable_symbols, normalize_weights(weights), strict=False):
        result[symbol] = float(weight)
    total = sum(result.values())
    if total <= 0:
        return {symbol: 1.0 / len(symbols) for symbol in symbols}
    return {symbol: weight / total for symbol, weight in result.items()}


def _optimize(returns: pd.DataFrame, method: str, risk_free_rate: float) -> np.ndarray:
    n = returns.shape[1]
    mean = _annualized_mean(returns)
    cov = _annualized_cov(returns)
    bounds = [(0.0, 1.0)] * n
    constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]
    init = np.ones(n) / n

    def variance(weights: np.ndarray) -> float:
        return float(weights @ cov @ weights)

    def sharpe_loss(weights: np.ndarray) -> float:
        vol = math.sqrt(max(variance(weights), 1e-12))
        return -float((weights @ mean - risk_free_rate) / vol)

    def sortino_loss(weights: np.ndarray) -> float:
        port = _portfolio_series(returns, weights)
        downside = port[port < 0]
        downside_vol = float(np.std(downside) * math.sqrt(252)) if len(downside) else 1e-6
        return -float((weights @ mean - risk_free_rate) / max(downside_vol, 1e-6))

    def calmar_loss(weights: np.ndarray) -> float:
        port = pd.Series(_portfolio_series(returns, weights), index=returns.index)
        equity = pd.Series(np.exp(port.cumsum()), index=returns.index)
        drawdown = equity / equity.cummax() - 1.0
        max_dd = abs(float(drawdown.min()))
        return -float((weights @ mean - risk_free_rate) / max(max_dd, 1e-6))

    def cvar_loss(weights: np.ndarray) -> float:
        port = np.sort(_portfolio_series(returns, weights))
        tail_n = max(1, int(math.ceil(len(port) * 0.05)))
        cvar = abs(float(port[:tail_n].mean())) * math.sqrt(252)
        expected = float(weights @ mean)
        return -float((expected - risk_free_rate) / max(cvar, 1e-6))

    objective = {
        "min_var": variance,
        "sharpe": sharpe_loss,
        "max_sharpe": sharpe_loss,
        "sortino": sortino_loss,
        "calmar": calmar_loss,
        "cvar": cvar_loss,
    }.get(method, sharpe_loss)
    result = minimize(objective, init, method="SLSQP", bounds=bounds, constraints=constraints)
    return normalize_weights(result.x if result.success else init)
