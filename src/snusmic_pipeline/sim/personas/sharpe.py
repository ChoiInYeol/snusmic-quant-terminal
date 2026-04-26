"""Long-only max-Sharpe weight solver shared by both prophet personas.

Both ``simulate_prophet`` and ``simulate_weak_prophet`` solve the same
optimisation — max ``(μ - r_f) / σ`` subject to ``sum(w) = 1``,
``0 ≤ w_i ≤ max_weight`` — over a returns window that the persona
itself selects (full remaining horizon for Prophet, next ``lookahead_months``
for Weak Prophet). Keeping the solver here means the math is in exactly
one place.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import minimize


def solve_max_sharpe_weights(
    returns: pd.DataFrame,
    *,
    risk_free_rate: float,
    max_weight: float,
    min_history_days: int,
) -> dict[str, float]:
    """Return a long-only weight dict that maximises Sharpe over ``returns``.

    Parameters
    ----------
    returns
        Daily simple returns, columns = symbols, index = dates. Will be
        winsorised internally (NaN → 0). Symbols with fewer than
        ``min_history_days`` non-NaN observations are dropped.
    risk_free_rate
        Annualised; the solver uses 252 trading days for compounding.
    max_weight
        Per-name cap, in (0, 1]. ``max_weight=1.0`` allows full
        concentration.
    min_history_days
        Drop columns shorter than this length post-NaN. Empty result
        when no symbols survive.

    Returns
    -------
    dict[str, float]
        ``{symbol: weight}`` with weights summing to 1.0 over the
        returned symbols (caller may renormalise after price filtering).
        Empty dict when the universe has no usable history.
    """
    if returns.empty:
        return {}
    rets = returns.dropna(axis=1, thresh=min_history_days)
    if rets.shape[1] == 0:
        return {}
    rets = rets.fillna(0.0)
    mu = rets.mean().to_numpy() * 252.0
    cov = rets.cov().to_numpy() * 252.0
    n = mu.size
    if n == 1:
        return {str(rets.columns[0]): 1.0}
    cap = float(min(1.0, max(max_weight, 1.0 / n)))

    def neg_sharpe(weights: np.ndarray) -> float:
        port_return = float(np.dot(weights, mu))
        port_var = float(np.dot(weights, cov @ weights))
        if port_var <= 1e-12:
            return -port_return
        port_vol = float(np.sqrt(port_var))
        return -(port_return - risk_free_rate) / port_vol

    constraints = ({"type": "eq", "fun": lambda w: float(np.sum(w) - 1.0)},)
    bounds = [(0.0, cap)] * n
    x0 = np.full(n, 1.0 / n)
    try:
        result = minimize(
            neg_sharpe,
            x0,
            method="SLSQP",
            bounds=bounds,
            constraints=constraints,
            options={"ftol": 1e-9, "maxiter": 200, "disp": False},
        )
        if not result.success:
            return _equal_weights(rets.columns)
        weights = np.clip(result.x, 0.0, cap)
        s = weights.sum()
        if s <= 0:
            return _equal_weights(rets.columns)
        weights = weights / s
    except Exception:
        return _equal_weights(rets.columns)
    return {str(sym): float(w) for sym, w in zip(rets.columns, weights, strict=True) if w > 1e-4}


def _equal_weights(columns) -> dict[str, float]:
    n = len(columns)
    if n == 0:
        return {}
    return {str(c): 1.0 / n for c in columns}
