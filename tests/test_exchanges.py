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
        # Use pytest.approx for floating point comparisons
        assert exchange.round_price(50000.123, 0.01) == pytest.approx(50000.12)
        assert exchange.round_price(50000.127, 0.01) == pytest.approx(50000.13)
        assert exchange.round_price(100.5, 1.0) == pytest.approx(101.0)


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


class TestExchangeNames:
    """Tests for exchange name properties."""

    def test_binance_name(self):
        """Test Binance exchange name."""
        from app.exchanges.binance import BinanceExchange

        exchange = BinanceExchange()
        assert exchange.name == "binance"

    def test_bybit_name(self):
        """Test Bybit exchange name."""
        from app.exchanges.bybit import BybitExchange

        exchange = BybitExchange()
        assert exchange.name == "bybit"

    def test_kucoin_name(self):
        """Test KuCoin exchange name."""
        from app.exchanges.kucoin import KucoinExchange

        exchange = KucoinExchange()
        assert exchange.name == "kucoin"

    def test_okx_name(self):
        """Test OKX exchange name."""
        from app.exchanges.okx import OKXExchange

        exchange = OKXExchange()
        assert exchange.name == "okx"

    def test_gateio_name(self):
        """Test Gate.io exchange name."""
        from app.exchanges.gateio import GateIOExchange

        exchange = GateIOExchange()
        assert exchange.name == "gateio"

    def test_mexc_name(self):
        """Test MEXC exchange name."""
        from app.exchanges.mexc import MEXCExchange

        exchange = MEXCExchange()
        assert exchange.name == "mexc"


class TestBinanceGetPrice:
    """Tests for Binance get_price method."""

    @pytest.mark.asyncio
    async def test_get_price_success(self):
        """Test successful price fetch from Binance."""
        from app.exchanges.binance import BinanceExchange

        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={
                "price": "50000.50",
                "time": 1705762800000
            })
            mock_response.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response.__aexit__ = AsyncMock(return_value=None)

            mock_session = MagicMock()
            mock_session.get = MagicMock(return_value=mock_response)
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_session_class.return_value = mock_session

            exchange = BinanceExchange()
            async with exchange:
                price_data = await exchange.get_price("BTC", "USDT")

            assert price_data.price == 50000.50


class TestBybitGetPrice:
    """Tests for Bybit get_price method."""

    @pytest.mark.asyncio
    async def test_get_price_success(self):
        """Test successful price fetch from Bybit."""
        from app.exchanges.bybit import BybitExchange

        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={
                "retCode": 0,
                "result": {
                    "list": [{"lastPrice": "50000.50"}]
                }
            })
            mock_response.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response.__aexit__ = AsyncMock(return_value=None)

            mock_session = MagicMock()
            mock_session.get = MagicMock(return_value=mock_response)
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_session_class.return_value = mock_session

            exchange = BybitExchange()
            async with exchange:
                price_data = await exchange.get_price("BTC", "USDT")

            assert price_data.price == 50000.50


class TestExchangeServiceIntegration:
    """Integration tests for ExchangeService."""

    def test_get_all_supported_exchanges(self):
        """Test getting all supported exchange names."""
        from app.services.exchange_service import ExchangeService

        # Test all known exchanges
        exchanges = ["binance", "bybit", "okx", "kucoin", "gateio", "mexc"]

        for exchange_name in exchanges:
            adapter = ExchangeService.get_exchange_adapter(exchange_name)
            assert adapter is not None

    def test_unknown_exchange_raises_error(self):
        """Test that unknown exchange raises ValueError."""
        from app.services.exchange_service import ExchangeService

        with pytest.raises(ValueError, match="Unknown exchange"):
            ExchangeService.get_exchange_adapter("unknown_exchange")


class TestBaseExchangeContextManager:
    """Tests for BaseExchange context manager."""

    @pytest.mark.asyncio
    async def test_context_manager_creates_session(self):
        """Test that context manager creates and closes session."""
        from app.exchanges.binance import BinanceExchange

        exchange = BinanceExchange()

        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = MagicMock()
            mock_session.close = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_session_class.return_value = mock_session

            async with exchange:
                pass

            mock_session.close.assert_called_once()


class TestSymbolInfoDataclass:
    """Tests for SymbolInfo dataclass."""

    def test_symbol_info_creation(self):
        """Test SymbolInfo dataclass creation."""
        from app.exchanges.base import SymbolInfo

        info = SymbolInfo(
            base="BTC",
            quote="USDT",
            price_precision=2,
            qty_precision=4,
            min_qty=0.0001,
            min_notional=10.0,
            tick_size=0.01
        )

        assert info.base == "BTC"
        assert info.quote == "USDT"
        assert info.price_precision == 2
        assert info.qty_precision == 4
        assert info.min_qty == 0.0001
        assert info.min_notional == 10.0
        assert info.tick_size == 0.01


class TestPriceDataDataclass:
    """Tests for PriceData dataclass."""

    def test_price_data_creation(self):
        """Test PriceData dataclass creation."""
        from app.exchanges.base import PriceData

        data = PriceData(
            price=50000.50,
            timestamp=1705762800000
        )

        assert data.price == 50000.50
        assert data.timestamp == 1705762800000

    def test_price_data_optional_timestamp(self):
        """Test PriceData with optional timestamp."""
        from app.exchanges.base import PriceData

        data = PriceData(price=50000.50)

        assert data.price == 50000.50
        assert data.timestamp is None
