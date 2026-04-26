"""Principle-4 regression tests: every lookahead site in ``backtest.engine`` must
decide using t-1 close, never t-close.

The parametrized test ids match the 4 sites enumerated in
``.omc/plans/consensus-full-overhaul.md``:

- ``engine.py:342`` — ``_close_position target_hit same-day close``
- ``engine.py:371`` — ``_expire_candidates target_hit same-day close``
- ``engine.py:400`` — ``_eligible_symbols target_upside same-day close (site 1)``
- ``engine.py:401-402`` — ``_eligible_symbols target_upside same-day close (site 2)``

Phase 2a fixed all 4 sites: every execution event now records ``signal_date``
(t-1), ``decision_price`` (price observed at signal_date), ``fill_price``
(t open or close fallback), and ``fill_rule``. CI keeps this honest via
``pytest --collect-only | grep -vq xfail`` (see
``.github/workflows/phase-2-xfail-transition.yml``) — any xfail marker
re-introduced on this module fails the build.
"""

from __future__ import annotations

import pandas as pd
import pytest

from snusmic_pipeline.backtest.engine import run_walk_forward_backtest
from snusmic_pipeline.backtest.schemas import BacktestConfig

LOOKAHEAD_SITES = [
    pytest.param("engine.py:342", id="engine.py:342"),
    pytest.param("engine.py:371", id="engine.py:371"),
    pytest.param("engine.py:400", id="engine.py:400"),
    pytest.param("engine.py:401-402", id="engine.py:401-402"),
]


def _price_frame(symbol: str = "AAA.KS", periods: int = 320) -> pd.DataFrame:
    """Synthetic price with open != close so the test can distinguish
    decision-side observation from fill-side observation."""
    dates = pd.bdate_range("2023-01-02", periods=periods)
    close = pd.Series(range(periods), dtype=float) * 0.15 + 80.0
    rows = []
    for date, price in zip(dates, close, strict=True):
        rows.append(
            {
                "date": date.date().isoformat(),
                "symbol": symbol,
                "open": float(price) * 0.99,  # <-- deliberately offset from close
                "high": float(price) * 1.01,
                "low": float(price) * 0.98,
                "close": float(price),
                "volume": 1000,
            }
        )
    return pd.DataFrame(rows)


def _reports_frame(symbol: str = "AAA.KS", target: float = 200.0) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "report_id": "r1",
                "publication_date": "2024-01-10",
                "title": "Equity Research, AAA",
                "company": "AAA Corp",
                "ticker": "AAA",
                "exchange": "KRX",
                "symbol": symbol,
                "target_price": target,
                "report_current_price": 100.0,
            }
        ]
    )


@pytest.mark.parametrize("site", LOOKAHEAD_SITES)
def test_decisions_use_prior_close_not_same_day(site: str) -> None:
    """For each lookahead site, assert the engine records a ``decision_price``
    that equals t-1 close (never t-close), a ``signal_date`` strictly before
    ``date``, and a ``fill_rule`` in {``open``, ``close_fallback``}.

    Phase 1a shipped this as ``xfail(strict=True)``; Phase 2a flipped it to
    pass by threading ``prev_close_row`` through every decision function and
    resolving fills at t open. CI enforces no xfail markers remain (see module
    docstring).
    """
    reports = _reports_frame(target=200.0)
    prices = _price_frame(periods=280)
    config = BacktestConfig(
        name=f"lookahead-{site}",
        entry_rule="target_only",
        weighting="1/N",
        rebalance="daily",
        min_target_upside=0.0,
    )
    result = run_walk_forward_backtest(reports, prices, config)
    events = result["execution_events"]
    assert not events.empty, f"{site}: no execution events produced; fixture is wrong"

    close_map = {(row["date"], row["symbol"]): float(row["close"]) for _, row in prices.iterrows()}
    # Index prices by position for prev-close lookup.
    prices_sorted = prices.sort_values(["symbol", "date"]).reset_index(drop=True)
    prev_close_map: dict[tuple[str, str], float] = {}
    prev_per_symbol: dict[str, float] = {}
    for _, row in prices_sorted.iterrows():
        if row["symbol"] in prev_per_symbol:
            prev_close_map[(row["date"], row["symbol"])] = prev_per_symbol[row["symbol"]]
        prev_per_symbol[row["symbol"]] = float(row["close"])

    violations: list[str] = []
    for _, ev in events.iterrows():
        date = str(ev.get("date", ""))[:10]
        symbol = str(ev.get("symbol", ""))
        signal_date = ev.get("signal_date")
        decision_price = ev.get("decision_price")
        fill_rule = ev.get("fill_rule")
        # Every Phase-2a event must carry the 4 new fields.
        if (
            signal_date is None
            or decision_price is None
            or fill_rule not in {"open", "close_fallback", "delisting_last_close"}
        ):
            violations.append(
                f"{date}/{symbol}: missing phase-2a metadata (signal_date={signal_date}, decision_price={decision_price}, fill_rule={fill_rule})"
            )
            continue
        if str(signal_date) >= date:
            violations.append(f"{date}/{symbol}: signal_date={signal_date} not strictly before trade date")
        same_day_close = close_map.get((date, symbol))
        prev_close = prev_close_map.get((date, symbol))
        if (
            same_day_close is not None
            and abs(float(decision_price) - same_day_close) < 1e-9
            and (prev_close is None or abs(prev_close - same_day_close) > 1e-9)
        ):
            violations.append(
                f"{date}/{symbol}: decision_price={decision_price} equals same-day close — lookahead"
            )
        if prev_close is not None and abs(float(decision_price) - prev_close) > 1e-6:
            # Allow small drift only on the first observation (when prev_close is unavailable and we fall back).
            violations.append(f"{date}/{symbol}: decision_price={decision_price} != prev_close={prev_close}")

    assert not violations, f"{site}: {len(violations)} lookahead violation(s):\n  " + "\n  ".join(
        violations[:5]
    )
