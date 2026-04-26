from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from .optimizers import optimize_execution_weights
from .schemas import BacktestConfig, StrategySummary
from .signals import compute_signals_daily, signal_lookup

# Phase 2b — 3-segment OOS-tail diagnostic shape.
# See docs/decisions/phase-2-objective.md for the locked contract.
PHASE_2_FOLD_COUNT = 3
PHASE_2_OOS_FRACTION = 0.30

# Phase 2c — delisting detection. A held position whose symbol has not
# reported a price for this many trading days is treated as delisted and
# forcibly sold at the last observed close (fill_rule='delisting_last_close').
# This closes the plan's AC #4 "never silently dropped" gap.
DELISTING_GAP_DAYS = 21


@dataclass
class Position:
    symbol: str
    company: str
    report_id: str
    entry_date: pd.Timestamp
    entry_price: float
    weight: float
    target_price: float | None
    contribution_return: float = 0.0


def run_walk_forward_backtest(
    reports: pd.DataFrame,
    prices: pd.DataFrame,
    config: BacktestConfig | None = None,
    run_id: str | None = None,
) -> dict[str, pd.DataFrame]:
    config = (config or BacktestConfig()).normalized()
    run_id = run_id or stable_run_id(config)
    reports = _prepare_reports(reports)
    prices = _prepare_prices(prices)
    if reports.empty or prices.empty:
        return empty_result(run_id, config)
    signals = compute_signals_daily(prices, reports, config.mtt_slope_months)
    signal_rows = signal_lookup(signals)
    wide = prices.pivot_table(index="date", columns="symbol", values="close", aggfunc="last").sort_index()
    wide_open = prices.pivot_table(index="date", columns="symbol", values="open", aggfunc="last").sort_index()
    # Boolean provenance pivots — code-review CRITICAL-2 / CRITICAL-3.
    # ``wide_open_valid``: True only where the original CSV row carried a
    # genuine ``open`` quote; ``_resolve_fill`` consults it to honestly stamp
    # ``fill_rule='open'`` vs ``'close_fallback'``.
    # ``wide_imputed``: True where ``close`` was forward-filled (no real
    # quote that day); the MTM loop skips those bars so synthetic zero-return
    # days do not deflate downside-vol and inflate Sortino.
    wide_open_valid = (
        prices.pivot_table(index="date", columns="symbol", values="open_valid", aggfunc="last")
        .reindex(index=wide.index, columns=wide.columns)
        .fillna(False)
        .astype(bool)
    )
    wide_imputed = (
        prices.pivot_table(index="date", columns="symbol", values="close_imputed", aggfunc="last")
        .reindex(index=wide.index, columns=wide.columns)
        .fillna(True)  # any cell with no row at all is "as-if-imputed" (no real observation)
        .astype(bool)
    )
    trading_dates = [pd.Timestamp(date) for date in wide.index if date >= reports["publication_date"].min()]
    trading_date_index = {date: i for i, date in enumerate(trading_dates)}
    if len(trading_dates) < 2:
        return empty_result(run_id, config)

    report_rows = reports.sort_values(["publication_date", "report_id"]).to_dict("records")
    pending_idx = 0
    candidates: dict[str, dict[str, Any]] = {}
    positions: dict[str, Position] = {}
    closed_once: set[str] = set()
    last_rebalance: pd.Timestamp | None = None
    prev_date: pd.Timestamp | None = None
    equity_value = 1.0

    candidate_events: list[dict[str, Any]] = []
    execution_events: list[dict[str, Any]] = []
    equity_rows: list[dict[str, Any]] = []
    position_rows: list[dict[str, Any]] = []

    for date in trading_dates:
        close_row = wide.loc[date]
        # Phase 2a + code-review CRITICAL-1: ``prev_close_row`` is None on the
        # very first trading day so decision helpers must skip the symbol
        # rather than fall back to today's close. Aliasing to ``close_row``
        # would silently leak same-day-close into entry / target_hit /
        # target_upside decisions.
        prev_close_row = wide.loc[prev_date] if prev_date is not None else None
        open_row = wide_open.loc[date]
        open_valid_row = wide_open_valid.loc[date]
        imputed_row = wide_imputed.loc[date]
        prev_imputed_row = wide_imputed.loc[prev_date] if prev_date is not None else None
        portfolio_return = 0.0
        realized_today = 0.0
        if prev_date is not None and prev_close_row is not None:
            for position in positions.values():
                # CRITICAL-3: skip MTM whenever either bar's close was
                # imputed. Forward-filled bars produce zero return by
                # construction, which understates realised vol and biases
                # Sortino upward.
                imputed_today = bool(imputed_row.get(position.symbol, True))
                imputed_prev = (
                    bool(prev_imputed_row.get(position.symbol, True))
                    if prev_imputed_row is not None
                    else True
                )
                if imputed_today or imputed_prev:
                    continue
                if _has_price(prev_close_row, position.symbol) and _has_price(close_row, position.symbol):
                    asset_return = (
                        float(close_row[position.symbol]) / float(prev_close_row[position.symbol]) - 1.0
                    )
                    contribution = position.weight * asset_return
                    position.contribution_return += contribution
                    portfolio_return += contribution

        while (
            pending_idx < len(report_rows)
            and pd.Timestamp(report_rows[pending_idx]["publication_date"]) < date
        ):
            report = report_rows[pending_idx]
            pending_idx += 1
            if not _has_price(close_row, report["symbol"]):
                continue
            event_type = "candidate_add" if report["symbol"] not in candidates else "candidate_refresh"
            candidates[report["symbol"]] = {**report, "eligible_date": date}
            candidate_events.append(
                _candidate_event(
                    run_id,
                    date,
                    report,
                    event_type,
                    "report_publication",
                    float(close_row[report["symbol"]]),
                    len(candidates),
                )
            )

        realized_today += _exit_positions_for_risk(
            run_id,
            date,
            prev_date,
            prev_close_row,
            open_row,
            open_valid_row,
            close_row,
            positions,
            candidates,
            candidate_events,
            execution_events,
            closed_once,
            config,
        )
        _expire_candidates(
            run_id,
            date,
            prev_date,
            prev_close_row,
            open_row,
            open_valid_row,
            close_row,
            candidates,
            positions,
            candidate_events,
            execution_events,
            closed_once,
            config,
        )

        if prev_date is not None and _is_rebalance_date(
            date, last_rebalance, config.rebalance, trading_date_index
        ):
            signal_date = prev_date
            eligible = _eligible_symbols(
                signal_date,
                date,
                prev_close_row,
                prev_imputed_row,
                candidates,
                signal_rows,
                config,
                closed_once,
            )
            if config.exit_on_signal_loss:
                for symbol in list(positions):
                    if symbol not in eligible:
                        realized_today += _sell_position(
                            run_id,
                            date,
                            signal_date,
                            symbol,
                            prev_close_row,
                            open_row,
                            open_valid_row,
                            close_row,
                            positions,
                            execution_events,
                            closed_once,
                            reason="signal_loss",
                        )
            target_symbols = sorted(
                set(eligible) | (set(positions) if not config.exit_on_signal_loss else set())
            )
            weights = _weights_for_symbols(wide, date, target_symbols, config)
            for symbol in target_symbols:
                if not _has_price(close_row, symbol):
                    continue
                report = candidates.get(symbol)
                if not report:
                    continue
                fill_price, fill_rule = _resolve_fill(open_row, close_row, open_valid_row, symbol)
                decision_price = _observed_price(prev_close_row, symbol)
                if symbol not in positions:
                    positions[symbol] = Position(
                        symbol=symbol,
                        company=str(report["company"]),
                        report_id=str(report["report_id"]),
                        entry_date=date,
                        entry_price=fill_price,
                        weight=float(weights.get(symbol, 0.0)),
                        target_price=_float_or_none(report.get("target_price")),
                    )
                    execution_events.append(
                        _execution_event(
                            run_id,
                            date,
                            positions[symbol],
                            "buy",
                            "rebalance_entry",
                            signal_date=signal_date,
                            decision_price=decision_price,
                            fill_price=fill_price,
                            fill_rule=fill_rule,
                        )
                    )
                else:
                    old_weight = positions[symbol].weight
                    new_weight = float(weights.get(symbol, 0.0))
                    positions[symbol].weight = new_weight
                    positions[symbol].target_price = _float_or_none(report.get("target_price"))
                    positions[symbol].report_id = str(report["report_id"])
                    if abs(old_weight - new_weight) > 1e-6:
                        execution_events.append(
                            _execution_event(
                                run_id,
                                date,
                                positions[symbol],
                                "rebalance",
                                "weight_update",
                                signal_date=signal_date,
                                decision_price=decision_price,
                                fill_price=fill_price,
                                fill_rule=fill_rule,
                            )
                        )
            last_rebalance = date

        equity_value *= max(0.0, 1.0 + portfolio_return)
        cumulative_return = equity_value - 1.0
        equity_rows.append(
            {
                "run_id": run_id,
                "date": date.date().isoformat(),
                "portfolio_return": portfolio_return,
                "realized_return": realized_today,
                "cumulative_return": cumulative_return,
                "equity": equity_value,
                "candidate_count": len(candidates),
                "execution_count": len(positions),
                "cash_weight": max(0.0, 1.0 - sum(position.weight for position in positions.values())),
            }
        )
        for position in positions.values():
            close = float(close_row[position.symbol]) if _has_price(close_row, position.symbol) else math.nan
            sig = signal_rows.get((prev_date or date, position.symbol), {})
            position_rows.append(
                {
                    "run_id": run_id,
                    "date": date.date().isoformat(),
                    "symbol": position.symbol,
                    "company": position.company,
                    "report_id": position.report_id,
                    "weight": position.weight,
                    "close": close,
                    "target_price": position.target_price,
                    "gross_return": close / position.entry_price - 1.0 if close and close > 0 else None,
                    "model_contribution": position.contribution_return,
                    "mtt_pass": bool(sig.get("mtt_pass", False)),
                }
            )
        prev_date = date

    # Phase 2c — end-of-sim delisting sweep. Any position still open whose
    # symbol's last valid price is more than ``DELISTING_GAP_DAYS`` trading
    # days before the sim end gets an explicit ``delisting`` sell event. The
    # fill is the last observed close with ``fill_rule='delisting_last_close'``
    # so callers can discount it if they want clean exits only.
    if trading_dates:
        last_date = trading_dates[-1]
        last_idx = len(trading_dates) - 1
        last_active_idx: dict[str, int] = {}
        for idx, d in enumerate(trading_dates):
            row = wide.loc[d]
            for symbol in row.index:
                if _has_price(row, symbol):
                    last_active_idx[symbol] = idx
        for symbol in list(positions):
            last_seen = last_active_idx.get(symbol)
            if last_seen is None or last_idx - last_seen < DELISTING_GAP_DAYS:
                continue
            position = positions.pop(symbol)
            last_seen_date = trading_dates[last_seen]
            last_close_row = wide.loc[last_seen_date]
            last_close = (
                float(last_close_row[symbol]) if _has_price(last_close_row, symbol) else position.entry_price
            )
            execution_events.append(
                _execution_event(
                    run_id,
                    last_date,
                    position,
                    "sell",
                    "delisting",
                    signal_date=last_seen_date,
                    decision_price=last_close,
                    fill_price=last_close,
                    fill_rule="delisting_last_close",
                )
            )
            closed_once.add(symbol)

    equity = pd.DataFrame(equity_rows)
    executions = pd.DataFrame(execution_events)
    summary = pd.DataFrame([_summarize(run_id, config, equity, executions, positions)])
    return {
        "strategy_runs": summary,
        "equity_daily": equity,
        "candidate_pool_events": pd.DataFrame(candidate_events),
        "execution_events": executions,
        "positions_daily": pd.DataFrame(position_rows),
        "signals_daily": signals.assign(date=signals["date"].dt.date.astype(str))
        if not signals.empty
        else signals,
    }


