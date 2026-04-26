"""Per-persona holdings reports derived from the trade ledger.

Four views, all reconstructed from :class:`Trade` records (not from
intermediate engine state — so they round-trip through ``trades.csv``):

* :func:`compute_position_episodes` — every contiguous holding period
  (qty 0 → >0 → ... → 0) for each (persona, symbol). Captures
  open/close dates, holding days, partial-fill counts, weighted-average
  entry/exit prices, and realised PnL for that one episode.
* :func:`compute_current_holdings` — the still-open positions on the
  last simulation day, marked-to-market against the price board.
* :func:`compute_symbol_stats` — episode aggregates per (persona,
  symbol): total holding days, total realised PnL, current open status.
* :func:`compute_monthly_holdings` — month-end snapshot of each
  persona's book (qty + market value + weight per symbol). Drives the
  portfolio-evolution stacked-area chart in the README.

The arithmetic is the same moving-average cost basis used by the
:class:`Account` ledger. By recomputing here we guarantee the saved
``trades.csv`` is the system's single source of truth — anything that
looks at the ledger gets the same numbers.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date

import pandas as pd

from .contracts import CurrentHolding, PositionEpisode, SymbolStat, Trade
from .market import PriceBoard


@dataclass
class _RunningPosition:
    open_date: date | None = None
    qty: int = 0
    total_cost_krw: float = 0.0  # carries fees on the buy side
    buy_fills: int = 0
    sell_fills: int = 0
    qty_bought: int = 0
    qty_sold: int = 0
    proceeds_krw: float = 0.0  # net of commission + tax on the sell side
    realized_pnl_krw: float = 0.0
    last_sell_date: date | None = None
    exit_reasons: list[str] = field(default_factory=list)
    first_buy_date: date | None = None


def compute_position_episodes(
    trades: Iterable[Trade],
    board: PriceBoard | None,
    end_date: date,
    company_by_symbol: Mapping[str, str] | None = None,
) -> list[PositionEpisode]:
    """Reconstruct round-trip episodes per (persona, symbol).

    Parameters
    ----------
    trades : iterable of Trade
        Full ledger. Order does not matter; we sort per group.
    board : PriceBoard | None
        Used for marking still-open episodes to market on ``end_date``.
        Pass ``None`` to skip MTM (open episodes will then carry
        ``unrealized_pnl_krw=None``).
    end_date : date
        Anchor for "still open" mark-to-market and holding-days math.
    company_by_symbol : mapping or None
        Optional symbol → human-readable name lookup (typically derived
        from ``reports.csv``).
    """
    company_lookup = dict(company_by_symbol or {})
    grouped: dict[tuple[str, str], list[Trade]] = defaultdict(list)
    for t in trades:
        grouped[(t.persona, t.symbol)].append(t)

    episodes: list[PositionEpisode] = []
    for (persona, symbol), group in grouped.items():
        group.sort(key=lambda x: (x.date, x.side))  # buys before sells when same day
        state = _RunningPosition()
        for t in group:
            if t.side == "buy":
                if state.qty == 0:
                    # New episode opens here.
                    state.open_date = t.date
                    if state.first_buy_date is None:
                        state.first_buy_date = t.date
                cost = t.gross_krw + t.commission_krw
                state.qty += t.qty
                state.total_cost_krw += cost
                state.buy_fills += 1
                state.qty_bought += t.qty
            elif t.side == "sell":
                if state.qty <= 0:
                    # Defensive: a sell with no inventory is illegal but we
                    # don't want to silently lose a row. Skip it.
                    continue
                avg_cost_per_share = state.total_cost_krw / state.qty
                sold_qty = min(t.qty, state.qty)
                cost_of_sold = avg_cost_per_share * sold_qty
                proceeds = t.gross_krw - t.commission_krw - t.tax_krw
                state.qty -= sold_qty
                state.total_cost_krw = max(0.0, state.total_cost_krw - cost_of_sold)
                state.sell_fills += 1
                state.qty_sold += sold_qty
                state.proceeds_krw += proceeds
                state.realized_pnl_krw += proceeds - cost_of_sold
                state.last_sell_date = t.date
                if t.reason and t.reason not in state.exit_reasons:
                    state.exit_reasons.append(t.reason)
                if state.qty == 0:
                    episodes.append(_finalize_episode(persona, symbol, state, company_lookup, closed=True))
                    # Reset for a possible later re-entry.
                    state = _RunningPosition()
        if state.qty > 0:
            # Open episode at end of sim — mark to market.
            mid = board.asof(end_date, symbol) if board is not None else None
            avg_cost = state.total_cost_krw / state.qty if state.qty else 0.0
            unreal = (mid - avg_cost) * state.qty if (mid is not None and avg_cost > 0) else None
            episodes.append(
                _finalize_episode(
                    persona,
                    symbol,
                    state,
                    company_lookup,
                    closed=False,
                    end_date=end_date,
                    last_close=mid,
                    unrealized=unreal,
                )
            )
    episodes.sort(key=lambda e: (e.persona, e.open_date, e.symbol))
    return episodes


def _finalize_episode(
    persona: str,
    symbol: str,
    state: _RunningPosition,
    company_lookup: Mapping[str, str],
    *,
    closed: bool,
    end_date: date | None = None,
    last_close: float | None = None,
    unrealized: float | None = None,
) -> PositionEpisode:
    open_date = state.open_date or state.first_buy_date or end_date or date.today()
    if closed:
        close_date = state.last_sell_date
        holding_days = (close_date - open_date).days if close_date else 0
        # At close, qty == 0 so all bought has been sold. The episode's total
        # buy-side cost basis = proceeds − realized_pnl (since
        # realized_pnl = proceeds − cost_of_sold_total when fully unwound).
        cost_basis_total = state.proceeds_krw - state.realized_pnl_krw
        avg_entry = cost_basis_total / state.qty_sold if state.qty_sold else 0.0
        avg_exit = state.proceeds_krw / state.qty_sold if state.qty_sold else None
        status = "closed"
    else:
        close_date = None
        anchor = end_date or date.today()
        holding_days = (anchor - open_date).days
        avg_entry = state.total_cost_krw / state.qty if state.qty else 0.0
        avg_exit = None
        status = "open"
    return PositionEpisode(
        persona=persona,
        symbol=symbol,
        company=company_lookup.get(symbol),
        open_date=open_date,
        close_date=close_date,
        holding_days=holding_days,
        buy_fills=state.buy_fills,
        sell_fills=state.sell_fills,
        total_qty_bought=state.qty_bought,
        total_qty_sold=state.qty_sold,
        avg_entry_price_krw=avg_entry,
        avg_exit_price_krw=avg_exit,
        realized_pnl_krw=state.realized_pnl_krw,
        unrealized_pnl_krw=unrealized,
        last_close_krw=last_close,
        status=status,
        exit_reasons=tuple(state.exit_reasons),
    )


def compute_current_holdings(
    episodes: Iterable[PositionEpisode],
    board: PriceBoard | None,
    end_date: date,
) -> list[CurrentHolding]:
    """Filter ``episodes`` to those still open on ``end_date`` and MTM."""
    holdings: list[CurrentHolding] = []
    for ep in episodes:
        if ep.status != "open":
            continue
        qty = ep.total_qty_bought - ep.total_qty_sold
        if qty <= 0:
            continue
        avg_cost = ep.avg_entry_price_krw
        last_close = ep.last_close_krw
        if last_close is None and board is not None:
            last_close = board.asof(end_date, ep.symbol)
        market_value = qty * (last_close if last_close is not None else avg_cost)
        unrealized = market_value - qty * avg_cost
        unreal_ret = (last_close / avg_cost - 1.0) if (last_close and avg_cost > 0) else None
        holdings.append(
            CurrentHolding(
                persona=ep.persona,
                symbol=ep.symbol,
                company=ep.company,
                qty=qty,
                avg_cost_krw=avg_cost,
                last_close_krw=last_close,
                market_value_krw=market_value,
                unrealized_pnl_krw=unrealized,
                unrealized_return=unreal_ret,
                holding_days=ep.holding_days,
                first_buy_date=ep.open_date,
            )
        )
    holdings.sort(key=lambda h: (h.persona, -h.market_value_krw))
    return holdings


def compute_monthly_holdings(
    trades: Iterable[Trade],
    boards_by_persona: Mapping[str, PriceBoard],
    end_date: date,
    company_by_symbol: Mapping[str, str] | None = None,
) -> pd.DataFrame:
    """Month-end snapshot of every still-open position per persona.

    Walks the trade ledger chronologically per persona, keeping a running
    integer-share book. At every calendar month-end inside the simulation
    window it freezes the book against the persona's price board, then
    emits one row per ``(persona, month_end, symbol)`` with positive qty.

    Output columns: ``persona``, ``month_end``, ``symbol``, ``company``,
    ``qty``, ``market_value_krw``, ``weight_in_portfolio`` (share of the
    invested book on that date, ignoring cash). Sorted ascending by
    persona then month_end then descending market value.

    ``boards_by_persona`` is a dict like ``{"oracle": board, "all_weather":
    benchmark_board}``. Personas not in the dict fall back to whatever
    is keyed under ``"_default"`` (or no MTM if neither exists).
    """
    grouped: dict[str, list[Trade]] = defaultdict(list)
    for t in trades:
        grouped[t.persona].append(t)
    if not grouped:
        return pd.DataFrame()

    company_lookup = dict(company_by_symbol or {})
    rows: list[dict] = []
    default_board = boards_by_persona.get("_default")

    for persona, persona_trades in grouped.items():
        persona_trades.sort(key=lambda t: (t.date, t.side))
        board = boards_by_persona.get(persona, default_board)
        if board is None:
            continue
        first_date = persona_trades[0].date
        month_ends = _month_ends_between(first_date, end_date)
        if not month_ends:
            continue
        positions: dict[str, dict[str, float]] = {}
        cursor = 0
        for month_end in month_ends:
            while cursor < len(persona_trades) and persona_trades[cursor].date <= month_end:
                t = persona_trades[cursor]
                cursor += 1
                pos = positions.setdefault(t.symbol, {"qty": 0, "cost": 0.0})
                if t.side == "buy":
                    pos["qty"] += t.qty
                    pos["cost"] += t.gross_krw + t.commission_krw
                else:
                    if pos["qty"] <= 0:
                        continue
                    avg_cost = pos["cost"] / pos["qty"] if pos["qty"] else 0.0
                    sold = min(t.qty, pos["qty"])
                    pos["qty"] -= sold
                    pos["cost"] = max(0.0, pos["cost"] - avg_cost * sold)
                    if pos["qty"] == 0:
                        pos["cost"] = 0.0
            snapshot = []
            total_value = 0.0
            for symbol, pos in positions.items():
                if pos["qty"] <= 0:
                    continue
                mid = board.asof(month_end, symbol)
                if mid is None:
                    mid = (pos["cost"] / pos["qty"]) if pos["qty"] else 0.0
                value = pos["qty"] * mid
                snapshot.append((symbol, int(pos["qty"]), value))
                total_value += value
            for symbol, qty, value in snapshot:
                rows.append(
                    {
                        "persona": persona,
                        "month_end": month_end,
                        "symbol": symbol,
                        "company": company_lookup.get(symbol, ""),
                        "qty": qty,
                        "market_value_krw": value,
                        "weight_in_portfolio": (value / total_value) if total_value > 0 else 0.0,
                    }
                )
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df = df.sort_values(["persona", "month_end", "market_value_krw"], ascending=[True, True, False])
    return df.reset_index(drop=True)


def _month_ends_between(start: date, end: date) -> list[date]:
    """All calendar month-ends in ``[start, end]``, plus the final ``end`` itself."""
    if end < start:
        return []
    cursor = pd.Timestamp(start).to_period("M").to_timestamp("M").date()
    ends: list[date] = []
    final = end
    while cursor <= final:
        ends.append(cursor)
        next_month = (pd.Timestamp(cursor) + pd.Timedelta(days=1)).to_period("M").to_timestamp("M").date()
        if next_month <= cursor:
            break
        cursor = next_month
    if not ends or ends[-1] != final:
        ends.append(final)
    return ends


def compute_symbol_stats(episodes: Iterable[PositionEpisode]) -> list[SymbolStat]:
    """One row per (persona, symbol) summarising every episode for that pair."""
    grouped: dict[tuple[str, str], list[PositionEpisode]] = defaultdict(list)
    for ep in episodes:
        grouped[(ep.persona, ep.symbol)].append(ep)
    stats: list[SymbolStat] = []
    for (persona, symbol), eps in grouped.items():
        company = next((e.company for e in eps if e.company), None)
        open_eps = [e for e in eps if e.status == "open"]
        is_open = bool(open_eps)
        current_qty = sum(e.total_qty_bought - e.total_qty_sold for e in open_eps)
        current_unreal = sum(e.unrealized_pnl_krw or 0.0 for e in open_eps) if is_open else None
        stats.append(
            SymbolStat(
                persona=persona,
                symbol=symbol,
                company=company,
                episodes=len(eps),
                total_buy_fills=sum(e.buy_fills for e in eps),
                total_sell_fills=sum(e.sell_fills for e in eps),
                total_holding_days=sum(e.holding_days for e in eps),
                total_realized_pnl_krw=sum(e.realized_pnl_krw for e in eps),
                is_currently_held=is_open,
                current_qty=current_qty,
                current_unrealized_pnl_krw=current_unreal,
            )
        )
    stats.sort(key=lambda s: (s.persona, -s.total_realized_pnl_krw))
    return stats
