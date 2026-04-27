"""Share-based brokerage ledger.

Models exactly what a Korean retail brokerage app shows:

* KRW cash balance (float, but conceptually a hangang of 100-won lots).
* Per-symbol integer-share holdings with **moving-average cost basis**
  (가중평균법 — the standard Korean retail accounting method).
* Buy/sell fills round qty down to whole shares, apply commission +
  slippage, and (on sell) the KOSPI/KOSDAQ securities tax.
* Realised PnL is accrued on every sell; unrealised PnL is whatever the
  current mark-to-market on holdings produces.

The ledger is a stateful object; immutable record types (:class:`Trade`,
:class:`EquityPoint`) live in :mod:`.contracts`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date

from .contracts import BrokerageFees, Trade, TradeReason


@dataclass
class Lot:
    """Per-symbol holding state (moving-average cost basis)."""

    qty: int = 0
    avg_cost_krw: float = 0.0  # weighted average per share
    total_cost_krw: float = 0.0  # cumulative cost (incl. fees) of currently-held qty
    first_buy_date: date | None = None
    last_buy_date: date | None = None
    buy_count: int = 0  # how many separate buy fills landed (used for "averaged down")
    realized_pnl_krw: float = 0.0  # locked-in PnL from prior sells of THIS symbol

    @property
    def is_open(self) -> bool:
        return self.qty > 0


@dataclass
class Account:
    """A single persona's share-based account."""

    persona: str
    fees: BrokerageFees
    cash_krw: float = 0.0
    contributed_krw: float = 0.0
    realized_pnl_krw: float = 0.0
    holdings: dict[str, Lot] = field(default_factory=dict)
    trades: list[Trade] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Cash deposits.
    # ------------------------------------------------------------------

    def deposit(self, when: date, amount_krw: float) -> None:
        if amount_krw < 0:
            raise ValueError(f"deposit amount must be ≥ 0; got {amount_krw}")
        self.cash_krw += amount_krw
        self.contributed_krw += amount_krw

    # ------------------------------------------------------------------
    # Helpers for fill mechanics.
    # ------------------------------------------------------------------

    def _fill_price(self, mid_price_krw: float, side: str) -> float:
        """Apply slippage in the adverse direction."""
        slip = self.fees.slippage_bps / 10_000.0
        if side == "buy":
            return mid_price_krw * (1.0 + slip)
        return mid_price_krw * (1.0 - slip)

    def _commission(self, gross_krw: float) -> float:
        return gross_krw * (self.fees.commission_bps / 10_000.0)

    def _sell_tax(self, gross_krw: float) -> float:
        return gross_krw * (self.fees.sell_tax_bps / 10_000.0)

    def _holding(self, symbol: str) -> Lot:
        return self.holdings.setdefault(symbol, Lot())

    # ------------------------------------------------------------------
    # Buy / sell primitives.
    # ------------------------------------------------------------------

    def buy_value(
        self,
        when: date,
        symbol: str,
        mid_price_krw: float,
        target_value_krw: float,
        reason: TradeReason,
        report_id: str | None = None,
    ) -> int:
        """Buy as many whole shares as ``target_value_krw`` and ``cash_krw``
        can afford. Returns the qty filled (0 if nothing executed)."""
        if mid_price_krw <= 0 or target_value_krw <= 0 or self.cash_krw <= 0:
            return 0
        budget = min(target_value_krw, self.cash_krw)
        fill_price = self._fill_price(mid_price_krw, "buy")
        # Reserve budget for commission so we don't go negative.
        commission_factor = 1.0 + self.fees.commission_bps / 10_000.0
        affordable_qty = math.floor(budget / (fill_price * commission_factor))
        if affordable_qty <= 0:
            return 0
        gross = affordable_qty * fill_price
        commission = self._commission(gross)
        cost_total = gross + commission
        if cost_total > self.cash_krw + 1e-6:
            # Numerical safety — drop one share if we just barely overshot.
            affordable_qty -= 1
            if affordable_qty <= 0:
                return 0
            gross = affordable_qty * fill_price
            commission = self._commission(gross)
            cost_total = gross + commission
        self.cash_krw -= cost_total
        lot = self._holding(symbol)
        prior_qty = lot.qty
        lot.qty = prior_qty + affordable_qty
        lot.total_cost_krw += cost_total
        lot.avg_cost_krw = lot.total_cost_krw / lot.qty if lot.qty else 0.0
        lot.last_buy_date = when
        lot.buy_count += 1
        if lot.first_buy_date is None:
            lot.first_buy_date = when
        self.trades.append(
            Trade(
                persona=self.persona,
                date=when,
                symbol=symbol,
                side="buy",
                qty=affordable_qty,
                fill_price_krw=fill_price,
                gross_krw=gross,
                commission_krw=commission,
                tax_krw=0.0,
                cash_after_krw=self.cash_krw,
                reason=reason,
                report_id=report_id,
            )
        )
        return affordable_qty

    def sell_qty(
        self,
        when: date,
        symbol: str,
        mid_price_krw: float,
        qty: int,
        reason: TradeReason,
        report_id: str | None = None,
    ) -> int:
        """Sell ``qty`` (capped to held) shares of ``symbol``."""
        lot = self.holdings.get(symbol)
        if lot is None or lot.qty <= 0 or qty <= 0 or mid_price_krw <= 0:
            return 0
        fill_qty = min(qty, lot.qty)
        fill_price = self._fill_price(mid_price_krw, "sell")
        gross = fill_qty * fill_price
        commission = self._commission(gross)
        tax = self._sell_tax(gross)
        proceeds = gross - commission - tax
        # Cost basis of the sold slice (proportional to qty).
        cost_basis_sold = lot.avg_cost_krw * fill_qty
        realized = proceeds - cost_basis_sold
        self.cash_krw += proceeds
        self.realized_pnl_krw += realized
        lot.realized_pnl_krw += realized
        lot.qty -= fill_qty
        lot.total_cost_krw = max(0.0, lot.total_cost_krw - cost_basis_sold)
        if lot.qty == 0:
            lot.avg_cost_krw = 0.0
            lot.total_cost_krw = 0.0
            lot.first_buy_date = None
            lot.buy_count = 0
        self.trades.append(
            Trade(
                persona=self.persona,
                date=when,
                symbol=symbol,
                side="sell",
                qty=fill_qty,
                fill_price_krw=fill_price,
                gross_krw=gross,
                commission_krw=commission,
                tax_krw=tax,
                cash_after_krw=self.cash_krw,
                reason=reason,
                report_id=report_id,
            )
        )
        return fill_qty

    def sell_all(
        self,
        when: date,
        symbol: str,
        mid_price_krw: float,
        reason: TradeReason,
        report_id: str | None = None,
    ) -> int:
        lot = self.holdings.get(symbol)
        if lot is None:
            return 0
        return self.sell_qty(when, symbol, mid_price_krw, lot.qty, reason, report_id)

    # ------------------------------------------------------------------
    # Composite operations.
    # ------------------------------------------------------------------

    def rebalance_to_weights(
        self,
        when: date,
        weights: dict[str, float],
        prices: dict[str, float],
        reason_buy: TradeReason = "rebalance_buy",
        reason_sell: TradeReason = "rebalance_sell",
    ) -> None:
        """Trade the holdings to match ``weights`` (sum ≤ 1).

        Strategy:

        1. Mark the entire book to market today.
        2. Compute target value per symbol = ``equity × weight``.
        3. Sell symbols whose holding > target first (frees cash, avoids
           over-spending downstream).
        4. Then buy symbols whose holding < target up to available cash.
        Symbols absent from ``weights`` are sold to zero.
        """
        equity = self.equity(prices)
        targets: dict[str, float] = {sym: equity * w for sym, w in weights.items()}
        live_symbols = set(self.holdings) | set(weights)
        # Phase 1: sell-side deltas.
        for symbol in sorted(live_symbols):
            lot = self.holdings.get(symbol)
            if lot is None or lot.qty == 0:
                continue
            mid = prices.get(symbol)
            if mid is None or mid <= 0:
                continue
            target_value = targets.get(symbol, 0.0)
            current_value = lot.qty * mid
            if current_value <= target_value:
                continue
            # We need to reduce holdings to ~target_value.
            excess_value = current_value - target_value
            sell_qty = math.floor(excess_value / mid)
            if sell_qty <= 0:
                continue
            self.sell_qty(when, symbol, mid, sell_qty, reason_sell)
        # Phase 2: buy-side deltas.
        for symbol in sorted(weights):
            mid = prices.get(symbol)
            if mid is None or mid <= 0:
                continue
            current_value = self.holdings.get(symbol, Lot()).qty * mid
            target_value = targets.get(symbol, 0.0)
            if current_value >= target_value:
                continue
            self.buy_value(when, symbol, mid, target_value - current_value, reason_buy)

    # ------------------------------------------------------------------
    # Mark-to-market.
    # ------------------------------------------------------------------

    def equity(self, prices: dict[str, float]) -> float:
        """Cash + Σ qty × close. Symbols missing from ``prices`` mark at avg cost
        (so a temporarily-stale price doesn't pretend the position vanished)."""
        value = self.cash_krw
        for symbol, lot in self.holdings.items():
            if lot.qty == 0:
                continue
            mid = prices.get(symbol)
            if mid is None or mid <= 0 or not math.isfinite(mid):
                value += lot.qty * lot.avg_cost_krw
            else:
                value += lot.qty * mid
        return value

    def holdings_value(self, prices: dict[str, float]) -> float:
        return self.equity(prices) - self.cash_krw

    def open_position_count(self) -> int:
        return sum(1 for lot in self.holdings.values() if lot.qty > 0)