def stable_run_id(config: BacktestConfig) -> str:
    payload = repr(sorted(config.to_dict().items()))
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:12]


def empty_result(run_id: str, config: BacktestConfig) -> dict[str, pd.DataFrame]:
    summary = StrategySummary(
        run_id=run_id,
        strategy_name=config.name,
        weighting=config.weighting,
        entry_rule=config.entry_rule,
        rebalance=config.rebalance,
        stop_loss_pct=config.stop_loss_pct,
        reward_risk=config.reward_risk,
        max_pool_months=config.max_pool_months,
        target_hit_multiplier=config.target_hit_multiplier,
        lookback_days=config.lookback_days,
        final_wealth=1.0,
        total_return=0.0,
        cagr=None,
        annualized_volatility=None,
        sharpe=None,
        sortino=None,
        max_drawdown=0.0,
        calmar=None,
        realized_return=0.0,
        live_return=0.0,
        exposure_ratio=0.0,
        average_positions=0.0,
        max_positions=0,
        turnover_events=0,
        trade_count=0,
        win_rate=None,
        target_hit_rate=None,
        stop_loss_hit_rate=None,
        average_holding_days=None,
        objective=0.0,
        status="empty",
    )
    # Pydantic-v2-friendly dict; include Phase 2b columns as None so that
    # DataFrames produced from empty + non-empty runs share a schema.
    row = {
        **summary.model_dump(mode="json"),
        "open_position_count": 0,
        "sortino_in_sample": None,
        "sortino_oos_tail": None,
        "sharpe_oos_tail": None,
        "max_drawdown_oos_tail": None,
        "fold_count": None,
    }
    return {
        "strategy_runs": pd.DataFrame([row]),
        "equity_daily": pd.DataFrame(),
        "candidate_pool_events": pd.DataFrame(),
        "execution_events": pd.DataFrame(),
        "positions_daily": pd.DataFrame(),
        "signals_daily": pd.DataFrame(),
    }


