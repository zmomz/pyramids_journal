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

        # Test different precisions
        assert BaseExchange.round_quantity(0.123456789, 4) == 0.1234
        assert BaseExchange.round_quantity(0.123456789, 2) == 0.12
        assert BaseExchange.round_quantity(0.123456789, 8) == 0.12345678
        assert BaseExchange.round_quantity(1.999, 0) == 1.0

    def test_round_price(self):
        """Test price rounding to precision."""
        from app.exchanges.base import BaseExchange

        assert BaseExchange.round_price(50000.123456, 2) == 50000.12
        assert BaseExchange.round_price(0.00012345, 8) == 0.00012345


class TestExchangeService:
    """Tests for exchange service."""

    @pytest.mark.asyncio
    async def test_get_exchange_binance(self):
        """Test getting Binance exchange instance."""
        from app.services.exchange_service import ExchangeService

        service = ExchangeService()
        exchange = service._get_exchange("binance")

        assert exchange is not None
        assert exchange.name == "binance"

    @pytest.mark.asyncio
    async def test_get_exchange_bybit(self):
        """Test getting Bybit exchange instance."""
        from app.services.exchange_service import ExchangeService

        service = ExchangeService()
        exchange = service._get_exchange("bybit")

        assert exchange is not None
        assert exchange.name == "bybit"

    @pytest.mark.asyncio
    async def test_get_exchange_kucoin(self):
        """Test getting KuCoin exchange instance."""
        from app.services.exchange_service import ExchangeService

        service = ExchangeService()
        exchange = service._get_exchange("kucoin")

        assert exchange is not None
        assert exchange.name == "kucoin"

    @pytest.mark.asyncio
    async def test_get_exchange_unknown(self):
        """Test getting unknown exchange returns None."""
        from app.services.exchange_service import ExchangeService

        service = ExchangeService()
        exchange = service._get_exchange("unknown_exchange")

        assert exchange is None

    @pytest.mark.asyncio
    async def test_get_price_success(self):
        """Test successful price fetch."""
        from app.services.exchange_service import ExchangeService, PriceData

        service = ExchangeService()

        with patch.object(service, "_get_exchange") as mock_get:
            mock_exchange = MagicMock()
            mock_exchange.get_price = AsyncMock(return_value=PriceData(
                price=50000.0,
                timestamp="2026-01-20T12:00:00Z"
            ))
            mock_get.return_value = mock_exchange

            price_data = await service.get_price("binance", "BTC", "USDT")

            assert price_data.price == 50000.0

    @pytest.mark.asyncio
    async def test_get_price_unknown_exchange(self):
        """Test price fetch for unknown exchange raises error."""
        from app.services.exchange_service import ExchangeService

        service = ExchangeService()

        with patch.object(service, "_get_exchange", return_value=None):
            with pytest.raises(ValueError, match="Unknown exchange"):
                await service.get_price("unknown", "BTC", "USDT")

    @pytest.mark.asyncio
    async def test_get_symbol_info_success(self):
        """Test successful symbol info fetch."""
        from app.services.exchange_service import ExchangeService, SymbolInfo

        service = ExchangeService()

        with patch.object(service, "_get_exchange") as mock_get:
            mock_exchange = MagicMock()
            mock_exchange.get_symbol_info = AsyncMock(return_value=SymbolInfo(
                price_precision=2,
                qty_precision=4,
                min_qty=0.0001,
                min_notional=10.0,
                tick_size=0.01
            ))
            mock_get.return_value = mock_exchange

            symbol_info = await service.get_symbol_info("binance", "BTC", "USDT")

            assert symbol_info.qty_precision == 4
            assert symbol_info.min_notional == 10.0

    @pytest.mark.asyncio
    async def test_validate_order_success(self):
        """Test successful order validation."""
        from app.services.exchange_service import ExchangeService, SymbolInfo

        service = ExchangeService()

        with patch.object(service, "get_symbol_info") as mock_info:
            mock_info.return_value = SymbolInfo(
                price_precision=2,
                qty_precision=4,
                min_qty=0.0001,
                min_notional=10.0,
                tick_size=0.01
            )

            is_valid, error = await service.validate_order(
                "binance", "BTC", "USDT",
                quantity=0.001,  # $50 at $50k price
                price=50000.0
            )

            assert is_valid is True
            assert error is None

    @pytest.mark.asyncio
    async def test_validate_order_below_min_qty(self):
        """Test order validation fails for quantity below minimum."""
        from app.services.exchange_service import ExchangeService, SymbolInfo

        service = ExchangeService()

        with patch.object(service, "get_symbol_info") as mock_info:
            mock_info.return_value = SymbolInfo(
                price_precision=2,
                qty_precision=4,
                min_qty=0.001,
                min_notional=10.0,
                tick_size=0.01
            )

            is_valid, error = await service.validate_order(
                "binance", "BTC", "USDT",
                quantity=0.0001,  # Below min_qty
                price=50000.0
            )

            assert is_valid is False
            assert "minimum quantity" in error.lower()

    @pytest.mark.asyncio
    async def test_validate_order_below_min_notional(self):
        """Test order validation fails for notional below minimum."""
        from app.services.exchange_service import ExchangeService, SymbolInfo

        service = ExchangeService()

        with patch.object(service, "get_symbol_info") as mock_info:
            mock_info.return_value = SymbolInfo(
                price_precision=2,
                qty_precision=4,
                min_qty=0.0001,
                min_notional=10.0,
                tick_size=0.01
            )

            is_valid, error = await service.validate_order(
                "binance", "BTC", "USDT",
                quantity=0.0001,  # $5 at $50k price (below $10 min)
                price=50000.0
            )

            assert is_valid is False
            assert "notional" in error.lower()


