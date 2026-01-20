"""
Tests for symbol normalizer in app/services/symbol_normalizer.py

Tests symbol parsing and exchange normalization.
"""

import pytest


class TestParseSymbol:
    """Tests for parse_symbol function."""

    def test_parse_simple_symbol(self):
        """Test parsing simple symbol without separator."""
        from app.services.symbol_normalizer import parse_symbol

        parsed = parse_symbol("BTCUSDT")
        assert parsed.base == "BTC"
        assert parsed.quote == "USDT"

    def test_parse_symbol_with_slash(self):
        """Test parsing symbol with slash separator."""
        from app.services.symbol_normalizer import parse_symbol

        parsed = parse_symbol("BTC/USDT")
        assert parsed.base == "BTC"
        assert parsed.quote == "USDT"

    def test_parse_symbol_with_hyphen(self):
        """Test parsing symbol with hyphen separator."""
        from app.services.symbol_normalizer import parse_symbol

        parsed = parse_symbol("BTC-USDT")
        assert parsed.base == "BTC"
        assert parsed.quote == "USDT"

    def test_parse_symbol_with_underscore(self):
        """Test parsing symbol with underscore separator."""
        from app.services.symbol_normalizer import parse_symbol

        parsed = parse_symbol("BTC_USDT")
        assert parsed.base == "BTC"
        assert parsed.quote == "USDT"

    def test_parse_symbol_lowercase(self):
        """Test parsing lowercase symbol."""
        from app.services.symbol_normalizer import parse_symbol

        parsed = parse_symbol("btcusdt")
        assert parsed.base == "BTC"
        assert parsed.quote == "USDT"

    def test_parse_symbol_various_quotes(self):
        """Test parsing symbols with various quote currencies."""
        from app.services.symbol_normalizer import parse_symbol

        # USDT
        parsed = parse_symbol("ETHUSDT")
        assert parsed.base == "ETH"
        assert parsed.quote == "USDT"

        # USDC
        parsed = parse_symbol("ETHUSDC")
        assert parsed.base == "ETH"
        assert parsed.quote == "USDC"

        # BTC
        parsed = parse_symbol("ETHBTC")
        assert parsed.base == "ETH"
        assert parsed.quote == "BTC"

    def test_parse_symbol_with_exchange_prefix(self):
        """Test parsing symbol with exchange prefix."""
        from app.services.symbol_normalizer import parse_symbol

        parsed = parse_symbol("BINANCE:BTCUSDT")
        assert parsed.base == "BTC"
        assert parsed.quote == "USDT"

    def test_parse_invalid_symbol_raises(self):
        """Test that invalid symbol raises ValueError."""
        from app.services.symbol_normalizer import parse_symbol

        with pytest.raises(ValueError):
            parse_symbol("INVALID")

    def test_parse_empty_symbol_raises(self):
        """Test that empty symbol raises ValueError."""
        from app.services.symbol_normalizer import parse_symbol

        with pytest.raises(ValueError):
            parse_symbol("")