def _prepare_reports(reports: pd.DataFrame) -> pd.DataFrame:
    frame = reports.copy()
    if "target_price" not in frame:
        frame["target_price"] = frame.get("base_target")
    frame["publication_date"] = pd.to_datetime(frame["publication_date"])
    frame = frame.dropna(subset=["symbol", "publication_date"])
    frame = frame[frame["symbol"].astype(str) != ""].copy()
    return frame


def _prepare_prices(prices: pd.DataFrame) -> pd.DataFrame:
    """Normalise the price frame and apply Phase 2b's NaN-close policy.

    Plan Principle 6 (extended in Phase 2b): ``close`` values are forward-filled
    within each symbol (last observation carried forward) instead of being
    dropped. The additive ``close_imputed`` boolean column flags forward-filled
    rows so downstream consumers — including the MTM loop — can exclude them
    from return computation (per code-review CRITICAL-3 fix).

    The shift is schema-visible via ``close.nan_policy='forward_fill_then_flag'``
    on the DailyPrice model, and the companion sidecar
    ``docs/schemas/daily_prices.v2.schema.json`` acknowledges the change for
    the Principle-6 semantic-drift guard.

    ``open_imputed`` is set whenever the row's ``open`` value was missing /
    aliased to close; the engine uses this to label fill_rule honestly.
    """
    frame = prices.copy()
    frame["date"] = pd.to_datetime(frame["date"]).dt.tz_localize(None)
    frame["symbol"] = frame["symbol"].astype(str)
    frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
    if "open" in frame.columns:
        frame["open_raw"] = pd.to_numeric(frame["open"], errors="coerce")
    else:
        frame["open_raw"] = pd.NA
    frame = frame.dropna(subset=["date", "symbol"]).sort_values(["symbol", "date"])
    frame["close_imputed"] = frame["close"].isna()
    frame["close"] = frame.groupby("symbol", sort=False)["close"].ffill()
    # Drop leading-NaN rows (a symbol whose very first observation is NaN has
    # nothing to forward-fill from; those rows must still be dropped).
    frame = frame.dropna(subset=["close"])
    # Open provenance — ``open_valid`` is True only when the row carried a
    # genuine open quote; otherwise ``_resolve_fill`` falls back to close
    # with ``fill_rule='close_fallback'`` (per code-review CRITICAL-2 fix).
    frame["open_valid"] = frame["open_raw"].notna() & (pd.to_numeric(frame["open_raw"], errors="coerce") > 0)
    frame["open"] = frame["open_raw"].where(frame["open_valid"], frame["close"])
    return frame.drop(columns=["open_raw"]).sort_values(["date", "symbol"]).reset_index(drop=True)


