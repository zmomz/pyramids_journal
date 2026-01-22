"""
Tests for symbol parsing and exchange normalization.

These are pure functions with no external dependencies - perfect for
table-driven tests that exhaustively cover all input formats.

Bug categories prevented:
- Wrong pair extraction from various symbol formats
- Unknown exchange errors due to missed aliases
- Incorrect symbol formatting for exchange APIs
"""

import pytest
from app.services.symbol_normalizer import (
    parse_symbol,
    normalize_exchange,
    format_for_exchange,
    is_valid_exchange,
    get_supported_exchanges,
    ParsedSymbol,
    EXCHANGE_ALIASES,
    QUOTE_CURRENCIES,
)


class TestParseSymbol:
    """
    Tests for parse_symbol() function.

    Bug prevented: Extracting wrong base/quote from symbol strings,
    leading to incorrect trades or API calls.
    """

    @pytest.mark.parametrize(
        "symbol,expected_base,expected_quote",
        [
            # Slash separator (common in TradingView)
            ("BTC/USDT", "BTC", "USDT"),
            ("ETH/BTC", "ETH", "BTC"),
            ("SOL/USDC", "SOL", "USDC"),
            # Hyphen separator (OKX, Kucoin)
            ("BTC-USDT", "BTC", "USDT"),
            ("ETH-BTC", "ETH", "BTC"),
            ("DOGE-USDT", "DOGE", "USDT"),
            # Underscore separator (Gate.io)
            ("BTC_USDT", "BTC", "USDT"),
            ("ETH_USDC", "ETH", "USDC"),
            # Concatenated (Binance, Bybit, MEXC)
            ("BTCUSDT", "BTC", "USDT"),
            ("ETHUSDT", "ETH", "USDT"),
            ("SOLUSDT", "SOL", "USDT"),
            ("DOGEUSDT", "DOGE", "USDT"),
            ("XRPUSDT", "XRP", "USDT"),
            # Less common quotes
            ("ETHBTC", "ETH", "BTC"),
            ("SOLBTC", "SOL", "BTC"),
            ("LINKETH", "LINK", "ETH"),
            ("BNBBUSD", "BNB", "BUSD"),
            ("BTCEUR", "BTC", "EUR"),
            # Exchange prefix (TradingView format)
            ("BINANCE:BTCUSDT", "BTC", "USDT"),
            ("BYBIT:ETHUSDT", "ETH", "USDT"),
            ("OKX:BTC-USDT", "BTC", "USDT"),
            ("KUCOIN:SOL/USDT", "SOL", "USDT"),
            # Case insensitivity
            ("btc/usdt", "BTC", "USDT"),
            ("Btc-Usdt", "BTC", "USDT"),
            ("btcusdt", "BTC", "USDT"),
            # Whitespace handling
            ("  BTC/USDT  ", "BTC", "USDT"),
        ],
        ids=[
            "slash-BTC/USDT",
            "slash-ETH/BTC",
            "slash-SOL/USDC",
            "hyphen-BTC-USDT",
            "hyphen-ETH-BTC",
            "hyphen-DOGE-USDT",
            "underscore-BTC_USDT",
            "underscore-ETH_USDC",
            "concat-BTCUSDT",
            "concat-ETHUSDT",
            "concat-SOLUSDT",
            "concat-DOGEUSDT",
            "concat-XRPUSDT",
            "concat-ETHBTC-quote",
            "concat-SOLBTC-quote",
            "concat-LINKETH-quote",
            "concat-BNBBUSD",
            "concat-BTCEUR-fiat",
            "prefix-BINANCE",
            "prefix-BYBIT",
            "prefix-OKX",
            "prefix-KUCOIN",
            "case-lower",
            "case-mixed",
            "case-concat-lower",
            "whitespace-padded",
        ],
    )
    def test_parse_symbol_valid_formats(self, symbol, expected_base, expected_quote):
        """Verify all valid symbol formats parse correctly."""
        result = parse_symbol(symbol)

        assert result.base == expected_base
        assert result.quote == expected_quote

    @pytest.mark.parametrize(
        "invalid_symbol",
        [
            "",  # Empty string
            "   ",  # Whitespace only
            "BTC",  # Single token, no quote detected
            "INVALID",  # Unknown token
            "X",  # Too short
        ],
        ids=["empty", "whitespace", "no-quote", "unknown", "too-short"],
    )
    def test_parse_symbol_invalid_raises(self, invalid_symbol):
        """Verify invalid symbols raise ValueError."""
        with pytest.raises(ValueError):
            parse_symbol(invalid_symbol)

    def test_parse_symbol_preserves_all_quote_currencies(self):
        """
        Verify all known quote currencies are detected.

        Bug prevented: New quote currency not recognized, causing
        wrong symbol parsing.
        """
        for quote in QUOTE_CURRENCIES:
            symbol = f"TEST{quote}"
            result = parse_symbol(symbol)
            assert result.quote == quote, f"Failed to detect quote: {quote}"
            assert result.base == "TEST"


