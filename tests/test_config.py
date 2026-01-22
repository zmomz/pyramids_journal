"""
Tests for configuration and fee calculations.

Bug categories prevented:
- Wrong fee percentages applied to trades
- Unknown exchange returning wrong default fee
- Percentage conversion errors (0.1% stored as 0.1 vs 0.001)
"""

import pytest
import tempfile
import yaml
from pathlib import Path

from app.config import ExchangeFees, ExchangeConfig


class TestExchangeFees:
    """
    Tests for ExchangeFees class.

    Bug prevented: Fee percentages stored incorrectly (e.g., 0.1 instead of 0.001).
    """

    def test_percentage_to_decimal_conversion(self):
        """
        Verify that percentage inputs are converted to decimal.

        0.1% should be stored as 0.001 for calculation.
        """
        fees = ExchangeFees(maker_fee=0.1, taker_fee=0.1)

        assert fees.maker_fee == 0.001
        assert fees.taker_fee == 0.001

    @pytest.mark.parametrize(
        "maker_pct,taker_pct,expected_maker,expected_taker",
        [
            (0.1, 0.1, 0.001, 0.001),  # Standard 0.1%
            (0.075, 0.1, 0.00075, 0.001),  # VIP maker, regular taker
            (0.02, 0.04, 0.0002, 0.0004),  # VIP tier
            (0.0, 0.1, 0.0, 0.001),  # Zero maker rebate
            (1.0, 1.0, 0.01, 0.01),  # 1% fees (rare but possible)
        ],
        ids=[
            "standard-0.1%",
            "vip-maker",
            "vip-tier",
            "zero-maker",
            "high-1%",
        ],
    )
    def test_various_fee_tiers(self, maker_pct, taker_pct, expected_maker, expected_taker):
        """Verify various fee tiers convert correctly."""
        fees = ExchangeFees(maker_fee=maker_pct, taker_fee=taker_pct)

        assert fees.maker_fee == pytest.approx(expected_maker, abs=1e-10)
        assert fees.taker_fee == pytest.approx(expected_taker, abs=1e-10)

    def test_get_fee_maker(self):
        """Verify get_fee returns maker fee for maker orders."""
        fees = ExchangeFees(maker_fee=0.05, taker_fee=0.1)

        assert fees.get_fee("maker") == pytest.approx(0.0005, abs=1e-10)

    def test_get_fee_taker(self):
        """Verify get_fee returns taker fee for taker orders."""
        fees = ExchangeFees(maker_fee=0.05, taker_fee=0.1)

        assert fees.get_fee("taker") == pytest.approx(0.001, abs=1e-10)

    def test_get_fee_defaults_to_taker(self):
        """Verify get_fee defaults to taker for unknown fee types."""
        fees = ExchangeFees(maker_fee=0.05, taker_fee=0.1)

        # Any non-"maker" string should return taker
        assert fees.get_fee("unknown") == fees.taker_fee
        assert fees.get_fee("") == fees.taker_fee


