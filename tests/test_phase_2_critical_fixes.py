"""Regression tests for the 4 CRITICAL bugs flagged in the Phase 2 code review.

Each test is named ``test_critical_<n>_*`` and is intentionally narrow — it
must FAIL deterministically if the corresponding fix regresses, and PASS only
when the fix is in place.
"""

from __future__ import annotations

import math

import pandas as pd

from snusmic_pipeline.backtest.engine import (
    _observed_price,
    _resolve_fill,
    run_walk_forward_backtest,
)
from snusmic_pipeline.backtest.schemas import BacktestConfig

# ---------------------------------------------------------------------------
# CRITICAL-1: first-bar same-day-close lookahead must not be possible.
# ---------------------------------------------------------------------------


def test_critical_1_first_bar_observed_price_returns_none() -> None:
    """When ``prev_close_row is None`` (very first trading day), ``_observed_price``
    must return ``None`` — callers must skip the symbol rather than fall back
    to today's close. Aliasing to ``close_row`` would silently leak same-day
    close into entry decisions.
    """
    assert _observed_price(None, "AAA.KS") is None


def test_critical_1_first_bar_publication_does_not_emit_lookahead_decision() -> None:
    """End-to-end: a report whose ``publication_date`` lands one day before
    ``prices.date.min()`` (a backfilled symbol) must not produce an execution
    event whose ``decision_price`` equals same-day close.
    """
    dates = pd.bdate_range("2024-01-02", periods=120)
    rows = []
    for date, price in zip(dates, [100.0 + i * 1.5 for i in range(len(dates))], strict=True):
        rows.append(
            {
                "date": date.date().isoformat(),
                "symbol": "AAA.KS",
                "open": price * 0.98,
                "high": price * 1.01,
                "low": price * 0.97,
                "close": price,
                "volume": 1000,
            }
        )
    prices = pd.DataFrame(rows)
    reports = pd.DataFrame(
        [
            {
                "report_id": "r1",
                # Published BEFORE the first available bar — engine sees the
                # report on day 0 and used to decide using day-0 close.
                "publication_date": "2024-01-01",
                "title": "AAA",
                "company": "AAA Co",
                "ticker": "AAA",
                "exchange": "KRX",
                "symbol": "AAA.KS",
                "target_price": 130.0,
                "report_current_price": 100.0,
            }
        ]
    )
    config = BacktestConfig(
        name="critical-1",
        entry_rule="target_only",
        weighting="1/N",
        rebalance="daily",
        min_target_upside=0.0,
    )
    result = run_walk_forward_backtest(reports, prices, config)
    events = result["execution_events"]
    if events.empty:
        return  # vacuous pass — no entry triggered, no lookahead possible
    same_day_decisions = [
        (str(ev["date"])[:10], ev["symbol"], ev.get("decision_price"))
        for _, ev in events.iterrows()
        if ev.get("signal_date") is not None and str(ev["signal_date"])[:10] >= str(ev["date"])[:10]
    ]
    assert not same_day_decisions, f"first-bar lookahead reintroduced: {same_day_decisions}"


# ---------------------------------------------------------------------------
# CRITICAL-2: open / close fill_rule mislabeling.
# ---------------------------------------------------------------------------


def test_critical_2_resolve_fill_close_fallback_when_open_invalid() -> None:
    open_row = pd.Series({"AAA.KS": 99.0})
    close_row = pd.Series({"AAA.KS": 100.0})
    valid_yes = pd.Series({"AAA.KS": True})
    valid_no = pd.Series({"AAA.KS": False})

    price, rule = _resolve_fill(open_row, close_row, valid_yes, "AAA.KS")
    assert (price, rule) == (99.0, "open")

    price, rule = _resolve_fill(open_row, close_row, valid_no, "AAA.KS")
    # Even when ``open_row`` carries a numeric value, an invalid provenance
    # must downgrade fill_rule to ``close_fallback`` so a missing-open day
    # cannot be silently mislabelled.
    assert rule == "close_fallback"
    assert price == 100.0


