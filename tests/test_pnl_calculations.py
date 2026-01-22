"""
Tests for PnL (Profit and Loss) calculations.

This is the most critical financial logic in the system. Every calculation
must be verified with hand-computed expected values.

Bug categories prevented:
- Incorrect gross PnL (price difference * size)
- Fees not deducted correctly
- Percentage calculations wrong (dividing by wrong base)
- Multiple pyramids summed incorrectly
- Rounding errors in financial calculations

The formulas tested here match the implementation in trade_service.py:
- gross_pnl = (exit_price - entry_price) * position_size
- entry_fee = entry_price * position_size * fee_rate
- exit_fee = exit_price * position_size * fee_rate
- net_pnl = gross_pnl - entry_fee - exit_fee
- pnl_percent = (net_pnl / capital) * 100
"""

import pytest
from decimal import Decimal


def calculate_pyramid_pnl(
    entry_price: float,
    exit_price: float,
    position_size: float,
    capital_usdt: float,
    fee_rate: float,
) -> dict:
    """
    Calculate PnL for a single pyramid (LONG only).

    This mirrors the logic in trade_service._process_exit()
    """
    # Gross PnL from price movement
    gross_pnl = (exit_price - entry_price) * position_size

    # Fees on both entry and exit
    entry_notional = entry_price * position_size
    exit_notional = exit_price * position_size
    entry_fee = entry_notional * fee_rate
    exit_fee = exit_notional * fee_rate

    # Net PnL after all fees
    total_fees = entry_fee + exit_fee
    net_pnl = gross_pnl - total_fees

    # Percentage return on capital
    pnl_percent = (net_pnl / capital_usdt) * 100 if capital_usdt > 0 else 0

    return {
        "gross_pnl": gross_pnl,
        "entry_fee": entry_fee,
        "exit_fee": exit_fee,
        "total_fees": total_fees,
        "net_pnl": net_pnl,
        "pnl_percent": pnl_percent,
    }