class TestExchangeConfig:
    """
    Tests for ExchangeConfig class (YAML loading).

    Bug prevented: Config file not found crashes app,
    or exchange not in config returns wrong default.
    """

    @pytest.fixture
    def temp_config_file(self):
        """Create a temporary config file for testing."""
        config_data = {
            "default_fee_type": "taker",
            "exchanges": {
                "binance": {"maker_fee": 0.1, "taker_fee": 0.1},
                "bybit": {"maker_fee": 0.075, "taker_fee": 0.1},
                "okx": {"maker_fee": 0.08, "taker_fee": 0.1},
            },
        }

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            yaml.dump(config_data, f)
            temp_path = f.name

        yield temp_path

        # Cleanup
        Path(temp_path).unlink(missing_ok=True)

    def test_load_config_from_yaml(self, temp_config_file):
        """Verify config loads correctly from YAML file."""
        config = ExchangeConfig(config_path=temp_config_file)

        assert "binance" in config.exchanges
        assert "bybit" in config.exchanges
        assert "okx" in config.exchanges

    def test_get_exchange_fees(self, temp_config_file):
        """Verify get_exchange_fees returns correct ExchangeFees object."""
        config = ExchangeConfig(config_path=temp_config_file)

        fees = config.get_exchange_fees("binance")
        assert fees is not None
        assert fees.taker_fee == pytest.approx(0.001, abs=1e-10)

    def test_get_exchange_fees_case_insensitive(self, temp_config_file):
        """Verify exchange name lookup is case-insensitive."""
        config = ExchangeConfig(config_path=temp_config_file)

        fees_lower = config.get_exchange_fees("binance")
        fees_upper = config.get_exchange_fees("BINANCE")
        fees_mixed = config.get_exchange_fees("Binance")

        assert fees_lower is not None
        assert fees_upper is not None
        assert fees_mixed is not None
        assert fees_lower.taker_fee == fees_upper.taker_fee == fees_mixed.taker_fee

    def test_get_exchange_fees_unknown_exchange(self, temp_config_file):
        """Verify unknown exchange returns None."""
        config = ExchangeConfig(config_path=temp_config_file)

        fees = config.get_exchange_fees("unknown_exchange")
        assert fees is None

    def test_get_fee_rate_uses_default_fee_type(self, temp_config_file):
        """Verify get_fee_rate uses default_fee_type when not specified."""
        config = ExchangeConfig(config_path=temp_config_file)

        # Config has default_fee_type: "taker"
        rate = config.get_fee_rate("bybit")

        # Bybit taker: 0.1% = 0.001
        assert rate == pytest.approx(0.001, abs=1e-10)

    def test_get_fee_rate_with_explicit_type(self, temp_config_file):
        """Verify get_fee_rate uses explicit fee_type when provided."""
        config = ExchangeConfig(config_path=temp_config_file)

        maker_rate = config.get_fee_rate("bybit", fee_type="maker")
        taker_rate = config.get_fee_rate("bybit", fee_type="taker")

        # Bybit maker: 0.075% = 0.00075
        assert maker_rate == pytest.approx(0.00075, abs=1e-10)
        # Bybit taker: 0.1% = 0.001
        assert taker_rate == pytest.approx(0.001, abs=1e-10)

    def test_get_fee_rate_unknown_exchange_returns_default(self, temp_config_file):
        """
        Verify unknown exchange returns default fee rate (0.1%).

        Bug prevented: App crashes or uses 0 fees for unknown exchange.
        """
        config = ExchangeConfig(config_path=temp_config_file)

        rate = config.get_fee_rate("unknown_exchange")

        # Default is 0.001 (0.1%)
        assert rate == pytest.approx(0.001, abs=1e-10)

    def test_missing_config_file_raises(self):
        """Verify missing config file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            ExchangeConfig(config_path="nonexistent_config.yaml")


class TestFeeCalculationIntegration:
    """
    Integration tests for fee calculations in trade scenarios.
    """

    @pytest.fixture
    def config(self):
        """Create config with test data."""
        config_data = {
            "default_fee_type": "taker",
            "exchanges": {
                "binance": {"maker_fee": 0.1, "taker_fee": 0.1},
            },
        }

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            yaml.dump(config_data, f)
            temp_path = f.name

        yield ExchangeConfig(config_path=temp_path)

        Path(temp_path).unlink(missing_ok=True)

    def test_fee_on_trade(self, config):
        """
        Verify fee calculation on a trade.

        Trade: $50,000 @ 0.1 BTC = $5,000 notional
        Fee rate: 0.1%
        Expected fee: $5.00
        """
        notional = 50000.0 * 0.1  # $5,000
        fee_rate = config.get_fee_rate("binance")
        fee = notional * fee_rate

        assert fee == pytest.approx(5.0, abs=0.01)

    def test_fee_total_for_round_trip(self, config):
        """
        Verify total fees for entry + exit (round trip).

        Entry: $50,000 @ 0.1 BTC = $5,000 notional
        Exit: $51,000 @ 0.1 BTC = $5,100 notional
        Fee rate: 0.1%

        Entry fee: $5.00
        Exit fee: $5.10
        Total fees: $10.10
        """
        fee_rate = config.get_fee_rate("binance")

        entry_notional = 50000.0 * 0.1
        exit_notional = 51000.0 * 0.1

        entry_fee = entry_notional * fee_rate
        exit_fee = exit_notional * fee_rate
        total_fees = entry_fee + exit_fee

        assert entry_fee == pytest.approx(5.0, abs=0.01)
        assert exit_fee == pytest.approx(5.1, abs=0.01)
        assert total_fees == pytest.approx(10.1, abs=0.01)