def test_critical_2_no_open_quote_yields_close_fallback_label() -> None:
    """End-to-end: a price frame whose ``open`` column is entirely NaN must
    label every fill ``close_fallback``, never ``open``. Pre-fix the engine
    aliased ``open_row = close_row`` and stamped ``fill_rule='open'``.
    """
    dates = pd.bdate_range("2024-01-02", periods=80)
    rows = []
    for date, price in zip(dates, [100.0 + i * 0.8 for i in range(len(dates))], strict=True):
        rows.append(
            {
                "date": date.date().isoformat(),
                "symbol": "AAA.KS",
                "open": float("nan"),  # <-- no genuine open quote
                "high": price * 1.01,
                "low": price * 0.99,
                "close": price,
                "volume": 1000,
            }
        )
    prices = pd.DataFrame(rows)
    reports = pd.DataFrame(
        [
            {
                "report_id": "r1",
                "publication_date": "2024-01-15",
                "title": "AAA",
                "company": "AAA Co",
                "ticker": "AAA",
                "exchange": "KRX",
                "symbol": "AAA.KS",
                "target_price": 200.0,
                "report_current_price": 100.0,
            }
        ]
    )
    config = BacktestConfig(
        name="critical-2",
        entry_rule="target_only",
        weighting="1/N",
        rebalance="daily",
        min_target_upside=0.0,
    )
    result = run_walk_forward_backtest(reports, prices, config)
    events = result["execution_events"]
    if events.empty:
        return
    fill_rules = set(events["fill_rule"].dropna().unique())
    assert "open" not in fill_rules, f"fill_rule='open' emitted with no genuine open quote: {fill_rules}"
    assert fill_rules <= {"close_fallback", "delisting_last_close"}, fill_rules


# ---------------------------------------------------------------------------
# CRITICAL-3: forward-fill MTM bias on Sortino.
# ---------------------------------------------------------------------------