def _candidate_event(
    run_id: str,
    date: pd.Timestamp,
    report: dict[str, Any],
    event_type: str,
    reason: str,
    close: float,
    count: int,
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "date": date.date().isoformat(),
        "symbol": report["symbol"],
        "company": report.get("company", ""),
        "report_id": report.get("report_id", ""),
        "event_type": event_type,
        "reason": reason,
        "close": close,
        "target_price": _float_or_none(report.get("target_price")),
        "candidate_count_after": count,
    }


def _execution_event(
    run_id: str,
    date: pd.Timestamp,
    position: Position,
    event_type: str,
    reason: str,
    *,
    signal_date: pd.Timestamp | None = None,
    decision_price: float | None = None,
    fill_price: float,
    fill_rule: str,
) -> dict[str, Any]:
    gross = fill_price / position.entry_price - 1.0 if fill_price > 0 and position.entry_price > 0 else None
    signal_date_iso = signal_date.date().isoformat() if signal_date is not None else None
    return {
        "run_id": run_id,
        "date": date.date().isoformat(),
        "symbol": position.symbol,
        "company": position.company,
        "report_id": position.report_id,
        "event_type": event_type,
        "reason": reason,
        "price": fill_price,  # back-compat: existing consumers read ``price`` and expect the actual fill
        "weight": position.weight,
        "entry_date": position.entry_date.date().isoformat(),
        "entry_price": position.entry_price,
        "target_price": position.target_price,
        "gross_return": gross,
        "realized_return": position.contribution_return if event_type == "sell" else None,
        "holding_days": (date - position.entry_date).days,
        "signal_date": signal_date_iso,
        "decision_price": decision_price,
        "fill_price": fill_price,
        "fill_rule": fill_rule,
    }