class TestNormalizeExchange:
    """
    Tests for normalize_exchange() function.

    Bug prevented: Exchange aliases not recognized, causing
    "unknown exchange" errors for valid exchanges.
    """

    @pytest.mark.parametrize(
        "input_name,expected",
        [
            # Standard names
            ("binance", "binance"),
            ("bybit", "bybit"),
            ("okx", "okx"),
            ("gateio", "gateio"),
            ("kucoin", "kucoin"),
            ("mexc", "mexc"),
            # Aliases
            ("bin", "binance"),
            ("okex", "okx"),
            ("gate", "gateio"),
            ("gate.io", "gateio"),
            ("mxc", "mexc"),
            # Case variations
            ("BINANCE", "binance"),
            ("Binance", "binance"),
            ("BYBIT", "bybit"),
            ("OKX", "okx"),
            # Whitespace
            ("  binance  ", "binance"),
            (" bybit ", "bybit"),
        ],
        ids=[
            "binance",
            "bybit",
            "okx",
            "gateio",
            "kucoin",
            "mexc",
            "alias-bin",
            "alias-okex",
            "alias-gate",
            "alias-gate.io",
            "alias-mxc",
            "case-upper-binance",
            "case-mixed-binance",
            "case-upper-bybit",
            "case-upper-okx",
            "whitespace-binance",
            "whitespace-bybit",
        ],
    )
    def test_normalize_exchange_valid(self, input_name, expected):
        """Verify valid exchange names normalize correctly."""
        assert normalize_exchange(input_name) == expected

    @pytest.mark.parametrize(
        "invalid_name",
        [
            "",
            None,
            "unknown",
            "coinbase",
            "ftx",
            "kraken",
        ],
        ids=["empty", "none", "unknown", "coinbase", "ftx", "kraken"],
    )
    def test_normalize_exchange_invalid_returns_none(self, invalid_name):
        """Verify invalid/unknown exchanges return None."""
        assert normalize_exchange(invalid_name) is None

    def test_all_aliases_map_to_supported_exchange(self):
        """
        Verify all defined aliases map to a supported exchange.

        Bug prevented: Alias pointing to non-existent exchange.
        """
        supported = get_supported_exchanges()
        for alias, target in EXCHANGE_ALIASES.items():
            assert target in supported, f"Alias '{alias}' maps to unsupported '{target}'"


class TestFormatForExchange:
    """
    Tests for format_for_exchange() and ParsedSymbol.format_for_exchange().

    Bug prevented: Symbol formatted incorrectly for exchange API,
    causing API calls to fail.
    """

    @pytest.mark.parametrize(
        "base,quote,exchange,expected",
        [
            # Binance: concatenated (BTCUSDT)
            ("BTC", "USDT", "binance", "BTCUSDT"),
            ("ETH", "USDT", "binance", "ETHUSDT"),
            # Bybit: concatenated (BTCUSDT)
            ("BTC", "USDT", "bybit", "BTCUSDT"),
            ("SOL", "USDC", "bybit", "SOLUSDC"),
            # OKX: hyphen (BTC-USDT)
            ("BTC", "USDT", "okx", "BTC-USDT"),
            ("ETH", "BTC", "okx", "ETH-BTC"),
            # Gate.io: underscore (BTC_USDT)
            ("BTC", "USDT", "gateio", "BTC_USDT"),
            ("DOGE", "USDT", "gateio", "DOGE_USDT"),
            # Kucoin: hyphen (BTC-USDT)
            ("BTC", "USDT", "kucoin", "BTC-USDT"),
            ("XRP", "USDC", "kucoin", "XRP-USDC"),
            # MEXC: concatenated (BTCUSDT)
            ("BTC", "USDT", "mexc", "BTCUSDT"),
            ("LINK", "USDT", "mexc", "LINKUSDT"),
        ],
    )
    def test_format_for_exchange(self, base, quote, exchange, expected):
        """Verify symbol formatting matches exchange requirements."""
        # Test via convenience function
        assert format_for_exchange(base, quote, exchange) == expected

        # Test via ParsedSymbol method
        parsed = ParsedSymbol(base=base, quote=quote)
        assert parsed.format_for_exchange(exchange) == expected

    def test_format_normalizes_case(self):
        """Verify formatting normalizes to uppercase."""
        result = format_for_exchange("btc", "usdt", "binance")
        assert result == "BTCUSDT"


class TestParsedSymbol:
    """Tests for ParsedSymbol dataclass methods."""

    def test_display_format(self):
        """
        Verify display() returns human-readable format.

        Bug prevented: Wrong format shown in Telegram messages.
        """
        parsed = ParsedSymbol(base="BTC", quote="USDT")
        assert parsed.display() == "BTC/USDT"

    def test_format_for_unknown_exchange_raises(self):
        """Verify formatting for unknown exchange raises ValueError."""
        parsed = ParsedSymbol(base="BTC", quote="USDT")
        with pytest.raises(ValueError):
            parsed.format_for_exchange("unknown_exchange")

    def test_parsed_symbol_equality(self):
        """Test ParsedSymbol equality comparison."""
        p1 = ParsedSymbol(base="BTC", quote="USDT")
        p2 = ParsedSymbol(base="BTC", quote="USDT")
        p3 = ParsedSymbol(base="ETH", quote="USDT")

        assert p1 == p2
        assert p1 != p3


class TestIsValidExchange:
    """Tests for is_valid_exchange() function."""

    def test_valid_exchanges_return_true(self):
        """Verify all supported exchanges are valid."""
        for exchange in get_supported_exchanges():
            assert is_valid_exchange(exchange) is True

    def test_invalid_exchanges_return_false(self):
        """Verify unsupported exchanges are invalid."""
        assert is_valid_exchange("coinbase") is False
        assert is_valid_exchange("unknown") is False
        assert is_valid_exchange("") is False


class TestGetSupportedExchanges:
    """Tests for get_supported_exchanges() function."""

    def test_returns_all_exchanges(self):
        """Verify all expected exchanges are supported."""
        supported = get_supported_exchanges()

        expected = ["binance", "bybit", "okx", "gateio", "kucoin", "mexc"]
        for exchange in expected:
            assert exchange in supported

    def test_returns_list(self):
        """Verify return type is list."""
        result = get_supported_exchanges()
        assert isinstance(result, list)
        assert len(result) > 0
