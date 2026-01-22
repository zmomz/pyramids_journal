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
        # Python's banker's rounding rounds 0.5 to nearest even (100.0, not 101.0)
        assert exchange.round_price(100.5, 1.0) == pytest.approx(100.0)
        assert exchange.round_price(101.5, 1.0) == pytest.approx(102.0)


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
        """Test successful price fetch from Binance using httpx."""
        from app.exchanges.binance import BinanceExchange
        import httpx

        exchange = BinanceExchange()

        # Mock the httpx client response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "price": "50000.50",
            "time": 1705762800000
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(httpx.AsyncClient, "request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            async with exchange:
                price_data = await exchange.get_price("BTC", "USDT")

            assert price_data.price == 50000.50


class TestBybitGetPrice:
    """Tests for Bybit get_price method."""

    @pytest.mark.asyncio
    async def test_get_price_success(self):
        """Test successful price fetch from Bybit using httpx."""
        from app.exchanges.bybit import BybitExchange
        import httpx

        exchange = BybitExchange()

        # Mock the httpx client response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "retCode": 0,
            "result": {
                "list": [{"lastPrice": "50000.50"}]
            },
            "time": 1705762800000
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(httpx.AsyncClient, "request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

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
        """Test that context manager creates and closes client."""
        from app.exchanges.binance import BinanceExchange
        import httpx

        exchange = BinanceExchange()

        # Use the real context manager but don't make any requests
        async with exchange:
            # Client should be set
            assert exchange._client is not None
            assert isinstance(exchange._client, httpx.AsyncClient)

        # After exit, client should be closed (but reference may still exist)


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

    def test_price_data_with_timestamp(self):
        """Test PriceData with different timestamp values."""
        from app.exchanges.base import PriceData

        data = PriceData(price=50000.50, timestamp=0)
        assert data.price == 50000.50
        assert data.timestamp == 0

        # Test with a very large timestamp
        data2 = PriceData(price=60000.0, timestamp=9999999999999)
        assert data2.timestamp == 9999999999999


class TestOKXGetPrice:
    """Tests for OKX get_price method."""

    @pytest.mark.asyncio
    async def test_get_price_success(self):
        """Test successful price fetch from OKX."""
        from app.exchanges.okx import OKXExchange
        import httpx

        exchange = OKXExchange()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "code": "0",
            "data": [{"last": "50000.50", "ts": 1705762800000}]
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(httpx.AsyncClient, "request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            async with exchange:
                price_data = await exchange.get_price("BTC", "USDT")

            assert price_data.price == 50000.50

    @pytest.mark.asyncio
    async def test_get_price_symbol_not_found(self):
        """Test price fetch for non-existent symbol."""
        from app.exchanges.okx import OKXExchange
        from app.exchanges.base import SymbolNotFoundError
        import httpx

        exchange = OKXExchange()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"code": "0", "data": []}
        mock_response.raise_for_status = MagicMock()

        with patch.object(httpx.AsyncClient, "request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            async with exchange:
                with pytest.raises(SymbolNotFoundError):
                    await exchange.get_price("INVALID", "USDT")

    @pytest.mark.asyncio
    async def test_get_price_api_error(self):
        """Test price fetch with API error response."""
        from app.exchanges.okx import OKXExchange
        from app.exchanges.base import ExchangeAPIError
        import httpx

        exchange = OKXExchange()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"code": "51001", "msg": "Instrument does not exist"}
        mock_response.raise_for_status = MagicMock()

        with patch.object(httpx.AsyncClient, "request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            async with exchange:
                with pytest.raises(ExchangeAPIError):
                    await exchange.get_price("BTC", "USDT")


class TestOKXGetSymbolInfo:
    """Tests for OKX get_symbol_info method."""

    @pytest.mark.asyncio
    async def test_get_symbol_info_success(self):
        """Test successful symbol info fetch from OKX."""
        from app.exchanges.okx import OKXExchange
        import httpx

        exchange = OKXExchange()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "code": "0",
            "data": [{
                "tickSz": "0.01",
                "lotSz": "0.0001",
                "minSz": "0.0001"
            }]
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(httpx.AsyncClient, "request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            async with exchange:
                info = await exchange.get_symbol_info("BTC", "USDT")

            assert info.base == "BTC"
            assert info.quote == "USDT"
            assert info.tick_size == 0.01


class TestKuCoinGetPrice:
    """Tests for KuCoin get_price method."""

    @pytest.mark.asyncio
    async def test_get_price_success(self):
        """Test successful price fetch from KuCoin."""
        from app.exchanges.kucoin import KucoinExchange
        import httpx

        exchange = KucoinExchange()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "code": "200000",
            "data": {"price": "50000.50", "time": 1705762800000}
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(httpx.AsyncClient, "request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            async with exchange:
                price_data = await exchange.get_price("BTC", "USDT")

            assert price_data.price == 50000.50

    @pytest.mark.asyncio
    async def test_get_price_symbol_not_found(self):
        """Test price fetch for non-existent symbol."""
        from app.exchanges.kucoin import KucoinExchange
        from app.exchanges.base import SymbolNotFoundError
        import httpx

        exchange = KucoinExchange()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"code": "200000", "data": None}
        mock_response.raise_for_status = MagicMock()

        with patch.object(httpx.AsyncClient, "request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            async with exchange:
                with pytest.raises(SymbolNotFoundError):
                    await exchange.get_price("INVALID", "USDT")

    @pytest.mark.asyncio
    async def test_get_price_api_error(self):
        """Test price fetch with API error response."""
        from app.exchanges.kucoin import KucoinExchange
        from app.exchanges.base import ExchangeAPIError
        import httpx

        exchange = KucoinExchange()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"code": "400001", "msg": "Bad Request"}
        mock_response.raise_for_status = MagicMock()

        with patch.object(httpx.AsyncClient, "request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            async with exchange:
                with pytest.raises(ExchangeAPIError):
                    await exchange.get_price("BTC", "USDT")


class TestKuCoinGetSymbolInfo:
    """Tests for KuCoin get_symbol_info method."""

    @pytest.mark.asyncio
    async def test_get_symbol_info_success(self):
        """Test successful symbol info fetch from KuCoin."""
        from app.exchanges.kucoin import KucoinExchange
        import httpx

        exchange = KucoinExchange()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "code": "200000",
            "data": [{
                "symbol": "BTC-USDT",
                "priceIncrement": "0.01",
                "baseIncrement": "0.0001",
                "baseMinSize": "0.0001",
                "quoteMinSize": "10"
            }]
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(httpx.AsyncClient, "request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            async with exchange:
                info = await exchange.get_symbol_info("BTC", "USDT")

            assert info.base == "BTC"
            assert info.quote == "USDT"
            assert info.min_notional == 10.0


class TestGateIOGetPrice:
    """Tests for Gate.io get_price method."""

    @pytest.mark.asyncio
    async def test_get_price_success(self):
        """Test successful price fetch from Gate.io."""
        from app.exchanges.gateio import GateIOExchange
        import httpx

        exchange = GateIOExchange()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [{"last": "50000.50"}]
        mock_response.raise_for_status = MagicMock()

        with patch.object(httpx.AsyncClient, "request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            async with exchange:
                price_data = await exchange.get_price("BTC", "USDT")

            assert price_data.price == 50000.50

    @pytest.mark.asyncio
    async def test_get_price_symbol_not_found(self):
        """Test price fetch for non-existent symbol."""
        from app.exchanges.gateio import GateIOExchange
        from app.exchanges.base import SymbolNotFoundError
        import httpx

        exchange = GateIOExchange()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = []
        mock_response.raise_for_status = MagicMock()

        with patch.object(httpx.AsyncClient, "request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            async with exchange:
                with pytest.raises(SymbolNotFoundError):
                    await exchange.get_price("INVALID", "USDT")


class TestGateIOGetSymbolInfo:
    """Tests for Gate.io get_symbol_info method."""

    @pytest.mark.asyncio
    async def test_get_symbol_info_success(self):
        """Test successful symbol info fetch from Gate.io."""
        from app.exchanges.gateio import GateIOExchange
        import httpx

        exchange = GateIOExchange()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "precision": 2,
            "amount_precision": 4,
            "min_base_amount": "0.0001",
            "min_quote_amount": "10"
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(httpx.AsyncClient, "request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            async with exchange:
                info = await exchange.get_symbol_info("BTC", "USDT")

            assert info.base == "BTC"
            assert info.quote == "USDT"
            assert info.price_precision == 2
            assert info.qty_precision == 4


class TestMEXCGetPrice:
    """Tests for MEXC get_price method."""

    @pytest.mark.asyncio
    async def test_get_price_success(self):
        """Test successful price fetch from MEXC."""
        from app.exchanges.mexc import MEXCExchange
        import httpx

        exchange = MEXCExchange()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"symbol": "BTCUSDT", "price": "50000.50"}
        mock_response.raise_for_status = MagicMock()

        with patch.object(httpx.AsyncClient, "request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            async with exchange:
                price_data = await exchange.get_price("BTC", "USDT")

            assert price_data.price == 50000.50

    @pytest.mark.asyncio
    async def test_get_price_symbol_not_found(self):
        """Test price fetch for non-existent symbol."""
        from app.exchanges.mexc import MEXCExchange
        from app.exchanges.base import SymbolNotFoundError
        import httpx

        exchange = MEXCExchange()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}
        mock_response.raise_for_status = MagicMock()

        with patch.object(httpx.AsyncClient, "request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            async with exchange:
                with pytest.raises(SymbolNotFoundError):
                    await exchange.get_price("INVALID", "USDT")


class TestMEXCGetSymbolInfo:
    """Tests for MEXC get_symbol_info method."""

    @pytest.mark.asyncio
    async def test_get_symbol_info_success(self):
        """Test successful symbol info fetch from MEXC."""
        from app.exchanges.mexc import MEXCExchange
        import httpx

        exchange = MEXCExchange()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "symbols": [{
                "symbol": "BTCUSDT",
                "quotePrecision": 2,
                "baseSizePrecision": 4,
                "filters": [
                    {"filterType": "LOT_SIZE", "minQty": "0.0001", "stepSize": "0.0001"},
                    {"filterType": "MIN_NOTIONAL", "minNotional": "10"},
                    {"filterType": "PRICE_FILTER", "tickSize": "0.01"}
                ]
            }]
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(httpx.AsyncClient, "request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            async with exchange:
                info = await exchange.get_symbol_info("BTC", "USDT")

            assert info.base == "BTC"
            assert info.quote == "USDT"
            assert info.min_qty == 0.0001
            assert info.min_notional == 10.0

    @pytest.mark.asyncio
    async def test_get_symbol_info_not_found(self):
        """Test symbol info fetch for non-existent symbol."""
        from app.exchanges.mexc import MEXCExchange
        from app.exchanges.base import SymbolNotFoundError
        import httpx

        exchange = MEXCExchange()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"symbols": []}
        mock_response.raise_for_status = MagicMock()

        with patch.object(httpx.AsyncClient, "request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            async with exchange:
                with pytest.raises(SymbolNotFoundError):
                    await exchange.get_symbol_info("INVALID", "USDT")


class TestBinanceGetSymbolInfo:
    """Tests for Binance get_symbol_info method."""

    @pytest.mark.asyncio
    async def test_get_symbol_info_success(self):
        """Test successful symbol info fetch from Binance."""
        from app.exchanges.binance import BinanceExchange
        import httpx

        exchange = BinanceExchange()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "symbols": [{
                "symbol": "BTCUSDT",
                "baseAsset": "BTC",
                "quoteAsset": "USDT",
                "filters": [
                    {"filterType": "PRICE_FILTER", "tickSize": "0.01"},
                    {"filterType": "LOT_SIZE", "minQty": "0.00001", "stepSize": "0.00001"},
                    {"filterType": "NOTIONAL", "minNotional": "10.0"}
                ]
            }]
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(httpx.AsyncClient, "request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            async with exchange:
                info = await exchange.get_symbol_info("BTC", "USDT")

            assert info.base == "BTC"
            assert info.quote == "USDT"
            assert info.min_notional == 10.0


class TestBybitGetSymbolInfo:
    """Tests for Bybit get_symbol_info method."""

    @pytest.mark.asyncio
    async def test_get_symbol_info_success(self):
        """Test successful symbol info fetch from Bybit."""
        from app.exchanges.bybit import BybitExchange
        import httpx

        exchange = BybitExchange()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "retCode": 0,
            "result": {
                "list": [{
                    "symbol": "BTCUSDT",
                    "baseCoin": "BTC",
                    "quoteCoin": "USDT",
                    "lotSizeFilter": {"minOrderQty": "0.00001", "basePrecision": "0.00001"},
                    "priceFilter": {"tickSize": "0.01"}
                }]
            }
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(httpx.AsyncClient, "request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            async with exchange:
                info = await exchange.get_symbol_info("BTC", "USDT")

            assert info.base == "BTC"
            assert info.quote == "USDT"


class TestExchangeEdgeCases:
    """Edge case tests for exchange functionality."""

    def test_round_quantity_zero(self):
        """Test quantity rounding with zero value."""
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
        assert exchange.round_quantity(0, 4) == 0.0

    def test_round_quantity_very_small(self):
        """Test quantity rounding with very small values."""
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
        assert exchange.round_quantity(0.000000001, 8) == 0.0

    def test_round_price_zero_tick_size(self):
        """Test price rounding with very small tick size."""
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
        # Very small tick size for low-cap tokens
        # Rounding to 0.00000001 tick size truncates to 8 decimal places
        assert exchange.round_price(0.000012345, 0.00000001) == pytest.approx(0.00001234)

    def test_round_quantity_large_value(self):
        """Test quantity rounding with large values."""
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
        assert exchange.round_quantity(1000000.123456, 2) == 1000000.12

    def test_symbol_info_min_values(self):
        """Test SymbolInfo with minimum values."""
        from app.exchanges.base import SymbolInfo

        info = SymbolInfo(
            base="SHIB",
            quote="USDT",
            price_precision=8,
            qty_precision=0,
            min_qty=1,
            min_notional=1.0,
            tick_size=0.00000001
        )

        assert info.min_qty == 1
        assert info.qty_precision == 0
        assert info.tick_size == 0.00000001

    def test_exchange_service_round_quantity_edge_cases(self):
        """Test ExchangeService rounding with edge cases."""
        from app.services.exchange_service import ExchangeService

        # Zero quantity
        assert ExchangeService.round_quantity(0, 4) == 0.0
        # Large quantity
        assert ExchangeService.round_quantity(999999.9999, 2) == 1000000.0
        # Negative (should still round correctly if passed)
        assert ExchangeService.round_quantity(-0.123, 2) == -0.12

    def test_exchange_service_round_price_edge_cases(self):
        """Test ExchangeService price rounding with edge cases."""
        from app.services.exchange_service import ExchangeService

        # Very small tick size
        assert ExchangeService.round_price(0.00001234, 0.00000001) == 0.00001234
        # Large tick size
        assert ExchangeService.round_price(50123.45, 100) == 50100.0

    def test_round_price_zero_tick_size(self):
        """
        Verify round_price returns original price when tick_size <= 0.

        Bug prevented: Division by zero or infinite loop with invalid tick_size.
        """
        from app.services.exchange_service import ExchangeService

        price = 50000.123
        # tick_size = 0 should return original price unchanged
        assert ExchangeService.round_price(price, 0) == price
        # tick_size < 0 should return original price unchanged
        assert ExchangeService.round_price(price, -0.01) == price

    @pytest.mark.asyncio
    async def test_validate_order_symbol_not_found(self):
        """
        Verify validate_order handles SymbolNotFoundError gracefully.

        Bug prevented: Unhandled exception crashes validation.
        """
        from app.services.exchange_service import ExchangeService
        from app.exchanges.base import SymbolNotFoundError

        with patch.object(ExchangeService, "get_symbol_info") as mock_info:
            mock_info.side_effect = SymbolNotFoundError("NOTREAL/USDT")

            is_valid, error = await ExchangeService.validate_order(
                "binance", "NOTREAL", "USDT",
                size=0.01,
                price=100.0
            )

        assert is_valid is False
        assert "NOTREAL/USDT" in error

    @pytest.mark.asyncio
    async def test_validate_order_exchange_api_error(self):
        """
        Verify validate_order handles ExchangeAPIError gracefully.

        Bug prevented: API errors crash validation instead of returning failure.
        """
        from app.services.exchange_service import ExchangeService
        from app.exchanges.base import ExchangeAPIError

        with patch.object(ExchangeService, "get_symbol_info") as mock_info:
            mock_info.side_effect = ExchangeAPIError("API rate limit exceeded")

            is_valid, error = await ExchangeService.validate_order(
                "binance", "BTC", "USDT",
                size=0.01,
                price=50000.0
            )

        assert is_valid is False
        assert "rate limit" in error.lower()

    @pytest.mark.asyncio
    async def test_get_symbol_info_uses_cache(self):
        """
        Verify get_symbol_info uses cached data when available and fresh.

        Bug prevented: Unnecessary API calls for symbol info.
        """
        from app.services.exchange_service import ExchangeService
        from app.exchanges.base import SymbolInfo
        from datetime import datetime, timezone

        cached_data = {
            "base": "BTC",
            "quote": "USDT",
            "price_precision": 2,
            "qty_precision": 4,
            "min_qty": 0.0001,
            "min_notional": 10.0,
            "tick_size": 0.01,
            "updated_at": datetime.now(timezone.utc).isoformat()  # Fresh cache
        }

        with patch("app.services.exchange_service.db") as mock_db, \
             patch("app.services.exchange_service.normalize_exchange", return_value="binance"):
            mock_db.get_symbol_rules = AsyncMock(return_value=cached_data)

            info = await ExchangeService.get_symbol_info("binance", "BTC", "USDT")

        # Should return cached data without hitting exchange
        assert info.base == "BTC"
        assert info.quote == "USDT"
        assert info.min_qty == 0.0001

    @pytest.mark.asyncio
    async def test_get_symbol_info_fetches_when_cache_expired(self):
        """
        Verify get_symbol_info fetches from exchange when cache is expired.

        Bug prevented: Using stale trading rules causes validation errors.
        """
        from app.services.exchange_service import ExchangeService
        from app.exchanges.base import SymbolInfo
        from datetime import datetime, timezone, timedelta

        # Cache that's 25 hours old (past 24h expiry)
        old_cache = {
            "base": "BTC",
            "quote": "USDT",
            "price_precision": 2,
            "qty_precision": 4,
            "min_qty": 0.0001,
            "min_notional": 10.0,
            "tick_size": 0.01,
            "updated_at": (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
        }

        fresh_info = SymbolInfo(
            base="BTC",
            quote="USDT",
            price_precision=2,
            qty_precision=5,  # Updated precision
            min_qty=0.00001,  # Updated min_qty
            min_notional=5.0,
            tick_size=0.01
        )

        with patch("app.services.exchange_service.db") as mock_db, \
             patch("app.services.exchange_service.normalize_exchange", return_value="binance"), \
             patch.object(ExchangeService, "get_exchange_adapter") as mock_get_adapter:

            mock_db.get_symbol_rules = AsyncMock(return_value=old_cache)
            mock_db.upsert_symbol_rules = AsyncMock()

            # Mock the adapter
            mock_adapter = MagicMock()
            mock_adapter_instance = MagicMock()
            mock_adapter_instance.get_symbol_info = AsyncMock(return_value=fresh_info)
            mock_adapter.return_value.__aenter__ = AsyncMock(return_value=mock_adapter_instance)
            mock_adapter.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_get_adapter.return_value = mock_adapter

            info = await ExchangeService.get_symbol_info("binance", "BTC", "USDT")

        # Should have fresh data
        assert info.qty_precision == 5
        assert info.min_qty == 0.00001
        # Should have updated cache
        mock_db.upsert_symbol_rules.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_symbol_info_fetches_when_no_cache(self):
        """
        Verify get_symbol_info fetches from exchange when no cache exists.

        Bug prevented: New symbols can't be traded without cache.
        """
        from app.services.exchange_service import ExchangeService
        from app.exchanges.base import SymbolInfo

        fresh_info = SymbolInfo(
            base="NEW",
            quote="USDT",
            price_precision=2,
            qty_precision=4,
            min_qty=0.001,
            min_notional=10.0,
            tick_size=0.01
        )

        with patch("app.services.exchange_service.db") as mock_db, \
             patch("app.services.exchange_service.normalize_exchange", return_value="binance"), \
             patch.object(ExchangeService, "get_exchange_adapter") as mock_get_adapter:

            mock_db.get_symbol_rules = AsyncMock(return_value=None)  # No cache
            mock_db.upsert_symbol_rules = AsyncMock()

            mock_adapter = MagicMock()
            mock_adapter_instance = MagicMock()
            mock_adapter_instance.get_symbol_info = AsyncMock(return_value=fresh_info)
            mock_adapter.return_value.__aenter__ = AsyncMock(return_value=mock_adapter_instance)
            mock_adapter.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_get_adapter.return_value = mock_adapter

            info = await ExchangeService.get_symbol_info("binance", "NEW", "USDT")

        assert info.base == "NEW"
        mock_db.upsert_symbol_rules.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_price_and_info(self):
        """
        Verify get_price_and_info convenience method returns both data.

        Bug prevented: Multiple separate API calls when both needed.
        """
        from app.services.exchange_service import ExchangeService
        from app.exchanges.base import PriceData, SymbolInfo

        mock_price = PriceData(price=50000.0, timestamp=1705762800000)
        mock_info = SymbolInfo(
            base="BTC",
            quote="USDT",
            price_precision=2,
            qty_precision=4,
            min_qty=0.0001,
            min_notional=10.0,
            tick_size=0.01
        )

        with patch.object(ExchangeService, "get_price", new_callable=AsyncMock) as mock_get_price, \
             patch.object(ExchangeService, "get_symbol_info", new_callable=AsyncMock) as mock_get_info:

            mock_get_price.return_value = mock_price
            mock_get_info.return_value = mock_info

            price_data, symbol_info = await ExchangeService.get_price_and_info(
                "binance", "BTCUSDT"
            )

        assert price_data.price == 50000.0
        assert symbol_info.min_qty == 0.0001

    def test_get_exchange_adapter_no_adapter(self):
        """
        Verify error when exchange is known but adapter not registered.

        Bug prevented: Silent failure when adapter missing from EXCHANGES dict.
        """
        from app.services.exchange_service import ExchangeService

        with patch("app.services.exchange_service.normalize_exchange", return_value="valid_exchange"), \
             patch("app.services.exchange_service.EXCHANGES", {"other_exchange": MagicMock()}):

            with pytest.raises(ValueError, match="No adapter"):
                ExchangeService.get_exchange_adapter("valid_exchange")