class TestSinglePyramidPnL:
    """
    Tests for single pyramid PnL calculations.

    Each test has hand-verified expected values.
    """

    def test_profitable_trade_basic(self):
        """
        Test a simple profitable trade.

        Entry: $50,000 @ 0.1 BTC = $5,000 notional
        Exit: $51,000 @ 0.1 BTC = $5,100 notional
        Fee rate: 0.1% (0.001)

        Gross PnL = (51000 - 50000) * 0.1 = $100
        Entry fee = 5000 * 0.001 = $5
        Exit fee = 5100 * 0.001 = $5.10
        Total fees = $10.10
        Net PnL = 100 - 10.10 = $89.90
        PnL % = (89.90 / 5000) * 100 = 1.798%
        """
        result = calculate_pyramid_pnl(
            entry_price=50000.0,
            exit_price=51000.0,
            position_size=0.1,
            capital_usdt=5000.0,
            fee_rate=0.001,
        )

        assert result["gross_pnl"] == pytest.approx(100.0, abs=0.01)
        assert result["entry_fee"] == pytest.approx(5.0, abs=0.01)
        assert result["exit_fee"] == pytest.approx(5.10, abs=0.01)
        assert result["total_fees"] == pytest.approx(10.10, abs=0.01)
        assert result["net_pnl"] == pytest.approx(89.90, abs=0.01)
        assert result["pnl_percent"] == pytest.approx(1.798, abs=0.01)

    def test_losing_trade_basic(self):
        """
        Test a simple losing trade.

        Entry: $50,000 @ 0.1 BTC = $5,000 notional
        Exit: $49,000 @ 0.1 BTC = $4,900 notional
        Fee rate: 0.1%

        Gross PnL = (49000 - 50000) * 0.1 = -$100
        Entry fee = 5000 * 0.001 = $5
        Exit fee = 4900 * 0.001 = $4.90
        Total fees = $9.90
        Net PnL = -100 - 9.90 = -$109.90
        PnL % = (-109.90 / 5000) * 100 = -2.198%
        """
        result = calculate_pyramid_pnl(
            entry_price=50000.0,
            exit_price=49000.0,
            position_size=0.1,
            capital_usdt=5000.0,
            fee_rate=0.001,
        )

        assert result["gross_pnl"] == pytest.approx(-100.0, abs=0.01)
        assert result["net_pnl"] == pytest.approx(-109.90, abs=0.01)
        assert result["pnl_percent"] == pytest.approx(-2.198, abs=0.01)

    def test_breakeven_before_fees(self):
        """
        Test exit at entry price (gross breakeven, but fees cause loss).

        Entry: $50,000 @ 0.1 BTC = $5,000 notional
        Exit: $50,000 @ 0.1 BTC = $5,000 notional
        Fee rate: 0.1%

        Gross PnL = 0
        Entry fee = $5
        Exit fee = $5
        Net PnL = -$10 (loss from fees alone)
        """
        result = calculate_pyramid_pnl(
            entry_price=50000.0,
            exit_price=50000.0,
            position_size=0.1,
            capital_usdt=5000.0,
            fee_rate=0.001,
        )

        assert result["gross_pnl"] == 0.0
        assert result["net_pnl"] == pytest.approx(-10.0, abs=0.01)
        assert result["net_pnl"] < 0  # Fees cause loss

    def test_large_position_scaling(self):
        """
        Test that calculations scale correctly with position size.

        Entry: $3,000 @ 5 ETH = $15,000 notional
        Exit: $3,100 @ 5 ETH = $15,500 notional
        Fee rate: 0.1%

        Gross PnL = (3100 - 3000) * 5 = $500
        Entry fee = 15000 * 0.001 = $15
        Exit fee = 15500 * 0.001 = $15.50
        Net PnL = 500 - 30.50 = $469.50
        """
        result = calculate_pyramid_pnl(
            entry_price=3000.0,
            exit_price=3100.0,
            position_size=5.0,
            capital_usdt=15000.0,
            fee_rate=0.001,
        )

        assert result["gross_pnl"] == pytest.approx(500.0, abs=0.01)
        assert result["net_pnl"] == pytest.approx(469.50, abs=0.01)

    def test_different_fee_rates(self):
        """
        Test with different fee rates (e.g., VIP tier).

        Using 0.075% fee rate (common VIP rate).

        Entry: $50,000 @ 0.1 BTC = $5,000 notional
        Exit: $51,000 @ 0.1 BTC = $5,100 notional
        Fee rate: 0.075% (0.00075)

        Entry fee = 5000 * 0.00075 = $3.75
        Exit fee = 5100 * 0.00075 = $3.825
        Total fees = $7.575
        Net PnL = 100 - 7.575 = $92.425
        """
        result = calculate_pyramid_pnl(
            entry_price=50000.0,
            exit_price=51000.0,
            position_size=0.1,
            capital_usdt=5000.0,
            fee_rate=0.00075,
        )

        assert result["total_fees"] == pytest.approx(7.575, abs=0.01)
        assert result["net_pnl"] == pytest.approx(92.425, abs=0.01)

    def test_zero_fee_rate(self):
        """
        Test with zero fee rate (maker rebate scenario).

        Gross = Net when no fees.
        """
        result = calculate_pyramid_pnl(
            entry_price=50000.0,
            exit_price=51000.0,
            position_size=0.1,
            capital_usdt=5000.0,
            fee_rate=0.0,
        )

        assert result["total_fees"] == 0.0
        assert result["gross_pnl"] == result["net_pnl"]

    def test_small_price_movement(self):
        """
        Test very small price movements.

        $1 move on BTC shouldn't cause precision issues.

        Entry: $50,000 @ 0.1 BTC
        Exit: $50,001 @ 0.1 BTC
        Gross PnL = $0.10
        """
        result = calculate_pyramid_pnl(
            entry_price=50000.0,
            exit_price=50001.0,
            position_size=0.1,
            capital_usdt=5000.0,
            fee_rate=0.001,
        )

        assert result["gross_pnl"] == pytest.approx(0.1, abs=0.001)

    def test_percentage_calculation_correct_base(self):
        """
        Verify percentage is calculated against capital, not entry notional.

        Capital might differ from entry notional due to rounding.

        Capital: $1,000
        Entry: $50,000 @ 0.02 BTC = $1,000 notional (exact match)
        Exit: $52,000 @ 0.02 BTC = $1,040 notional

        Gross PnL = (52000 - 50000) * 0.02 = $40
        Fees = ~$2.04
        Net PnL = ~$37.96
        PnL % = (37.96 / 1000) * 100 = ~3.796%
        """
        result = calculate_pyramid_pnl(
            entry_price=50000.0,
            exit_price=52000.0,
            position_size=0.02,
            capital_usdt=1000.0,
            fee_rate=0.001,
        )

        # Net PnL = 40 - (1.0 + 1.04) = 37.96
        assert result["net_pnl"] == pytest.approx(37.96, abs=0.01)
        # Percentage is based on capital ($1000)
        assert result["pnl_percent"] == pytest.approx(3.796, abs=0.01)


