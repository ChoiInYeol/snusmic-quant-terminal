"""Share-based brokerage ledger semantics."""

from __future__ import annotations

from datetime import date

from snusmic_pipeline.sim.brokerage import Account, Lot
from snusmic_pipeline.sim.contracts import BrokerageFees


def _zero_fee_account() -> Account:
    return Account(persona="t", fees=BrokerageFees(commission_bps=0, sell_tax_bps=0, slippage_bps=0))


def test_deposit_increments_cash_and_contributed():
    acc = _zero_fee_account()
    acc.deposit(date(2024, 1, 1), 5_000_000)
    assert acc.cash_krw == 5_000_000
    assert acc.contributed_krw == 5_000_000


def test_buy_value_rounds_down_to_whole_shares():
    acc = _zero_fee_account()
    acc.deposit(date(2024, 1, 1), 1_000_000)
    qty = acc.buy_value(
        date(2024, 1, 1), "A", mid_price_krw=300_000, target_value_krw=1_000_000, reason="deposit_buy"
    )
    assert qty == 3  # 1M / 300k = 3.33 → 3 shares
    assert acc.cash_krw == 100_000  # 1_000_000 − 3 × 300_000


def test_buy_value_includes_commission_and_slippage():
    acc = Account(persona="t", fees=BrokerageFees(commission_bps=10, sell_tax_bps=0, slippage_bps=20))
    acc.deposit(date(2024, 1, 1), 1_000_000)
    # Slippage 0.2% pushes fill_price to 300_600; commission 0.1% on gross.
    qty = acc.buy_value(
        date(2024, 1, 1), "A", mid_price_krw=300_000, target_value_krw=1_000_000, reason="deposit_buy"
    )
    assert qty == 3
    expected_cost = 3 * 300_600 * 1.001
    assert abs(acc.cash_krw - (1_000_000 - expected_cost)) < 1.0


def test_buy_zero_qty_when_budget_too_small():
    acc = _zero_fee_account()
    acc.deposit(date(2024, 1, 1), 100)
    qty = acc.buy_value(date(2024, 1, 1), "A", 300_000, 100, "deposit_buy")
    assert qty == 0
    assert acc.cash_krw == 100


def test_sell_qty_realises_pnl_and_pays_tax():
    acc = Account(persona="t", fees=BrokerageFees(commission_bps=0, sell_tax_bps=20, slippage_bps=0))
    acc.deposit(date(2024, 1, 1), 1_000_000)
    acc.buy_value(date(2024, 1, 1), "A", 100_000, 1_000_000, "deposit_buy")
    assert acc.holdings["A"].qty == 10
    acc.sell_qty(date(2024, 6, 1), "A", 200_000, 10, "target_hit")
    assert acc.holdings["A"].qty == 0
    # Proceeds = 10×200k − 0.2% tax = 2,000,000 − 4,000 = 1,996,000.
    # Realised PnL = 1,996,000 − 1,000,000 cost basis = 996,000.
    assert abs(acc.realized_pnl_krw - 996_000) < 1.0


def test_buy_keeps_moving_average_cost_basis():
    acc = _zero_fee_account()
    acc.deposit(date(2024, 1, 1), 2_000_000)
    acc.buy_value(date(2024, 1, 1), "A", 100_000, 1_000_000, "deposit_buy")  # 10 @ 100k
    acc.buy_value(date(2024, 2, 1), "A", 50_000, 500_000, "deposit_buy")  # 10 @ 50k
    lot = acc.holdings["A"]
    assert lot.qty == 20
    # Avg cost = (10×100k + 10×50k) / 20 = 75k
    assert abs(lot.avg_cost_krw - 75_000) < 1.0
    assert lot.buy_count == 2


def test_rebalance_reaches_target_weights_within_one_lot():
    acc = _zero_fee_account()
    acc.deposit(date(2024, 1, 1), 10_000_000)
    prices = {"A": 100_000, "B": 50_000, "C": 200_000}
    acc.rebalance_to_weights(date(2024, 1, 1), {"A": 0.4, "B": 0.3, "C": 0.3}, prices)
    equity = acc.equity(prices)
    a_share = (acc.holdings["A"].qty * prices["A"]) / equity
    b_share = (acc.holdings["B"].qty * prices["B"]) / equity
    c_share = (acc.holdings["C"].qty * prices["C"]) / equity
    assert abs(a_share - 0.4) < 0.01
    assert abs(b_share - 0.3) < 0.01
    assert abs(c_share - 0.3) < 0.01


def test_equity_marks_missing_prices_at_avg_cost():
    acc = _zero_fee_account()
    acc.deposit(date(2024, 1, 1), 1_000_000)
    acc.buy_value(date(2024, 1, 1), "A", 100_000, 1_000_000, "deposit_buy")
    # Symbol A has no price today → use avg cost
    eq = acc.equity({})
    assert abs(eq - 1_000_000) < 1.0


def test_open_position_count_excludes_closed_lots():
    acc = _zero_fee_account()
    acc.deposit(date(2024, 1, 1), 1_000_000)
    acc.buy_value(date(2024, 1, 1), "A", 100_000, 1_000_000, "deposit_buy")
    acc.sell_all(date(2024, 6, 1), "A", 200_000, "target_hit")
    assert acc.open_position_count() == 0
    assert isinstance(acc.holdings["A"], Lot)
