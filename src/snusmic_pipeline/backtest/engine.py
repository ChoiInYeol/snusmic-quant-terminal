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
    trading_dates = [pd.Timestamp(date) for date in wide.index if date >= reports["publication_date"].min()]
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
        portfolio_return = 0.0
        realized_today = 0.0
        if prev_date is not None:
            prev_close = wide.loc[prev_date]
            for position in positions.values():
                if _has_price(prev_close, position.symbol) and _has_price(close_row, position.symbol):
                    asset_return = float(close_row[position.symbol]) / float(prev_close[position.symbol]) - 1.0
                    contribution = position.weight * asset_return
                    position.contribution_return += contribution
                    portfolio_return += contribution

        while pending_idx < len(report_rows) and pd.Timestamp(report_rows[pending_idx]["publication_date"]) < date:
            report = report_rows[pending_idx]
            pending_idx += 1
            if not _has_price(close_row, report["symbol"]):
                continue
            event_type = "candidate_add" if report["symbol"] not in candidates else "candidate_refresh"
            candidates[report["symbol"]] = {**report, "eligible_date": date}
            candidate_events.append(_candidate_event(run_id, date, report, event_type, "report_publication", float(close_row[report["symbol"]]), len(candidates)))

        realized_today += _exit_positions_for_risk(
            run_id,
            date,
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
            close_row,
            candidates,
            positions,
            candidate_events,
            execution_events,
            closed_once,
            config,
        )

        if prev_date is not None and _is_rebalance_date(date, last_rebalance, config.rebalance):
            signal_date = prev_date
            eligible = _eligible_symbols(signal_date, date, close_row, candidates, signal_rows, config, closed_once)
            if config.exit_on_signal_loss:
                for symbol in list(positions):
                    if symbol not in eligible:
                        realized_today += _sell_position(
                            run_id,
                            date,
                            symbol,
                            close_row,
                            positions,
                            execution_events,
                            closed_once,
                            reason="signal_loss",
                        )
            target_symbols = sorted(set(eligible) | (set(positions) if not config.exit_on_signal_loss else set()))
            weights = _weights_for_symbols(wide, date, target_symbols, config)
            for symbol in target_symbols:
                if not _has_price(close_row, symbol):
                    continue
                report = candidates.get(symbol)
                if not report:
                    continue
                if symbol not in positions:
                    positions[symbol] = Position(
                        symbol=symbol,
                        company=str(report["company"]),
                        report_id=str(report["report_id"]),
                        entry_date=date,
                        entry_price=float(close_row[symbol]),
                        weight=float(weights.get(symbol, 0.0)),
                        target_price=_float_or_none(report.get("target_price")),
                    )
                    execution_events.append(_execution_event(run_id, date, positions[symbol], "buy", "rebalance_entry", float(close_row[symbol])))
                else:
                    old_weight = positions[symbol].weight
                    new_weight = float(weights.get(symbol, 0.0))
                    positions[symbol].weight = new_weight
                    positions[symbol].target_price = _float_or_none(report.get("target_price"))
                    positions[symbol].report_id = str(report["report_id"])
                    if abs(old_weight - new_weight) > 1e-6:
                        execution_events.append(_execution_event(run_id, date, positions[symbol], "rebalance", "weight_update", float(close_row[symbol])))
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
                    "rs_score": _float_or_none(sig.get("rs_score")),
                }
            )
        prev_date = date

    equity = pd.DataFrame(equity_rows)
    executions = pd.DataFrame(execution_events)
    summary = pd.DataFrame([_summarize(run_id, config, equity, executions, positions)])
    return {
        "strategy_runs": summary,
        "equity_daily": equity,
        "candidate_pool_events": pd.DataFrame(candidate_events),
        "execution_events": executions,
        "positions_daily": pd.DataFrame(position_rows),
        "signals_daily": signals.assign(date=signals["date"].dt.date.astype(str)) if not signals.empty else signals,
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
        rs_threshold=config.rs_threshold,
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
    return {
        "strategy_runs": pd.DataFrame([summary.__dict__]),
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
    frame = prices.copy()
    frame["date"] = pd.to_datetime(frame["date"])
    frame["symbol"] = frame["symbol"].astype(str)
    frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
    return frame.dropna(subset=["date", "symbol", "close"]).sort_values(["date", "symbol"])


def _candidate_event(run_id: str, date: pd.Timestamp, report: dict[str, Any], event_type: str, reason: str, close: float, count: int) -> dict[str, Any]:
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


def _execution_event(run_id: str, date: pd.Timestamp, position: Position, event_type: str, reason: str, price: float) -> dict[str, Any]:
    gross = price / position.entry_price - 1.0 if price > 0 and position.entry_price > 0 else None
    return {
        "run_id": run_id,
        "date": date.date().isoformat(),
        "symbol": position.symbol,
        "company": position.company,
        "report_id": position.report_id,
        "event_type": event_type,
        "reason": reason,
        "price": price,
        "weight": position.weight,
        "entry_date": position.entry_date.date().isoformat(),
        "entry_price": position.entry_price,
        "target_price": position.target_price,
        "gross_return": gross,
        "realized_return": position.contribution_return if event_type == "sell" else None,
        "holding_days": (date - position.entry_date).days,
    }


def _sell_position(
    run_id: str,
    date: pd.Timestamp,
    symbol: str,
    close_row: pd.Series,
    positions: dict[str, Position],
    execution_events: list[dict[str, Any]],
    closed_once: set[str],
    reason: str,
) -> float:
    if symbol not in positions or not _has_price(close_row, symbol):
        return 0.0
    position = positions.pop(symbol)
    price = float(close_row[symbol])
    execution_events.append(_execution_event(run_id, date, position, "sell", reason, price))
    closed_once.add(symbol)
    return position.contribution_return


def _exit_positions_for_risk(
    run_id: str,
    date: pd.Timestamp,
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
        if not _has_price(close_row, symbol):
            continue
        close = float(close_row[symbol])
        reason = ""
        if close <= position.entry_price * (1.0 - config.stop_loss_pct):
            reason = "stop_loss"
        elif close >= position.entry_price * (1.0 + config.stop_loss_pct * config.reward_risk):
            reason = "take_profit_rr"
        elif position.target_price and close >= position.target_price * config.target_hit_multiplier:
            reason = "target_hit"
        if reason:
            realized += _sell_position(run_id, date, symbol, close_row, positions, execution_events, closed_once, reason)
            if reason == "target_hit" and symbol in candidates:
                report = candidates.pop(symbol)
                candidate_events.append(_candidate_event(run_id, date, report, "candidate_exit", "target_hit", close, len(candidates)))
    return realized


def _expire_candidates(
    run_id: str,
    date: pd.Timestamp,
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
        if not _has_price(close_row, symbol):
            continue
        close = float(close_row[symbol])
        target = _float_or_none(report.get("target_price"))
        age = (date - pd.Timestamp(report["publication_date"])).days
        reason = ""
        if target and close >= target * config.target_hit_multiplier:
            reason = "target_hit"
        elif age > max_age_days:
            reason = "aging_out"
        if reason:
            candidates.pop(symbol)
            candidate_events.append(_candidate_event(run_id, date, report, "candidate_exit", reason, close, len(candidates)))
            if symbol in positions:
                _sell_position(run_id, date, symbol, close_row, positions, execution_events, closed_once, f"candidate_{reason}")


def _eligible_symbols(
    signal_date: pd.Timestamp,
    trade_date: pd.Timestamp,
    close_row: pd.Series,
    candidates: dict[str, dict[str, Any]],
    signal_rows: dict[tuple[pd.Timestamp, str], dict],
    config: BacktestConfig,
    closed_once: set[str],
) -> list[str]:
    eligible = []
    for symbol, report in candidates.items():
        if not config.allow_reentry and symbol in closed_once:
            continue
        if not _has_price(close_row, symbol):
            continue
        sig = signal_rows.get((signal_date, symbol), {})
        mtt = bool(sig.get("mtt_pass", False))
        rs = _float_or_none(sig.get("rs_score"))
        rs_ok = rs is not None and rs >= config.rs_threshold
        target = _float_or_none(report.get("target_price"))
        close = float(close_row[symbol])
        target_upside = (target / close - 1.0) if target and close > 0 else None
        target_ok = target_upside is not None and target_upside >= config.min_target_upside
        if config.entry_rule == "mtt_or_rs":
            ok = mtt or rs_ok
        elif config.entry_rule == "mtt_and_rs":
            ok = mtt and rs_ok
        elif config.entry_rule == "target_only":
            ok = target_ok
        else:
            ok = (mtt and target_ok) or (rs_ok and target_ok)
        if ok:
            eligible.append(symbol)
    return eligible


def _weights_for_symbols(wide: pd.DataFrame, date: pd.Timestamp, symbols: list[str], config: BacktestConfig) -> dict[str, float]:
    if not symbols:
        return {}
    lookback = wide.loc[wide.index < date, symbols].tail(config.lookback_days + 1)
    returns = lookback.pct_change().replace([np.inf, -np.inf], np.nan).dropna(how="all")
    return optimize_execution_weights(returns, symbols, config.weighting, config.risk_free_rate)


def _is_rebalance_date(date: pd.Timestamp, last_rebalance: pd.Timestamp | None, frequency: str) -> bool:
    if last_rebalance is None or frequency == "daily":
        return True
    if frequency == "weekly":
        return (date - last_rebalance).days >= 7
    if frequency == "biweekly":
        return (date - last_rebalance).days >= 14
    if frequency == "monthly":
        return (date.year, date.month) != (last_rebalance.year, last_rebalance.month)
    return False


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
    sharpe = None if not vol else float((returns.mean() * 252 - config.risk_free_rate) / vol)
    downside = returns[returns < 0]
    downside_vol = float(downside.std() * math.sqrt(252)) if len(downside) > 1 else None
    sortino = None if not downside_vol else float((returns.mean() * 252 - config.risk_free_rate) / downside_vol)
    equity_curve = equity["equity"].astype(float)
    drawdown = equity_curve / equity_curve.cummax() - 1.0
    max_drawdown = abs(float(drawdown.min()))
    calmar = None if max_drawdown == 0 else cagr / max_drawdown
    sells = executions[executions["event_type"] == "sell"] if not executions.empty else pd.DataFrame()
    wins = sells[sells["gross_return"].astype(float) > 0] if not sells.empty else pd.DataFrame()
    realized = float(sells["realized_return"].dropna().astype(float).sum()) if not sells.empty else 0.0
    return {
        "run_id": run_id,
        "strategy_name": config.name,
        "weighting": config.weighting,
        "entry_rule": config.entry_rule,
        "rebalance": config.rebalance,
        "rs_threshold": config.rs_threshold,
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
        "turnover_events": int(len(executions[executions["event_type"].isin(["buy", "sell", "rebalance"])]) if not executions.empty else 0),
        "trade_count": int(len(sells)),
        "win_rate": None if sells.empty else float(len(wins) / len(sells)),
        "target_hit_rate": None if sells.empty else float(sells["reason"].astype(str).str.contains("target|take_profit").mean()),
        "stop_loss_hit_rate": None if sells.empty else float((sells["reason"] == "stop_loss").mean()),
        "average_holding_days": None if sells.empty else float(sells["holding_days"].astype(float).mean()),
        "objective": total_return,
        "open_position_count": len(open_positions),
        "status": "ok",
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