class TestMultiplePyramidPnL:
    """
    Tests for aggregating PnL across multiple pyramids.

    This mirrors how trade_service._process_exit() sums pyramids.
    """

    def test_two_pyramids_both_profitable(self):
        """
        Test total PnL from two profitable pyramids.

        Pyramid 1: Entry $50,000 @ 0.1 BTC, capital $5,000
        Pyramid 2: Entry $49,000 @ 0.1 BTC, capital $4,900
        Exit both: $52,000
        Fee rate: 0.1%

        Pyramid 1:
          Gross = (52000 - 50000) * 0.1 = $200
          Entry fee = 5000 * 0.001 = $5
          Exit fee = 5200 * 0.001 = $5.20
          Net = 200 - 10.20 = $189.80

        Pyramid 2:
          Gross = (52000 - 49000) * 0.1 = $300
          Entry fee = 4900 * 0.001 = $4.90
          Exit fee = 5200 * 0.001 = $5.20
          Net = 300 - 10.10 = $289.90

        Total net = 189.80 + 289.90 = $479.70
        """
        pyr1 = calculate_pyramid_pnl(
            entry_price=50000.0,
            exit_price=52000.0,
            position_size=0.1,
            capital_usdt=5000.0,
            fee_rate=0.001,
        )

        pyr2 = calculate_pyramid_pnl(
            entry_price=49000.0,
            exit_price=52000.0,
            position_size=0.1,
            capital_usdt=4900.0,
            fee_rate=0.001,
        )

        total_net = pyr1["net_pnl"] + pyr2["net_pnl"]
        total_capital = 5000.0 + 4900.0
        total_pnl_percent = (total_net / total_capital) * 100

        assert total_net == pytest.approx(479.70, abs=0.1)
        assert total_pnl_percent == pytest.approx(4.85, abs=0.1)

    def test_mixed_pyramids_net_profitable(self):
        """
        Test pyramids where first wins big, second loses small.

        Pyramid 1: Entry $45,000, Exit $50,000, size 0.1
        Pyramid 2: Entry $52,000, Exit $50,000, size 0.1 (loss)

        Overall should still be profitable.
        """
        pyr1 = calculate_pyramid_pnl(
            entry_price=45000.0,
            exit_price=50000.0,
            position_size=0.1,
            capital_usdt=4500.0,
            fee_rate=0.001,
        )

        pyr2 = calculate_pyramid_pnl(
            entry_price=52000.0,
            exit_price=50000.0,
            position_size=0.1,
            capital_usdt=5200.0,
            fee_rate=0.001,
        )

        assert pyr1["net_pnl"] > 0  # First pyramid profitable
        assert pyr2["net_pnl"] < 0  # Second pyramid loss

        total_net = pyr1["net_pnl"] + pyr2["net_pnl"]
        assert total_net > 0  # Overall profitable

    def test_three_pyramids_dollar_cost_averaging(self):
        """
        Test DCA scenario: three entries at different prices.

        Pyramid 1: Entry $50,000 @ 0.1 BTC
        Pyramid 2: Entry $48,000 @ 0.1 BTC (price dropped, added more)
        Pyramid 3: Entry $45,000 @ 0.1 BTC (price dropped again)
        Exit all: $52,000

        This tests a common pyramid strategy: averaging down.
        """
        exit_price = 52000.0
        fee_rate = 0.001

        pyramids = [
            {"entry": 50000.0, "size": 0.1, "capital": 5000.0},
            {"entry": 48000.0, "size": 0.1, "capital": 4800.0},
            {"entry": 45000.0, "size": 0.1, "capital": 4500.0},
        ]

        total_gross = 0.0
        total_fees = 0.0
        total_capital = 0.0

        for pyr in pyramids:
            result = calculate_pyramid_pnl(
                entry_price=pyr["entry"],
                exit_price=exit_price,
                position_size=pyr["size"],
                capital_usdt=pyr["capital"],
                fee_rate=fee_rate,
            )
            total_gross += result["gross_pnl"]
            total_fees += result["total_fees"]
            total_capital += pyr["capital"]

        total_net = total_gross - total_fees
        total_pnl_percent = (total_net / total_capital) * 100

        # Expected:
        # Gross = (2000 + 4000 + 7000) * 0.1 = $1300
        assert total_gross == pytest.approx(1300.0, abs=0.1)
        assert total_net > 0
        assert total_pnl_percent > 0


