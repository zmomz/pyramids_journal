"""
Tests for trade service in app/services/trade_service.py

Tests the core trade processing logic.
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models import TradingViewAlert


def create_test_alert(
    action: str = "buy",
    symbol: str = "BTCUSDT",
    exchange: str = "binance",
    timeframe: str = "1h",
    position_side: str = "long",
    order_id: str = "test_123",
    timestamp: str = "2026-01-20T10:00:00Z",
    contracts: float = 0.01,
    close: float = 50000.0,
    position_qty: float = 0.01
) -> TradingViewAlert:
    """Helper to create TradingViewAlert with all required fields."""
    return TradingViewAlert(
        action=action,
        symbol=symbol,
        exchange=exchange,
        timeframe=timeframe,
        position_side=position_side,
        order_id=order_id,
        timestamp=timestamp,
        contracts=contracts,
        close=close,
        position_qty=position_qty
    )


class TestGenerateGroupId:
    """Tests for generate_group_id helper function."""

    def test_generates_correct_format(self):
        """Test group ID format is correct."""
        from app.services.trade_service import generate_group_id

        group_id = generate_group_id("ETH", "kucoin", "1h", 5)
        assert group_id == "ETH_Kucoin_1h_005"

    def test_sequence_padding(self):
        """Test sequence number is zero-padded."""
        from app.services.trade_service import generate_group_id

        assert generate_group_id("BTC", "binance", "4h", 1) == "BTC_Binance_4h_001"
        assert generate_group_id("BTC", "binance", "4h", 99) == "BTC_Binance_4h_099"
        assert generate_group_id("BTC", "binance", "4h", 100) == "BTC_Binance_4h_100"

    def test_exchange_capitalization(self):
        """Test exchange name is capitalized."""
        from app.services.trade_service import generate_group_id

        assert generate_group_id("SOL", "bybit", "15m", 1) == "SOL_Bybit_15m_001"
        assert generate_group_id("SOL", "BYBIT", "15m", 1) == "SOL_Bybit_15m_001"


class TestTradeResult:
    """Tests for TradeResult dataclass."""

    def test_default_values(self):
        """Test TradeResult has correct default values."""
        from app.services.trade_service import TradeResult

        result = TradeResult(success=True, message="Test")

        assert result.success is True
        assert result.message == "Test"
        assert result.trade_id is None
        assert result.group_id is None
        assert result.price is None
        assert result.error is None
        assert result.entry_data is None

    def test_with_all_values(self):
        """Test TradeResult with all values set."""
        from app.services.trade_service import TradeResult

        result = TradeResult(
            success=True,
            message="Trade created",
            trade_id="trade_123",
            group_id="BTC_Binance_1h_001",
            price=50000.0,
            error=None,
            entry_data=None
        )

        assert result.trade_id == "trade_123"
        assert result.group_id == "BTC_Binance_1h_001"
        assert result.price == 50000.0


class TestProcessSignal:
    """Tests for TradeService.process_signal method."""

    @pytest.mark.asyncio
    async def test_unknown_exchange_returns_error(self):
        """Test that unknown exchange returns error."""
        from app.services.trade_service import TradeService

        alert = create_test_alert(exchange="unknown_exchange")

        with patch("app.services.trade_service.normalize_exchange", return_value=None):
            result, data = await TradeService.process_signal(alert)

        assert result.success is False
        assert result.error == "UNKNOWN_EXCHANGE"
        assert data is None

    @pytest.mark.asyncio
    async def test_invalid_symbol_returns_error(self):
        """Test that invalid symbol returns error."""
        from app.services.trade_service import TradeService

        alert = create_test_alert(symbol="INVALID")

        with patch("app.services.trade_service.normalize_exchange", return_value="binance"), \
             patch("app.services.trade_service.parse_symbol", side_effect=ValueError("Invalid symbol")):
            result, data = await TradeService.process_signal(alert)

        assert result.success is False
        assert result.error == "INVALID_SYMBOL"
        assert data is None


class TestProcessEntry:
    """Tests for TradeService._process_entry method."""

    @pytest.mark.asyncio
    async def test_price_fetch_failure(self):
        """Test entry fails when price fetch fails."""
        from app.services.trade_service import TradeService
        from app.services.symbol_normalizer import ParsedSymbol

        alert = create_test_alert()
        parsed = ParsedSymbol(base="BTC", quote="USDT")

        with patch("app.services.trade_service.exchange_service") as mock_exchange:
            mock_exchange.get_price = AsyncMock(side_effect=Exception("Connection error"))

            result, data = await TradeService._process_entry(
                alert, "binance", parsed, datetime.utcnow()
            )

        assert result.success is False
        assert result.error == "PRICE_FETCH_FAILED"
        assert data is None

    @pytest.mark.asyncio
    async def test_new_trade_creation(self):
        """Test creating a new trade with first pyramid."""
        from app.services.trade_service import TradeService
        from app.services.symbol_normalizer import ParsedSymbol

        alert = create_test_alert()
        parsed = ParsedSymbol(base="BTC", quote="USDT")

        with patch("app.services.trade_service.exchange_service") as mock_exchange, \
             patch("app.services.trade_service.db") as mock_db, \
             patch("app.services.trade_service.exchange_config") as mock_config, \
             patch("app.services.trade_service.settings") as mock_settings:

            # Mock price fetch
            mock_price = MagicMock()
            mock_price.price = 50000.0
            mock_exchange.get_price = AsyncMock(return_value=mock_price)

            # Mock symbol info
            mock_symbol_info = MagicMock()
            mock_symbol_info.qty_precision = 4
            mock_exchange.get_symbol_info = AsyncMock(return_value=mock_symbol_info)
            mock_exchange.round_quantity = MagicMock(return_value=0.02)

            # Mock database
            mock_db.get_open_trade_by_group = AsyncMock(return_value=None)
            mock_db.get_next_group_sequence = AsyncMock(return_value=1)
            mock_db.create_trade_with_group = AsyncMock()
            mock_db.get_pyramid_capital = AsyncMock(return_value=1000.0)
            mock_db.add_pyramid = AsyncMock()
            mock_db.mark_alert_processed = AsyncMock()

            # Mock config
            mock_config.get_fee_rate = MagicMock(return_value=0.001)
            mock_settings.validation_mode = "lenient"

            result, data = await TradeService._process_entry(
                alert, "binance", parsed, datetime.utcnow()
            )

        assert result.success is True
        assert result.group_id == "BTC_Binance_1h_001"
        assert result.price == 50000.0
        assert data is not None
        assert data.pyramid_index == 0

    @pytest.mark.asyncio
    async def test_add_pyramid_to_existing_trade(self):
        """Test adding a pyramid to an existing trade."""
        from app.services.trade_service import TradeService
        from app.services.symbol_normalizer import ParsedSymbol

        alert = create_test_alert(order_id="test_456")
        parsed = ParsedSymbol(base="BTC", quote="USDT")

        with patch("app.services.trade_service.exchange_service") as mock_exchange, \
             patch("app.services.trade_service.db") as mock_db, \
             patch("app.services.trade_service.exchange_config") as mock_config, \
             patch("app.services.trade_service.settings") as mock_settings:

            # Mock price fetch
            mock_price = MagicMock()
            mock_price.price = 49000.0
            mock_exchange.get_price = AsyncMock(return_value=mock_price)

            # Mock symbol info
            mock_symbol_info = MagicMock()
            mock_symbol_info.qty_precision = 4
            mock_exchange.get_symbol_info = AsyncMock(return_value=mock_symbol_info)
            mock_exchange.round_quantity = MagicMock(return_value=0.0204)

            # Mock existing trade
            mock_db.get_open_trade_by_group = AsyncMock(return_value={
                "id": "trade_123",
                "group_id": "BTC_Binance_1h_001"
            })
            mock_db.get_pyramids_for_trade = AsyncMock(return_value=[
                {"id": "pyr_1", "pyramid_index": 0}
            ])
            mock_db.get_pyramid_capital = AsyncMock(return_value=1000.0)
            mock_db.add_pyramid = AsyncMock()
            mock_db.mark_alert_processed = AsyncMock()

            # Mock config
            mock_config.get_fee_rate = MagicMock(return_value=0.001)
            mock_settings.validation_mode = "lenient"

            result, data = await TradeService._process_entry(
                alert, "binance", parsed, datetime.utcnow()
            )

        assert result.success is True
        assert result.trade_id == "trade_123"
        assert data.pyramid_index == 1  # Second pyramid
        assert data.total_pyramids == 2

    @pytest.mark.asyncio
    async def test_validation_failure_strict_mode(self):
        """Test entry fails validation in strict mode."""
        from app.services.trade_service import TradeService
        from app.services.symbol_normalizer import ParsedSymbol

        alert = create_test_alert()
        parsed = ParsedSymbol(base="BTC", quote="USDT")

        with patch("app.services.trade_service.exchange_service") as mock_exchange, \
             patch("app.services.trade_service.db") as mock_db, \
             patch("app.services.trade_service.exchange_config") as mock_config, \
             patch("app.services.trade_service.settings") as mock_settings:

            # Mock price fetch
            mock_price = MagicMock()
            mock_price.price = 50000.0
            mock_exchange.get_price = AsyncMock(return_value=mock_price)

            # Mock symbol info
            mock_symbol_info = MagicMock()
            mock_symbol_info.qty_precision = 4
            mock_exchange.get_symbol_info = AsyncMock(return_value=mock_symbol_info)
            mock_exchange.round_quantity = MagicMock(return_value=0.0001)
            mock_exchange.validate_order = AsyncMock(return_value=(False, "Below min notional"))

            # Mock database
            mock_db.get_open_trade_by_group = AsyncMock(return_value=None)
            mock_db.get_next_group_sequence = AsyncMock(return_value=1)
            mock_db.create_trade_with_group = AsyncMock()
            mock_db.get_pyramid_capital = AsyncMock(return_value=1.0)  # Very small capital

            # Mock config
            mock_config.get_fee_rate = MagicMock(return_value=0.001)
            mock_settings.validation_mode = "strict"

            result, data = await TradeService._process_entry(
                alert, "binance", parsed, datetime.utcnow()
            )

        assert result.success is False
        assert result.error == "VALIDATION_FAILED"


class TestProcessExit:
    """Tests for TradeService._process_exit method."""

    @pytest.mark.asyncio
    async def test_no_open_trade(self):
        """Test exit fails when no open trade exists."""
        from app.services.trade_service import TradeService
        from app.services.symbol_normalizer import ParsedSymbol

        alert = create_test_alert(action="sell", position_side="flat")
        parsed = ParsedSymbol(base="BTC", quote="USDT")

        with patch("app.services.trade_service.db") as mock_db:
            mock_db.get_open_trade_by_group = AsyncMock(return_value=None)

            result, data = await TradeService._process_exit(
                alert, "binance", parsed, datetime.utcnow()
            )

        assert result.success is False
        assert result.error == "NO_OPEN_TRADE"
        assert data is None

    @pytest.mark.asyncio
    async def test_no_pyramids(self):
        """Test exit fails when trade has no pyramids."""
        from app.services.trade_service import TradeService
        from app.services.symbol_normalizer import ParsedSymbol

        alert = create_test_alert(action="sell", position_side="flat")
        parsed = ParsedSymbol(base="BTC", quote="USDT")

        with patch("app.services.trade_service.db") as mock_db:
            mock_db.get_open_trade_by_group = AsyncMock(return_value={
                "id": "trade_123",
                "group_id": "BTC_Binance_1h_001"
            })
            mock_db.get_pyramids_for_trade = AsyncMock(return_value=[])

            result, data = await TradeService._process_exit(
                alert, "binance", parsed, datetime.utcnow()
            )

        assert result.success is False
        assert result.error == "NO_PYRAMIDS"

    @pytest.mark.asyncio
    async def test_successful_exit(self):
        """Test successful exit with PnL calculation."""
        from app.services.trade_service import TradeService
        from app.services.symbol_normalizer import ParsedSymbol

        alert = create_test_alert(action="sell", position_side="flat")
        parsed = ParsedSymbol(base="BTC", quote="USDT")

        with patch("app.services.trade_service.exchange_service") as mock_exchange, \
             patch("app.services.trade_service.db") as mock_db, \
             patch("app.services.trade_service.exchange_config") as mock_config:

            # Mock exit price fetch
            mock_price = MagicMock()
            mock_price.price = 52000.0  # Exit at profit
            mock_exchange.get_price = AsyncMock(return_value=mock_price)

            # Mock database
            mock_db.get_open_trade_by_group = AsyncMock(return_value={
                "id": "trade_123",
                "group_id": "BTC_Binance_1h_001",
                "timeframe": "1h"
            })
            mock_db.get_pyramids_for_trade = AsyncMock(return_value=[
                {
                    "id": "pyr_1",
                    "pyramid_index": 0,
                    "entry_price": 50000.0,
                    "position_size": 0.02,
                    "capital_usdt": 1000.0,
                    "fee_usdt": 1.0,
                    "entry_time": "2026-01-20T10:00:00"
                },
                {
                    "id": "pyr_2",
                    "pyramid_index": 1,
                    "entry_price": 49000.0,
                    "position_size": 0.02,
                    "capital_usdt": 980.0,
                    "fee_usdt": 0.98,
                    "entry_time": "2026-01-20T11:00:00"
                }
            ])
            mock_db.update_pyramid_pnl = AsyncMock()
            mock_db.add_exit = AsyncMock()
            mock_db.close_trade = AsyncMock()
            mock_db.mark_alert_processed = AsyncMock()

            # Mock config
            mock_config.get_fee_rate = MagicMock(return_value=0.001)

            result, data = await TradeService._process_exit(
                alert, "binance", parsed, datetime.utcnow()
            )

        assert result.success is True
        assert result.price == 52000.0
        assert data is not None
        assert len(data.pyramids) == 2
        assert data.net_pnl > 0  # Should be profitable

    @pytest.mark.asyncio
    async def test_exit_price_fetch_failure(self):
        """Test exit fails when price fetch fails."""
        from app.services.trade_service import TradeService
        from app.services.symbol_normalizer import ParsedSymbol

        alert = create_test_alert(action="sell", position_side="flat")
        parsed = ParsedSymbol(base="BTC", quote="USDT")

        with patch("app.services.trade_service.exchange_service") as mock_exchange, \
             patch("app.services.trade_service.db") as mock_db:

            mock_db.get_open_trade_by_group = AsyncMock(return_value={
                "id": "trade_123",
                "group_id": "BTC_Binance_1h_001"
            })
            mock_db.get_pyramids_for_trade = AsyncMock(return_value=[
                {"id": "pyr_1", "pyramid_index": 0}
            ])
            mock_exchange.get_price = AsyncMock(side_effect=Exception("Connection error"))

            result, data = await TradeService._process_exit(
                alert, "binance", parsed, datetime.utcnow()
            )

        assert result.success is False
        assert result.error == "PRICE_FETCH_FAILED"


class TestGetTradeSummary:
    """Tests for TradeService.get_trade_summary method."""

    @pytest.mark.asyncio
    async def test_get_trade_summary(self):
        """Test getting trade summary."""
        from app.services.trade_service import TradeService

        with patch("app.services.trade_service.db") as mock_db:
            mock_db.get_trade_with_pyramids = AsyncMock(return_value={
                "trade": {"id": "trade_123"},
                "pyramids": [{"id": "pyr_1"}],
                "exit": None
            })

            summary = await TradeService.get_trade_summary("trade_123")

        assert summary is not None
        assert summary["trade"]["id"] == "trade_123"

    @pytest.mark.asyncio
    async def test_get_trade_summary_not_found(self):
        """Test getting summary for non-existent trade."""
        from app.services.trade_service import TradeService

        with patch("app.services.trade_service.db") as mock_db:
            mock_db.get_trade_with_pyramids = AsyncMock(return_value=None)

            summary = await TradeService.get_trade_summary("nonexistent")

        assert summary is None