def _observed_price(prev_close_row: pd.Series | None, symbol: str) -> float | None:
    """Decision-side observation: t-1 close. Returns ``None`` when no prior
    observation exists (first trading day) so callers MUST skip the symbol
    instead of leaking same-day close into a decision (code-review CRITICAL-1).
    """
    if prev_close_row is None:
        return None
    if _has_price(prev_close_row, symbol):
        return float(prev_close_row[symbol])
    return None


def _resolve_fill(
    open_row: pd.Series,
    close_row: pd.Series,
    open_valid_row: pd.Series,
    symbol: str,
) -> tuple[float, str]:
    """Phase 2a fill policy + code-review CRITICAL-2 fix.

    ``fill_rule='open'`` is stamped only when the original CSV row carried a
    genuine ``open`` quote (``open_valid_row[symbol]`` True). Otherwise the
    fill drops to today's close with ``fill_rule='close_fallback'`` so a
    missing-open observation cannot be silently mislabelled as an open fill.
    """
    is_open_valid = bool(open_valid_row.get(symbol, False))
    if is_open_valid and _has_price(open_row, symbol):
        return float(open_row[symbol]), "open"
    return float(close_row[symbol]), "close_fallback"


def _sell_position(
    run_id: str,
    date: pd.Timestamp,
    signal_date: pd.Timestamp | None,
    symbol: str,
    prev_close_row: pd.Series | None,
    open_row: pd.Series,
    open_valid_row: pd.Series,
    close_row: pd.Series,
    positions: dict[str, Position],
    execution_events: list[dict[str, Any]],
    closed_once: set[str],
    reason: str,
) -> float:
    if symbol not in positions or not _has_price(close_row, symbol):
        return 0.0
    position = positions.pop(symbol)
    fill_price, fill_rule = _resolve_fill(open_row, close_row, open_valid_row, symbol)
    decision_price = _observed_price(prev_close_row, symbol)
    execution_events.append(
        _execution_event(
            run_id,
            date,
            position,
            "sell",
            reason,
            signal_date=signal_date,
            decision_price=decision_price,
            fill_price=fill_price,
            fill_rule=fill_rule,
        )
    )
    closed_once.add(symbol)
    return position.contribution_return


def _exit_positions_for_risk(
    run_id: str,
    date: pd.Timestamp,
    prev_date: pd.Timestamp | None,
    prev_close_row: pd.Series | None,
    open_row: pd.Series,
    open_valid_row: pd.Series,
    close_row: pd.Series,
    positions: dict[str, Position],
    candidates: dict[str, dict[str, Any]],
    candidate_events: list[dict[str, Any]],
    execution_events: list[dict[str, Any]],
    closed_once: set[str],
    config: BacktestConfig,
) -> float:
    realized = 0.0
    for symbol, position in list(positions.items()):
        # Decision: observe prev_close (t-1). Fill: next-open / fallback close.
        decision_price = _observed_price(prev_close_row, symbol)
        if decision_price is None or not _has_price(close_row, symbol):
            # No prior observation (first bar) OR no current price — skip.
            # CRITICAL-1 fix: do NOT fall back to same-day close.
            continue
        reason = ""
        if decision_price <= position.entry_price * (1.0 - config.stop_loss_pct):
            reason = "stop_loss"
        elif decision_price >= position.entry_price * (1.0 + config.stop_loss_pct * config.reward_risk):
            reason = "take_profit_rr"
        elif position.target_price and decision_price >= position.target_price * config.target_hit_multiplier:
            reason = "target_hit"
        if reason:
            realized += _sell_position(
                run_id,
                date,
                prev_date,
                symbol,
                prev_close_row,
                open_row,
                open_valid_row,
                close_row,
                positions,
                execution_events,
                closed_once,
                reason,
            )
            if reason == "target_hit" and symbol in candidates:
                report = candidates.pop(symbol)
                candidate_events.append(
                    _candidate_event(
                        run_id, date, report, "candidate_exit", "target_hit", decision_price, len(candidates)
                    )
                )
    return realized