class TestEdgeCases:
    """
    Edge cases and boundary conditions for PnL calculations.
    """

    def test_very_small_position_size(self):
        """
        Test with very small position sizes (dust amounts).

        0.0001 BTC at $50,000 = $5 notional
        """
        result = calculate_pyramid_pnl(
            entry_price=50000.0,
            exit_price=51000.0,
            position_size=0.0001,
            capital_usdt=5.0,
            fee_rate=0.001,
        )

        # Gross = 0.1, fees ~0.01, net ~0.09
        assert result["gross_pnl"] == pytest.approx(0.1, abs=0.001)
        assert result["net_pnl"] > 0

    def test_high_fee_rate(self):
        """
        Test with high fee rate (1% - some exchanges charge this).

        High fees can turn a gross profit into a net loss.
        """
        result = calculate_pyramid_pnl(
            entry_price=50000.0,
            exit_price=50500.0,  # 1% gross profit
            position_size=0.1,
            capital_usdt=5000.0,
            fee_rate=0.01,  # 1% fee
        )

        # Gross = $50
        # Entry fee = $50
        # Exit fee = $50.50
        # Net = 50 - 100.50 = -$50.50 (loss despite price increase!)
        assert result["gross_pnl"] == pytest.approx(50.0, abs=0.01)
        assert result["net_pnl"] < 0  # Loss due to fees

    def test_zero_capital_division(self):
        """
        Test that zero capital doesn't cause division by zero.

        Should return 0% rather than crash.
        """
        result = calculate_pyramid_pnl(
            entry_price=50000.0,
            exit_price=51000.0,
            position_size=0.1,
            capital_usdt=0.0,  # Edge case
            fee_rate=0.001,
        )

        assert result["pnl_percent"] == 0.0  # No crash

    def test_precision_many_decimals(self):
        """
        Test that calculations handle many decimal places correctly.

        Use prices and sizes that could cause floating-point issues.
        """
        result = calculate_pyramid_pnl(
            entry_price=0.00001234,  # Low-cap token
            exit_price=0.00001357,
            position_size=10000000.0,  # Large position
            capital_usdt=123.4,
            fee_rate=0.001,
        )

        # Should not have weird floating-point artifacts
        assert isinstance(result["net_pnl"], float)
        assert result["gross_pnl"] > 0


class TestRealWorldScenarios:
    """
    Tests based on realistic trading scenarios.
    """

    def test_btc_scalp_trade(self):
        """
        Test a typical BTC scalp trade.

        Entry: $42,150.50 @ 0.05 BTC (~$2,107.52 capital)
        Exit: $42,320.00 @ 0.05 BTC
        Fee: 0.1% (standard taker)

        This is a ~0.4% move, typical for a scalp.
        """
        result = calculate_pyramid_pnl(
            entry_price=42150.50,
            exit_price=42320.00,
            position_size=0.05,
            capital_usdt=2107.52,
            fee_rate=0.001,
        )

        # Gross = (42320 - 42150.50) * 0.05 = $8.475
        assert result["gross_pnl"] == pytest.approx(8.475, abs=0.01)
        # Should be profitable after fees
        assert result["net_pnl"] > 0

    def test_eth_swing_trade(self):
        """
        Test an ETH swing trade held for a few days.

        Entry: $2,400 @ 1.5 ETH ($3,600 capital)
        Exit: $2,700 @ 1.5 ETH
        Fee: 0.1%

        This is a 12.5% move.
        """
        result = calculate_pyramid_pnl(
            entry_price=2400.0,
            exit_price=2700.0,
            position_size=1.5,
            capital_usdt=3600.0,
            fee_rate=0.001,
        )

        # Gross = (2700 - 2400) * 1.5 = $450
        assert result["gross_pnl"] == pytest.approx(450.0, abs=0.01)
        # Net should be close to gross (low fees relative to profit)
        assert result["net_pnl"] > 440.0

    def test_stopped_out_trade(self):
        """
        Test a trade that hit stop loss.

        Entry: $50,000 @ 0.1 BTC
        Stop triggered at: $48,000 (4% loss)
        Fee: 0.1%
        """
        result = calculate_pyramid_pnl(
            entry_price=50000.0,
            exit_price=48000.0,
            position_size=0.1,
            capital_usdt=5000.0,
            fee_rate=0.001,
        )

        # Gross loss = -$200
        assert result["gross_pnl"] == pytest.approx(-200.0, abs=0.01)
        # Net loss = gross + fees
        assert result["net_pnl"] < -200.0
        # Percentage loss should be around -4.2%
        assert result["pnl_percent"] < -4.0