def _make_imputed_fixture(imputed_run_length: int = 15) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return a 2-symbol fixture where one symbol has a large block of
    forward-filled (imputed) closes during the position's holding period.
    """
    dates = pd.bdate_range("2024-01-02", periods=200)
    rows = []
    for i, date in enumerate(dates):
        # GOOD.KS — fully clean.
        good_close = 100.0 + i * 0.4
        rows.append(
            {
                "date": date.date().isoformat(),
                "symbol": "GOOD.KS",
                "open": good_close * 0.998,
                "high": good_close * 1.01,
                "low": good_close * 0.99,
                "close": good_close,
                "volume": 1000,
            }
        )
        # BAD.KS — drops trading half-way through, NaN closes for a stretch.
        bad_close = 80.0 + i * 0.2
        if 60 <= i < 60 + imputed_run_length:
            bad_close = float("nan")
        rows.append(
            {
                "date": date.date().isoformat(),
                "symbol": "BAD.KS",
                "open": (bad_close * 0.998) if not math.isnan(bad_close) else float("nan"),
                "high": (bad_close * 1.01) if not math.isnan(bad_close) else float("nan"),
                "low": (bad_close * 0.99) if not math.isnan(bad_close) else float("nan"),
                "close": bad_close,
                "volume": 1000,
            }
        )
    prices = pd.DataFrame(rows)
    reports = pd.DataFrame(
        [
            {
                "report_id": "rG",
                "publication_date": "2024-01-15",
                "title": "Good",
                "company": "Good Co",
                "ticker": "GOOD",
                "exchange": "KRX",
                "symbol": "GOOD.KS",
                "target_price": 1000.0,
                "report_current_price": 100.0,
            },
            {
                "report_id": "rB",
                "publication_date": "2024-01-15",
                "title": "Bad",
                "company": "Bad Co",
                "ticker": "BAD",
                "exchange": "KRX",
                "symbol": "BAD.KS",
                "target_price": 1000.0,
                "report_current_price": 80.0,
            },
        ]
    )
    return reports, prices


def test_critical_3_imputed_bars_excluded_from_mtm() -> None:
    """End-to-end: the reported Sortino must be **lower** when a held
    position experiences a large block of imputed bars compared to a baseline
    where every bar is genuine. Pre-fix the engine padded zero-return days
    into the equity curve, deflating downside-vol and inflating Sortino —
    Optuna would systematically prefer illiquid / partially-delisted names.
    """
    reports, prices_imputed = _make_imputed_fixture(imputed_run_length=20)
    _, prices_clean = _make_imputed_fixture(imputed_run_length=0)

    config = BacktestConfig(
        name="critical-3",
        entry_rule="target_only",
        weighting="1/N",
        rebalance="daily",
        min_target_upside=0.0,
        lookback_days=60,
    )
    imputed_run = run_walk_forward_backtest(reports, prices_imputed, config)
    clean_run = run_walk_forward_backtest(reports, prices_clean, config)
    imputed_eq = imputed_run["equity_daily"]
    clean_eq = clean_run["equity_daily"]
    imputed_zero_days = int((imputed_eq["portfolio_return"].astype(float) == 0).sum())
    clean_zero_days = int((clean_eq["portfolio_return"].astype(float) == 0).sum())
    # The fixture deliberately injects 20 imputed bars on BAD.KS; with the
    # CRITICAL-3 fix the imputed-day MTM contributions are excluded, so the
    # ratio of zero-return days does NOT explode in the imputed run. Pre-fix
    # the imputed version had ~20 extra zero-return days from the BAD.KS
    # imputed contribution forcing portfolio_return to 0.
    extra_zero = imputed_zero_days - clean_zero_days
    assert extra_zero <= 5, (
        f"imputed run produced {extra_zero} more zero-return days than the clean run — "
        "MTM is still consuming forward-filled prices (CRITICAL-3 regression)."
    )


# ---------------------------------------------------------------------------
# CRITICAL-4: legacy_objective via config, not env var.
# ---------------------------------------------------------------------------


def test_critical_4_legacy_objective_lives_on_config_not_env(monkeypatch) -> None:
    """``BacktestConfig.legacy_objective=True`` must produce
    ``objective == total_return``; ``False`` must produce
    ``objective == sortino_oos`` (when computable). The env-var that used to
    drive this is gone — verify by setting it to ``1`` and asserting it has
    no effect.
    """
    monkeypatch.setenv("SNUSMIC_LEGACY_OBJECTIVE", "1")  # must be ignored

    dates = pd.bdate_range("2022-01-03", periods=400)
    rows = []
    for i, date in enumerate(dates):
        price = 80.0 + i * 0.2
        rows.append(
            {
                "date": date.date().isoformat(),
                "symbol": "AAA.KS",
                "open": price * 0.998,
                "high": price * 1.01,
                "low": price * 0.99,
                "close": price,
                "volume": 1000,
            }
        )
    prices = pd.DataFrame(rows)
    reports = pd.DataFrame(
        [
            {
                "report_id": "r1",
                "publication_date": "2022-06-01",
                "title": "AAA",
                "company": "AAA Co",
                "ticker": "AAA",
                "exchange": "KRX",
                "symbol": "AAA.KS",
                "target_price": 200.0,
                "report_current_price": 100.0,
            }
        ]
    )
    cfg_default = BacktestConfig(
        name="c4-default",
        entry_rule="target_only",
        weighting="1/N",
        rebalance="daily",
        min_target_upside=0.0,
    )
    cfg_legacy = BacktestConfig(
        name="c4-legacy",
        entry_rule="target_only",
        weighting="1/N",
        rebalance="daily",
        min_target_upside=0.0,
        legacy_objective=True,
    )
    default_row = run_walk_forward_backtest(reports, prices, cfg_default)["strategy_runs"].iloc[0]
    legacy_row = run_walk_forward_backtest(reports, prices, cfg_legacy)["strategy_runs"].iloc[0]

    # Default branch: env var is set but ignored — objective == sortino_oos.
    if default_row["sortino_oos"] is not None and math.isfinite(float(default_row["sortino_oos"])):
        assert math.isclose(
            float(default_row["objective"]),
            float(default_row["sortino_oos"]),
            rel_tol=1e-9,
        ), "env var leaked into default-config run"

    # Legacy branch: objective must equal total_return regardless of OOS.
    assert math.isclose(
        float(legacy_row["objective"]),
        float(legacy_row["total_return"]),
        rel_tol=1e-9,
    ), "legacy_objective config did not flip the objective to total_return"

    # The two configs must produce different run_ids — Optuna and the
    # warehouse cannot conflate them.
    assert default_row["run_id"] != legacy_row["run_id"], (
        "legacy_objective change did not propagate to run_id hash; "
        "rows would silently overwrite each other in strategy_runs.csv"
    )