class TestBinanceExchange:
    """Tests for Binance exchange implementation."""

    def test_build_symbol(self):
        """Test symbol building for Binance."""
        from app.exchanges.binance import BinanceExchange

        exchange = BinanceExchange()
        assert exchange._build_symbol("BTC", "USDT") == "BTCUSDT"
        assert exchange._build_symbol("ETH", "BTC") == "ETHBTC"


class TestBybitExchange:
    """Tests for Bybit exchange implementation."""

    def test_build_symbol(self):
        """Test symbol building for Bybit."""
        from app.exchanges.bybit import BybitExchange

        exchange = BybitExchange()
        assert exchange._build_symbol("BTC", "USDT") == "BTCUSDT"


class TestKuCoinExchange:
    """Tests for KuCoin exchange implementation."""

    def test_build_symbol(self):
        """Test symbol building for KuCoin."""
        from app.exchanges.kucoin import KuCoinExchange

        exchange = KuCoinExchange()
        # KuCoin uses hyphen separator
        assert exchange._build_symbol("BTC", "USDT") == "BTC-USDT"


class TestOKXExchange:
    """Tests for OKX exchange implementation."""

    def test_build_symbol(self):
        """Test symbol building for OKX."""
        from app.exchanges.okx import OKXExchange

        exchange = OKXExchange()
        # OKX uses hyphen separator
        assert exchange._build_symbol("BTC", "USDT") == "BTC-USDT"


class TestGateIOExchange:
    """Tests for Gate.io exchange implementation."""

    def test_build_symbol(self):
        """Test symbol building for Gate.io."""
        from app.exchanges.gateio import GateIOExchange

        exchange = GateIOExchange()
        # Gate.io uses underscore separator
        assert exchange._build_symbol("BTC", "USDT") == "BTC_USDT"


class TestMEXCExchange:
    """Tests for MEXC exchange implementation."""

    def test_build_symbol(self):
        """Test symbol building for MEXC."""
        from app.exchanges.mexc import MEXCExchange

        exchange = MEXCExchange()
        assert exchange._build_symbol("BTC", "USDT") == "BTCUSDT"
