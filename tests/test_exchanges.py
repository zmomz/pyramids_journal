"""
Tests for exchange implementations in app/exchanges/

Tests the price fetching and symbol info functionality.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestExchangeBase:
    """Tests for base exchange functionality."""

    def test_round_quantity(self):
        """Test quantity rounding to precision."""
        from app.exchanges.base import BaseExchange

        # Create a concrete implementation for testing
        class TestExchange(BaseExchange):
            name = "test"
            async def get_price(self, base, quote):
                pass
            async def get_symbol_info(self, base, quote):
                pass
            def format_symbol(self, base, quote):
                return f"{base}{quote}"

        exchange = TestExchange()
        # Test different precisions
        assert exchange.round_quantity(0.123456789, 4) == 0.1235
        assert exchange.round_quantity(0.123456789, 2) == 0.12
        assert exchange.round_quantity(0.123456789, 8) == 0.12345679
        assert exchange.round_quantity(1.999, 0) == 2.0

    def test_round_price(self):
        """Test price rounding to tick size."""
        from app.exchanges.base import BaseExchange

        class TestExchange(BaseExchange):
            name = "test"
            async def get_price(self, base, quote):
                pass
            async def get_symbol_info(self, base, quote):
                pass
            def format_symbol(self, base, quote):
                return f"{base}{quote}"

        exchange = TestExchange()
        # round_price takes tick_size, not precision
        assert exchange.round_price(50000.123, 0.01) == 50000.12
        assert exchange.round_price(50000.127, 0.01) == 50000.13
        assert exchange.round_price(100.5, 1.0) == 101.0


class TestExchangeService:
    """Tests for exchange service."""

    def test_get_exchange_adapter_binance(self):
        """Test getting Binance exchange adapter."""
        from app.services.exchange_service import ExchangeService
        from app.exchanges.binance import BinanceExchange

        adapter = ExchangeService.get_exchange_adapter("binance")
        assert adapter == BinanceExchange

    def test_get_exchange_adapter_bybit(self):
        """Test getting Bybit exchange adapter."""
        from app.services.exchange_service import ExchangeService
        from app.exchanges.bybit import BybitExchange

        adapter = ExchangeService.get_exchange_adapter("bybit")
        assert adapter == BybitExchange

    def test_get_exchange_adapter_kucoin(self):
        """Test getting KuCoin exchange adapter."""
        from app.services.exchange_service import ExchangeService
        from app.exchanges.kucoin import KucoinExchange

        adapter = ExchangeService.get_exchange_adapter("kucoin")
        assert adapter == KucoinExchange

    def test_get_exchange_adapter_unknown(self):
        """Test getting unknown exchange raises error."""
        from app.services.exchange_service import ExchangeService

        with pytest.raises(ValueError, match="Unknown exchange"):
            ExchangeService.get_exchange_adapter("unknown_exchange")

    @pytest.mark.asyncio
    async def test_get_price_success(self):
        """Test successful price fetch."""
        from app.services.exchange_service import ExchangeService
        from app.exchanges.base import PriceData

        with patch.object(ExchangeService, "get_exchange_adapter") as mock_get:
            mock_adapter = MagicMock()
            mock_adapter_instance = MagicMock()
            mock_adapter_instance.get_price = AsyncMock(return_value=PriceData(
                price=50000.0,
                timestamp=1705762800000
            ))
            mock_adapter.return_value.__aenter__ = AsyncMock(return_value=mock_adapter_instance)
            mock_adapter.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_get.return_value = mock_adapter

            price_data = await ExchangeService.get_price("binance", "BTC", "USDT")

            assert price_data.price == 50000.0

    @pytest.mark.asyncio
    async def test_get_price_unknown_exchange(self):
        """Test price fetch for unknown exchange raises error."""
        from app.services.exchange_service import ExchangeService

        with pytest.raises(ValueError, match="Unknown exchange"):
            await ExchangeService.get_price("unknown", "BTC", "USDT")

    @pytest.mark.asyncio
    async def test_validate_order_success(self):
        """Test successful order validation."""
        from app.services.exchange_service import ExchangeService
        from app.exchanges.base import SymbolInfo

        with patch.object(ExchangeService, "get_symbol_info") as mock_info:
            mock_info.return_value = SymbolInfo(
                base="BTC",
                quote="USDT",
                price_precision=2,
                qty_precision=4,
                min_qty=0.0001,
                min_notional=10.0,
                tick_size=0.01
            )

            is_valid, error = await ExchangeService.validate_order(
                "binance", "BTC", "USDT",
                size=0.001,  # $50 at $50k price
                price=50000.0
            )

            assert is_valid is True
            assert error is None

    @pytest.mark.asyncio
    async def test_validate_order_below_min_qty(self):
        """Test order validation fails for quantity below minimum."""
        from app.services.exchange_service import ExchangeService
        from app.exchanges.base import SymbolInfo

        with patch.object(ExchangeService, "get_symbol_info") as mock_info:
            mock_info.return_value = SymbolInfo(
                base="BTC",
                quote="USDT",
                price_precision=2,
                qty_precision=4,
                min_qty=0.001,
                min_notional=10.0,
                tick_size=0.01
            )

            is_valid, error = await ExchangeService.validate_order(
                "binance", "BTC", "USDT",
                size=0.0001,  # Below min_qty
                price=50000.0
            )

            assert is_valid is False
            assert "minimum" in error.lower() or "below" in error.lower()

    @pytest.mark.asyncio
    async def test_validate_order_below_min_notional(self):
        """Test order validation fails for notional below minimum."""
        from app.services.exchange_service import ExchangeService
        from app.exchanges.base import SymbolInfo

        with patch.object(ExchangeService, "get_symbol_info") as mock_info:
            mock_info.return_value = SymbolInfo(
                base="BTC",
                quote="USDT",
                price_precision=2,
                qty_precision=4,
                min_qty=0.0001,
                min_notional=100.0,  # $100 minimum
                tick_size=0.01
            )

            is_valid, error = await ExchangeService.validate_order(
                "binance", "BTC", "USDT",
                size=0.001,  # $50 at $50k price (below $100 min)
                price=50000.0
            )

            assert is_valid is False
            assert "notional" in error.lower()

    def test_round_quantity(self):
        """Test quantity rounding."""
        from app.services.exchange_service import ExchangeService

        assert ExchangeService.round_quantity(0.123456789, 4) == 0.1235
        assert ExchangeService.round_quantity(0.123456789, 2) == 0.12

    def test_round_price(self):
        """Test price rounding."""
        from app.services.exchange_service import ExchangeService

        assert ExchangeService.round_price(50000.123, 0.01) == 50000.12


class TestBinanceExchange:
    """Tests for Binance exchange implementation."""

    def test_format_symbol(self):
        """Test symbol formatting for Binance."""
        from app.exchanges.binance import BinanceExchange

        exchange = BinanceExchange()
        assert exchange.format_symbol("BTC", "USDT") == "BTCUSDT"
        assert exchange.format_symbol("ETH", "BTC") == "ETHBTC"


class TestBybitExchange:
    """Tests for Bybit exchange implementation."""

    def test_format_symbol(self):
        """Test symbol formatting for Bybit."""
        from app.exchanges.bybit import BybitExchange

        exchange = BybitExchange()
        assert exchange.format_symbol("BTC", "USDT") == "BTCUSDT"


class TestKuCoinExchange:
    """Tests for KuCoin exchange implementation."""

    def test_format_symbol(self):
        """Test symbol formatting for KuCoin."""
        from app.exchanges.kucoin import KucoinExchange

        exchange = KucoinExchange()
        # KuCoin uses hyphen separator
        assert exchange.format_symbol("BTC", "USDT") == "BTC-USDT"


class TestOKXExchange:
    """Tests for OKX exchange implementation."""

    def test_format_symbol(self):
        """Test symbol formatting for OKX."""
        from app.exchanges.okx import OKXExchange

        exchange = OKXExchange()
        # OKX uses hyphen separator
        assert exchange.format_symbol("BTC", "USDT") == "BTC-USDT"


class TestGateIOExchange:
    """Tests for Gate.io exchange implementation."""

    def test_format_symbol(self):
        """Test symbol formatting for Gate.io."""
        from app.exchanges.gateio import GateIOExchange

        exchange = GateIOExchange()
        # Gate.io uses underscore separator
        assert exchange.format_symbol("BTC", "USDT") == "BTC_USDT"


class TestMEXCExchange:
    """Tests for MEXC exchange implementation."""

    def test_format_symbol(self):
        """Test symbol formatting for MEXC."""
        from app.exchanges.mexc import MEXCExchange

        exchange = MEXCExchange()
        assert exchange.format_symbol("BTC", "USDT") == "BTCUSDT"