def _expire_candidates(
    run_id: str,
    date: pd.Timestamp,
    prev_date: pd.Timestamp | None,
    prev_close_row: pd.Series | None,
    open_row: pd.Series,
    open_valid_row: pd.Series,
    close_row: pd.Series,
    candidates: dict[str, dict[str, Any]],
    positions: dict[str, Position],
    candidate_events: list[dict[str, Any]],
    execution_events: list[dict[str, Any]],
    closed_once: set[str],
    config: BacktestConfig,
) -> None:
    max_age_days = int(round(config.max_pool_months * 30.4375))
    for symbol, report in list(candidates.items()):
        decision_price = _observed_price(prev_close_row, symbol)
        target = _float_or_none(report.get("target_price"))
        age = (date - pd.Timestamp(report["publication_date"])).days
        reason = ""
        # Target-hit needs an observation; aging-out is a calendar rule that
        # fires regardless of whether prev_close is available.
        if decision_price is not None and target and decision_price >= target * config.target_hit_multiplier:
            reason = "target_hit"
        elif age > max_age_days:
            reason = "aging_out"
        if reason:
            candidates.pop(symbol)
            event_close = (
                decision_price
                if decision_price is not None
                else (float(close_row[symbol]) if _has_price(close_row, symbol) else 0.0)
            )
            candidate_events.append(
                _candidate_event(run_id, date, report, "candidate_exit", reason, event_close, len(candidates))
            )
            if symbol in positions:
                _sell_position(
                    run_id,
                    date,
                    prev_date,
                    symbol,
                    prev_close_row,
                    open_row,
                    open_valid_row,
                    close_row,
                    positions,
                    execution_events,
                    closed_once,
                    f"candidate_{reason}",
                )


def _eligible_symbols(
    signal_date: pd.Timestamp,
    trade_date: pd.Timestamp,
    prev_close_row: pd.Series | None,
    prev_imputed_row: pd.Series | None,
    candidates: dict[str, dict[str, Any]],
    signal_rows: dict[tuple[pd.Timestamp, str], dict],
    config: BacktestConfig,
    closed_once: set[str],
) -> list[str]:
    if prev_close_row is None:
        return []
    eligible = []
    for symbol, report in candidates.items():
        if not config.allow_reentry and symbol in closed_once:
            continue
        if not _has_price(prev_close_row, symbol):
            continue
        # CRITICAL-3 / MAJOR-2: imputed (forward-filled) prev-close cannot be
        # trusted for entry decisions because target_upside on a stale price
        # systematically over-states upside as the real price decays toward
        # zero / NaN. Treat imputed bars as no observation.
        if prev_imputed_row is not None and bool(prev_imputed_row.get(symbol, True)):
            continue
        sig = signal_rows.get((signal_date, symbol), {})
        mtt = bool(sig.get("mtt_pass", False))
        target = _float_or_none(report.get("target_price"))
        # Phase 2a look-ahead fix: target_upside now uses the observed
        # (t-1) close, not today's close.
        decision_close = float(prev_close_row[symbol])
        target_upside = (target / decision_close - 1.0) if target and decision_close > 0 else None
        target_ok = target_upside is not None and target_upside >= config.min_target_upside
        if config.entry_rule == "mtt":
            ok = mtt
        elif config.entry_rule == "target_only":
            ok = target_ok
        else:
            ok = mtt and target_ok
        if ok:
            eligible.append(symbol)
    return eligible


def _weights_for_symbols(
    wide: pd.DataFrame, date: pd.Timestamp, symbols: list[str], config: BacktestConfig
) -> dict[str, float]:
    if not symbols:
        return {}
    lookback = wide.loc[wide.index < date, symbols].tail(config.lookback_days + 1)
    returns = lookback.pct_change().replace([np.inf, -np.inf], np.nan).dropna(how="all")
    return optimize_execution_weights(returns, symbols, config.weighting, config.risk_free_rate)


def _is_rebalance_date(
    date: pd.Timestamp,
    last_rebalance: pd.Timestamp | None,
    frequency: str,
    trading_date_index: dict[pd.Timestamp, int],
) -> bool:
    """Phase 2a: weekly / biweekly cadence counts trading days, not calendar
    days. Monthly stays calendar-based (same month boundary).
    """
    if last_rebalance is None or frequency == "daily":
        return True
    now_idx = trading_date_index.get(date)
    last_idx = trading_date_index.get(last_rebalance)
    if now_idx is not None and last_idx is not None:
        gap_trading = now_idx - last_idx
    else:
        # Defensive fallback — approximate 5 trading days per calendar week.
        gap_trading = int((date - last_rebalance).days * 5 / 7)
    if frequency == "weekly":
        return gap_trading >= 5
    if frequency == "biweekly":
        return gap_trading >= 10
    if frequency == "monthly":
        return (date.year, date.month) != (last_rebalance.year, last_rebalance.month)
    return False