class TestNormalizeExchange:
    """Tests for normalize_exchange function."""

    def test_binance_variations(self):
        """Test normalizing Binance variations."""
        from app.services.symbol_normalizer import normalize_exchange

        assert normalize_exchange("binance") == "binance"
        assert normalize_exchange("BINANCE") == "binance"
        assert normalize_exchange("Binance") == "binance"
        assert normalize_exchange("bin") == "binance"

    def test_bybit_variations(self):
        """Test normalizing Bybit variations."""
        from app.services.symbol_normalizer import normalize_exchange

        assert normalize_exchange("bybit") == "bybit"
        assert normalize_exchange("BYBIT") == "bybit"
        assert normalize_exchange("ByBit") == "bybit"

    def test_kucoin_variations(self):
        """Test normalizing KuCoin variations."""
        from app.services.symbol_normalizer import normalize_exchange

        assert normalize_exchange("kucoin") == "kucoin"
        assert normalize_exchange("KUCOIN") == "kucoin"
        assert normalize_exchange("KuCoin") == "kucoin"

    def test_okx_variations(self):
        """Test normalizing OKX variations."""
        from app.services.symbol_normalizer import normalize_exchange

        assert normalize_exchange("okx") == "okx"
        assert normalize_exchange("OKX") == "okx"
        assert normalize_exchange("okex") == "okx"
        assert normalize_exchange("OKEX") == "okx"

    def test_gateio_variations(self):
        """Test normalizing Gate.io variations."""
        from app.services.symbol_normalizer import normalize_exchange

        assert normalize_exchange("gateio") == "gateio"
        assert normalize_exchange("gate.io") == "gateio"
        assert normalize_exchange("GATEIO") == "gateio"
        assert normalize_exchange("gate") == "gateio"

    def test_mexc_variations(self):
        """Test normalizing MEXC variations."""
        from app.services.symbol_normalizer import normalize_exchange

        assert normalize_exchange("mexc") == "mexc"
        assert normalize_exchange("MEXC") == "mexc"
        assert normalize_exchange("mxc") == "mexc"

    def test_unknown_exchange(self):
        """Test that unknown exchange returns None."""
        from app.services.symbol_normalizer import normalize_exchange

        assert normalize_exchange("unknown") is None
        assert normalize_exchange("invalid_exchange") is None
        assert normalize_exchange("") is None


class TestParsedSymbol:
    """Tests for ParsedSymbol dataclass."""

    def test_parsed_symbol_attributes(self):
        """Test ParsedSymbol has correct attributes."""
        from app.services.symbol_normalizer import ParsedSymbol

        parsed = ParsedSymbol(base="BTC", quote="USDT")

        assert parsed.base == "BTC"
        assert parsed.quote == "USDT"

    def test_parsed_symbol_equality(self):
        """Test ParsedSymbol equality."""
        from app.services.symbol_normalizer import ParsedSymbol

        p1 = ParsedSymbol(base="BTC", quote="USDT")
        p2 = ParsedSymbol(base="BTC", quote="USDT")
        p3 = ParsedSymbol(base="ETH", quote="USDT")

        assert p1 == p2
        assert p1 != p3

    def test_format_for_exchange(self):
        """Test formatting symbol for different exchanges."""
        from app.services.symbol_normalizer import ParsedSymbol

        parsed = ParsedSymbol(base="BTC", quote="USDT")

        assert parsed.format_for_exchange("binance") == "BTCUSDT"
        assert parsed.format_for_exchange("okx") == "BTC-USDT"
        assert parsed.format_for_exchange("gateio") == "BTC_USDT"
        assert parsed.format_for_exchange("kucoin") == "BTC-USDT"

    def test_display(self):
        """Test display format."""
        from app.services.symbol_normalizer import ParsedSymbol

        parsed = ParsedSymbol(base="BTC", quote="USDT")
        assert parsed.display() == "BTC/USDT"


class TestFormatForExchange:
    """Tests for format_for_exchange helper function."""

    def test_format_for_binance(self):
        """Test formatting for Binance."""
        from app.services.symbol_normalizer import format_for_exchange

        assert format_for_exchange("BTC", "USDT", "binance") == "BTCUSDT"

    def test_format_for_okx(self):
        """Test formatting for OKX."""
        from app.services.symbol_normalizer import format_for_exchange

        assert format_for_exchange("BTC", "USDT", "okx") == "BTC-USDT"

    def test_format_for_gateio(self):
        """Test formatting for Gate.io."""
        from app.services.symbol_normalizer import format_for_exchange

        assert format_for_exchange("BTC", "USDT", "gateio") == "BTC_USDT"


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_is_valid_exchange(self):
        """Test is_valid_exchange function."""
        from app.services.symbol_normalizer import is_valid_exchange

        assert is_valid_exchange("binance") is True
        assert is_valid_exchange("bybit") is True
        assert is_valid_exchange("unknown") is False

    def test_get_supported_exchanges(self):
        """Test get_supported_exchanges function."""
        from app.services.symbol_normalizer import get_supported_exchanges

        exchanges = get_supported_exchanges()

        assert "binance" in exchanges
        assert "bybit" in exchanges
        assert "okx" in exchanges
        assert "gateio" in exchanges
        assert "kucoin" in exchanges
        assert "mexc" in exchanges