def _annualized_sharpe(returns: pd.Series, risk_free: float) -> float | None:
    if len(returns) <= 1:
        return None
    vol = float(returns.std() * math.sqrt(252))
    if vol == 0.0:
        return None
    return float((returns.mean() * 252 - risk_free) / vol)


def _annualized_sortino(returns: pd.Series, risk_free: float) -> float | None:
    if len(returns) <= 1:
        return None
    downside = returns[returns < 0]
    if len(downside) <= 1:
        return None
    downside_vol = float(downside.std() * math.sqrt(252))
    if downside_vol == 0.0:
        return None
    return float((returns.mean() * 252 - risk_free) / downside_vol)


def _equity_max_drawdown(returns: pd.Series) -> float:
    if returns.empty:
        return 0.0
    equity = (1.0 + returns).cumprod()
    drawdown = equity / equity.cummax() - 1.0
    return abs(float(drawdown.min()))


def _oos_tail_stats(returns: pd.Series, risk_free: float) -> dict[str, float | int | None]:
    """Compute 3-segment OOS-tail diagnostics, not a true walk-forward replay.

    This splits one backtest return series into three disjoint contiguous
    chunks, treats each chunk's first 70% as in-sample and last 30% as an OOS
    tail, then averages the tail diagnostics. A true walk-forward would replay
    the backtest per expanding-window fold and is intentionally left as a
    follow-up. See ``docs/decisions/phase-2-objective.md``.
    """
    fold_count = PHASE_2_FOLD_COUNT
    oos_frac = PHASE_2_OOS_FRACTION
    n = len(returns)
    if n < fold_count * 10:
        return {
            "sortino_in_sample": None,
            "sortino_oos_tail": None,
            "sharpe_oos_tail": None,
            "max_drawdown_oos_tail": None,
            "fold_count": fold_count,
        }
    fold_size = n // fold_count
    is_sortinos: list[float] = []
    oos_sortinos: list[float] = []
    oos_sharpes: list[float] = []
    oos_drawdowns: list[float] = []
    for i in range(fold_count):
        start = i * fold_size
        end = start + fold_size if i < fold_count - 1 else n
        chunk = returns.iloc[start:end]
        if len(chunk) < 5:
            continue
        split = max(1, int(round(len(chunk) * (1.0 - oos_frac))))
        is_chunk = chunk.iloc[:split]
        oos_chunk = chunk.iloc[split:]
        is_sortino = _annualized_sortino(is_chunk, risk_free)
        oos_sortino = _annualized_sortino(oos_chunk, risk_free)
        oos_sharpe = _annualized_sharpe(oos_chunk, risk_free)
        if is_sortino is not None:
            is_sortinos.append(is_sortino)
        if oos_sortino is not None:
            oos_sortinos.append(oos_sortino)
        if oos_sharpe is not None:
            oos_sharpes.append(oos_sharpe)
        oos_drawdowns.append(_equity_max_drawdown(oos_chunk))

    return {
        "sortino_in_sample": float(np.mean(is_sortinos)) if is_sortinos else None,
        "sortino_oos_tail": float(np.mean(oos_sortinos)) if oos_sortinos else None,
        "sharpe_oos_tail": float(np.mean(oos_sharpes)) if oos_sharpes else None,
        "max_drawdown_oos_tail": float(max(oos_drawdowns)) if oos_drawdowns else None,
        "fold_count": fold_count,
    }


def _resolve_objective(config: BacktestConfig, total_return: float, sortino_oos_tail: float | None) -> float:
    """Default objective is Sortino OOS-tail per docs/decisions/phase-2-objective.md.

    The ``BacktestConfig.legacy_objective`` flag (was the
    ``SNUSMIC_LEGACY_OBJECTIVE=1`` env-var pre code-review) restores
    ``total_return`` and is kept through Phase 8 per plan scope. The flag
    does NOT revive the Phase 2a look-ahead fix — that stays unconditional.
    Because it lives on the config, the ``run_id`` hash diverges between
    modes so legacy runs and Sortino-OOS runs cannot be mixed in
    ``strategy_runs.csv`` rows with the same id.
    """
    if config.legacy_objective:
        return float(total_return)
    if sortino_oos_tail is not None and math.isfinite(sortino_oos_tail):
        return float(sortino_oos_tail)
    # Fallback when OOS cannot be computed (short runs): use total_return so
    # optimisers still have a finite signal; flagged via `status="ok_short"`.
    return float(total_return)


def _summarize(
    run_id: str,
    config: BacktestConfig,
    equity: pd.DataFrame,
    executions: pd.DataFrame,
    open_positions: dict[str, Position],
) -> dict[str, Any]:
    if equity.empty:
        return empty_result(run_id, config)["strategy_runs"].iloc[0].to_dict()
    returns = equity["portfolio_return"].astype(float)
    final_wealth = float(equity["equity"].iloc[-1])
    total_return = final_wealth - 1.0
    start = pd.to_datetime(equity["date"].iloc[0])
    end = pd.to_datetime(equity["date"].iloc[-1])
    years = max((end - start).days / 365.25, 1 / 365.25)
    cagr = final_wealth ** (1.0 / years) - 1.0 if final_wealth > 0 else -1.0
    vol = float(returns.std() * math.sqrt(252)) if len(returns) > 1 else None
    sharpe = _annualized_sharpe(returns, config.risk_free_rate)
    sortino = _annualized_sortino(returns, config.risk_free_rate)
    equity_curve = equity["equity"].astype(float)
    drawdown = equity_curve / equity_curve.cummax() - 1.0
    max_drawdown = abs(float(drawdown.min()))
    calmar = None if max_drawdown == 0 else cagr / max_drawdown
    sells = executions[executions["event_type"] == "sell"] if not executions.empty else pd.DataFrame()
    wins = sells[sells["gross_return"].astype(float) > 0] if not sells.empty else pd.DataFrame()
    realized = float(sells["realized_return"].dropna().astype(float).sum()) if not sells.empty else 0.0

    tail_stats = _oos_tail_stats(returns, config.risk_free_rate)
    status = "ok" if len(returns) >= PHASE_2_FOLD_COUNT * 10 else "ok_short"

    return {
        "run_id": run_id,
        "strategy_name": config.name,
        "weighting": config.weighting,
        "entry_rule": config.entry_rule,
        "rebalance": config.rebalance,
        "stop_loss_pct": config.stop_loss_pct,
        "reward_risk": config.reward_risk,
        "max_pool_months": config.max_pool_months,
        "target_hit_multiplier": config.target_hit_multiplier,
        "lookback_days": config.lookback_days,
        "final_wealth": final_wealth,
        "total_return": total_return,
        "cagr": cagr,
        "annualized_volatility": vol,
        "sharpe": sharpe,
        "sortino": sortino,
        "max_drawdown": max_drawdown,
        "calmar": calmar,
        "realized_return": realized,
        "live_return": total_return - realized,
        "exposure_ratio": float((equity["execution_count"].astype(int) > 0).mean()),
        "average_positions": float(equity["execution_count"].astype(int).mean()),
        "max_positions": int(equity["execution_count"].astype(int).max()),
        "turnover_events": int(
            len(executions[executions["event_type"].isin(["buy", "sell", "rebalance"])])
            if not executions.empty
            else 0
        ),
        "trade_count": int(len(sells)),
        "win_rate": None if sells.empty else float(len(wins) / len(sells)),
        "target_hit_rate": None
        if sells.empty
        else float(sells["reason"].astype(str).str.contains("target|take_profit").mean()),
        "stop_loss_hit_rate": None if sells.empty else float((sells["reason"] == "stop_loss").mean()),
        "average_holding_days": None if sells.empty else float(sells["holding_days"].astype(float).mean()),
        "objective": _resolve_objective(config, total_return, tail_stats["sortino_oos_tail"]),
        "open_position_count": len(open_positions),
        "status": status,
        "sortino_in_sample": tail_stats["sortino_in_sample"],
        "sortino_oos_tail": tail_stats["sortino_oos_tail"],
        "sharpe_oos_tail": tail_stats["sharpe_oos_tail"],
        "max_drawdown_oos_tail": tail_stats["max_drawdown_oos_tail"],
        "fold_count": tail_stats["fold_count"],
    }


def _has_price(row: pd.Series, symbol: str) -> bool:
    if symbol not in row:
        return False
    value = row[symbol]
    return pd.notna(value) and float(value) > 0


def _float_or_none(value: Any) -> float | None:
    if value is None or value == "" or pd.isna(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
