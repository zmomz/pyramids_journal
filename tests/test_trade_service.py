"""
Tests for trade service in app/services/trade_service.py

Tests the core trade processing logic.
"""

from datetime import datetime, UTC
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
                alert, "binance", parsed, datetime.now(UTC)
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
                alert, "binance", parsed, datetime.now(UTC)
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
                alert, "binance", parsed, datetime.now(UTC)
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
                alert, "binance", parsed, datetime.now(UTC)
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
                alert, "binance", parsed, datetime.now(UTC)
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
                alert, "binance", parsed, datetime.now(UTC)
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
                alert, "binance", parsed, datetime.now(UTC)
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
                alert, "binance", parsed, datetime.now(UTC)
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


class TestGenerateGroupIdEdgeCases:
    """Edge case tests for generate_group_id function."""

    def test_special_characters_in_symbol(self):
        """Test group ID with special symbol names."""
        from app.services.trade_service import generate_group_id

        # Some exchanges have unusual symbol formats
        group_id = generate_group_id("1000SHIB", "binance", "1h", 1)
        assert group_id == "1000SHIB_Binance_1h_001"

    def test_long_sequence_number(self):
        """Test group ID with sequence number > 999."""
        from app.services.trade_service import generate_group_id

        group_id = generate_group_id("BTC", "binance", "1h", 1000)
        assert group_id == "BTC_Binance_1h_1000"

    def test_lowercase_exchange(self):
        """Test exchange name normalization."""
        from app.services.trade_service import generate_group_id

        group_id = generate_group_id("BTC", "BINANCE", "1h", 1)
        assert "_Binance_" in group_id


class TestTradeResultEdgeCases:
    """Edge case tests for TradeResult dataclass."""

    def test_failed_result_with_error_data(self):
        """Test TradeResult for failure with error details."""
        from app.services.trade_service import TradeResult

        result = TradeResult(
            success=False,
            message="Trade failed",
            error="PRICE_FETCH_FAILED",
            trade_id=None,
            group_id=None,
            price=None
        )

        assert result.success is False
        assert result.error == "PRICE_FETCH_FAILED"
        assert result.trade_id is None

    def test_result_with_entry_data(self):
        """Test TradeResult with entry data attached."""
        from app.services.trade_service import TradeResult

        mock_entry_data = {"pyramid_index": 0, "price": 50000.0}

        result = TradeResult(
            success=True,
            message="Trade created",
            trade_id="trade_123",
            entry_data=mock_entry_data
        )

        assert result.entry_data == mock_entry_data


class TestProcessEntryEdgeCases:
    """Edge case tests for entry processing."""

    @pytest.mark.asyncio
    async def test_zero_contracts_alert(self):
        """Test entry with zero contracts."""
        from app.services.trade_service import TradeService
        from app.services.symbol_normalizer import ParsedSymbol

        alert = create_test_alert(contracts=0)
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
            mock_exchange.round_quantity = MagicMock(return_value=0)

            # Mock database - all async methods need AsyncMock
            mock_db.get_open_trade_by_group = AsyncMock(return_value=None)
            mock_db.get_next_group_sequence = AsyncMock(return_value=1)
            mock_db.get_pyramid_capital = AsyncMock(return_value=0)
            mock_db.create_trade_with_group = AsyncMock()
            mock_db.add_pyramid = AsyncMock()
            mock_db.mark_alert_processed = AsyncMock()

            # Mock config
            mock_config.get_fee_rate = MagicMock(return_value=0.001)
            mock_settings.validation_mode = "lenient"

            result, data = await TradeService._process_entry(
                alert, "binance", parsed, datetime.now(UTC)
            )

        # Should handle zero contracts gracefully (either fail or create with 0)
        assert result is not None


class TestProcessExitEdgeCases:
    """Edge case tests for exit processing."""

    @pytest.mark.asyncio
    async def test_exit_with_single_pyramid(self):
        """Test exit with only one pyramid entry."""
        from app.services.trade_service import TradeService
        from app.services.symbol_normalizer import ParsedSymbol

        alert = create_test_alert(action="sell", position_side="flat")
        parsed = ParsedSymbol(base="BTC", quote="USDT")

        with patch("app.services.trade_service.exchange_service") as mock_exchange, \
             patch("app.services.trade_service.db") as mock_db, \
             patch("app.services.trade_service.exchange_config") as mock_config:

            # Mock exit price fetch
            mock_price = MagicMock()
            mock_price.price = 48000.0  # Exit at loss
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
                }
            ])
            mock_db.update_pyramid_pnl = AsyncMock()
            mock_db.add_exit = AsyncMock()
            mock_db.close_trade = AsyncMock()
            mock_db.mark_alert_processed = AsyncMock()

            # Mock config
            mock_config.get_fee_rate = MagicMock(return_value=0.001)

            result, data = await TradeService._process_exit(
                alert, "binance", parsed, datetime.now(UTC)
            )

        assert result.success is True
        assert data.net_pnl < 0  # Should be at loss

    @pytest.mark.asyncio
    async def test_exit_with_many_pyramids(self):
        """Test exit with many pyramid entries."""
        from app.services.trade_service import TradeService
        from app.services.symbol_normalizer import ParsedSymbol

        alert = create_test_alert(action="sell", position_side="flat")
        parsed = ParsedSymbol(base="BTC", quote="USDT")

        # Create 5 pyramid entries
        pyramids = [
            {
                "id": f"pyr_{i}",
                "pyramid_index": i,
                "entry_price": 50000.0 - (i * 500),  # Decreasing entry prices
                "position_size": 0.02,
                "capital_usdt": 1000.0,
                "fee_usdt": 1.0,
                "entry_time": f"2026-01-20T{10+i}:00:00"
            }
            for i in range(5)
        ]

        with patch("app.services.trade_service.exchange_service") as mock_exchange, \
             patch("app.services.trade_service.db") as mock_db, \
             patch("app.services.trade_service.exchange_config") as mock_config:

            # Mock exit price fetch - above all entries
            mock_price = MagicMock()
            mock_price.price = 52000.0
            mock_exchange.get_price = AsyncMock(return_value=mock_price)

            # Mock database
            mock_db.get_open_trade_by_group = AsyncMock(return_value={
                "id": "trade_123",
                "group_id": "BTC_Binance_1h_001",
                "timeframe": "1h"
            })
            mock_db.get_pyramids_for_trade = AsyncMock(return_value=pyramids)
            mock_db.update_pyramid_pnl = AsyncMock()
            mock_db.add_exit = AsyncMock()
            mock_db.close_trade = AsyncMock()
            mock_db.mark_alert_processed = AsyncMock()

            # Mock config
            mock_config.get_fee_rate = MagicMock(return_value=0.001)

            result, data = await TradeService._process_exit(
                alert, "binance", parsed, datetime.now(UTC)
            )

        assert result.success is True
        assert len(data.pyramids) == 5
        assert data.net_pnl > 0  # Should be profitable


class TestPnLCalculationAccuracy:
    """Tests to verify PnL calculations are mathematically correct."""

    @pytest.mark.asyncio
    async def test_pnl_calculation_single_pyramid_profit(self):
        """Test exact PnL calculation for a profitable single pyramid trade."""
        from app.services.trade_service import TradeService
        from app.services.symbol_normalizer import ParsedSymbol

        alert = create_test_alert(action="sell", position_side="flat")
        parsed = ParsedSymbol(base="BTC", quote="USDT")

        # Setup: Entry at $50,000, position size 0.02 BTC, capital $1000
        # Exit at $52,000 (4% profit)
        # Expected gross PnL: (52000 - 50000) * 0.02 = $40
        # Entry fee: 0.1% of $1000 = $1.00
        # Exit fee: 0.1% of (52000 * 0.02) = 0.1% of $1040 = $1.04
        # Expected net PnL: $40 - $1.00 - $1.04 = $37.96

        with patch("app.services.trade_service.exchange_service") as mock_exchange, \
             patch("app.services.trade_service.db") as mock_db, \
             patch("app.services.trade_service.exchange_config") as mock_config:

            mock_price = MagicMock()
            mock_price.price = 52000.0
            mock_exchange.get_price = AsyncMock(return_value=mock_price)

            mock_db.get_open_trade_by_group = AsyncMock(return_value={
                "id": "trade_pnl_test",
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
                    "fee_usdt": 1.0,  # Entry fee
                    "entry_time": "2026-01-20T10:00:00"
                }
            ])
            mock_db.update_pyramid_pnl = AsyncMock()
            mock_db.add_exit = AsyncMock()
            mock_db.close_trade = AsyncMock()
            mock_db.mark_alert_processed = AsyncMock()
            mock_config.get_fee_rate = MagicMock(return_value=0.001)  # 0.1%

            result, data = await TradeService._process_exit(
                alert, "binance", parsed, datetime.now(UTC)
            )

        assert result.success is True
        # Verify gross PnL calculation
        expected_gross = (52000.0 - 50000.0) * 0.02
        assert abs(data.gross_pnl - expected_gross) < 0.01, f"Gross PnL: {data.gross_pnl} != {expected_gross}"

        # Verify exit fee calculation (0.1% of exit value)
        exit_value = 52000.0 * 0.02
        expected_exit_fee = exit_value * 0.001
        # Total fees = entry fee + exit fee
        expected_total_fees = 1.0 + expected_exit_fee
        assert abs(data.total_fees - expected_total_fees) < 0.01, f"Fees: {data.total_fees} != {expected_total_fees}"

        # Verify net PnL
        expected_net = expected_gross - expected_total_fees
        assert abs(data.net_pnl - expected_net) < 0.01, f"Net PnL: {data.net_pnl} != {expected_net}"

    @pytest.mark.asyncio
    async def test_pnl_calculation_single_pyramid_loss(self):
        """Test exact PnL calculation for a losing single pyramid trade."""
        from app.services.trade_service import TradeService
        from app.services.symbol_normalizer import ParsedSymbol

        alert = create_test_alert(action="sell", position_side="flat")
        parsed = ParsedSymbol(base="BTC", quote="USDT")

        # Setup: Entry at $50,000, position size 0.02 BTC
        # Exit at $48,000 (4% loss)
        # Expected gross PnL: (48000 - 50000) * 0.02 = -$40
        # Entry fee: $1.00
        # Exit fee: 0.1% of (48000 * 0.02) = $0.96
        # Expected net PnL: -$40 - $1.00 - $0.96 = -$41.96

        with patch("app.services.trade_service.exchange_service") as mock_exchange, \
             patch("app.services.trade_service.db") as mock_db, \
             patch("app.services.trade_service.exchange_config") as mock_config:

            mock_price = MagicMock()
            mock_price.price = 48000.0
            mock_exchange.get_price = AsyncMock(return_value=mock_price)

            mock_db.get_open_trade_by_group = AsyncMock(return_value={
                "id": "trade_loss_test",
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
                }
            ])
            mock_db.update_pyramid_pnl = AsyncMock()
            mock_db.add_exit = AsyncMock()
            mock_db.close_trade = AsyncMock()
            mock_db.mark_alert_processed = AsyncMock()
            mock_config.get_fee_rate = MagicMock(return_value=0.001)

            result, data = await TradeService._process_exit(
                alert, "binance", parsed, datetime.now(UTC)
            )

        assert result.success is True
        # Verify loss calculation
        expected_gross = (48000.0 - 50000.0) * 0.02  # -40
        assert abs(data.gross_pnl - expected_gross) < 0.01
        assert data.gross_pnl < 0, "Gross PnL should be negative for a loss"
        assert data.net_pnl < data.gross_pnl, "Net PnL should be worse than gross due to fees"

    @pytest.mark.asyncio
    async def test_pnl_calculation_multiple_pyramids_averaged(self):
        """Test PnL calculation with multiple pyramid entries at different prices."""
        from app.services.trade_service import TradeService
        from app.services.symbol_normalizer import ParsedSymbol

        alert = create_test_alert(action="sell", position_side="flat")
        parsed = ParsedSymbol(base="BTC", quote="USDT")

        # Setup: Two pyramids
        # Pyramid 1: Entry $50,000 @ 0.02 BTC, fee $1.00
        # Pyramid 2: Entry $49,000 @ 0.02 BTC, fee $0.98
        # Exit at $51,000
        # Pyramid 1 gross: (51000 - 50000) * 0.02 = $20
        # Pyramid 2 gross: (51000 - 49000) * 0.02 = $40
        # Total gross: $60
        # Exit fees: 0.1% of (51000 * 0.04) = $2.04
        # Total fees: $1.00 + $0.98 + $2.04 = $4.02
        # Net PnL: $60 - $4.02 = $55.98

        with patch("app.services.trade_service.exchange_service") as mock_exchange, \
             patch("app.services.trade_service.db") as mock_db, \
             patch("app.services.trade_service.exchange_config") as mock_config:

            mock_price = MagicMock()
            mock_price.price = 51000.0
            mock_exchange.get_price = AsyncMock(return_value=mock_price)

            mock_db.get_open_trade_by_group = AsyncMock(return_value={
                "id": "trade_multi",
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
            mock_config.get_fee_rate = MagicMock(return_value=0.001)

            result, data = await TradeService._process_exit(
                alert, "binance", parsed, datetime.now(UTC)
            )

        assert result.success is True
        # Verify individual pyramid PnLs
        assert len(data.pyramids) == 2

        # Verify total gross PnL
        pyr1_gross = (51000.0 - 50000.0) * 0.02  # $20
        pyr2_gross = (51000.0 - 49000.0) * 0.02  # $40
        expected_gross = pyr1_gross + pyr2_gross  # $60
        assert abs(data.gross_pnl - expected_gross) < 0.01

        # Verify net is less than gross due to fees
        assert data.net_pnl < data.gross_pnl

    @pytest.mark.asyncio
    async def test_pnl_percent_calculation(self):
        """Test that PnL percentage is calculated correctly relative to capital."""
        from app.services.trade_service import TradeService
        from app.services.symbol_normalizer import ParsedSymbol

        alert = create_test_alert(action="sell", position_side="flat")
        parsed = ParsedSymbol(base="BTC", quote="USDT")

        # Setup: Entry at $50,000, capital $1000
        # Exit at $55,000 (10% price increase)
        # Gross PnL: (55000 - 50000) * 0.02 = $100 (10% of capital)

        with patch("app.services.trade_service.exchange_service") as mock_exchange, \
             patch("app.services.trade_service.db") as mock_db, \
             patch("app.services.trade_service.exchange_config") as mock_config:

            mock_price = MagicMock()
            mock_price.price = 55000.0
            mock_exchange.get_price = AsyncMock(return_value=mock_price)

            mock_db.get_open_trade_by_group = AsyncMock(return_value={
                "id": "trade_pct",
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
                }
            ])
            mock_db.update_pyramid_pnl = AsyncMock()
            mock_db.add_exit = AsyncMock()
            mock_db.close_trade = AsyncMock()
            mock_db.mark_alert_processed = AsyncMock()
            mock_config.get_fee_rate = MagicMock(return_value=0.001)

            result, data = await TradeService._process_exit(
                alert, "binance", parsed, datetime.now(UTC)
            )

        assert result.success is True
        # Gross should be 10% of capital
        assert abs(data.gross_pnl - 100.0) < 0.01
        # Net percent should be close to 10% but slightly less due to fees
        assert data.net_pnl_percent > 9.0  # Should be around 9.8%
        assert data.net_pnl_percent < 10.0  # Less than gross due to fees


class TestBoundaryConditions:
    """Tests for edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_very_small_position_size(self):
        """Test handling of very small position sizes."""
        from app.services.trade_service import TradeService
        from app.services.symbol_normalizer import ParsedSymbol

        alert = create_test_alert(action="sell", position_side="flat")
        parsed = ParsedSymbol(base="BTC", quote="USDT")

        with patch("app.services.trade_service.exchange_service") as mock_exchange, \
             patch("app.services.trade_service.db") as mock_db, \
             patch("app.services.trade_service.exchange_config") as mock_config:

            mock_price = MagicMock()
            mock_price.price = 50000.0
            mock_exchange.get_price = AsyncMock(return_value=mock_price)

            mock_db.get_open_trade_by_group = AsyncMock(return_value={
                "id": "trade_small",
                "group_id": "BTC_Binance_1h_001",
                "timeframe": "1h"
            })
            # Very small position - 0.00001 BTC = $0.50 at $50k
            mock_db.get_pyramids_for_trade = AsyncMock(return_value=[
                {
                    "id": "pyr_1",
                    "pyramid_index": 0,
                    "entry_price": 49000.0,
                    "position_size": 0.00001,
                    "capital_usdt": 0.49,
                    "fee_usdt": 0.0005,
                    "entry_time": "2026-01-20T10:00:00"
                }
            ])
            mock_db.update_pyramid_pnl = AsyncMock()
            mock_db.add_exit = AsyncMock()
            mock_db.close_trade = AsyncMock()
            mock_db.mark_alert_processed = AsyncMock()
            mock_config.get_fee_rate = MagicMock(return_value=0.001)

            result, data = await TradeService._process_exit(
                alert, "binance", parsed, datetime.now(UTC)
            )

        assert result.success is True
        # Should still calculate correctly even with tiny amounts
        expected_gross = (50000.0 - 49000.0) * 0.00001  # $0.01
        assert abs(data.gross_pnl - expected_gross) < 0.001

    @pytest.mark.asyncio
    async def test_breakeven_trade(self):
        """Test handling of breakeven trade (exit = entry)."""
        from app.services.trade_service import TradeService
        from app.services.symbol_normalizer import ParsedSymbol

        alert = create_test_alert(action="sell", position_side="flat")
        parsed = ParsedSymbol(base="BTC", quote="USDT")

        with patch("app.services.trade_service.exchange_service") as mock_exchange, \
             patch("app.services.trade_service.db") as mock_db, \
             patch("app.services.trade_service.exchange_config") as mock_config:

            mock_price = MagicMock()
            mock_price.price = 50000.0  # Same as entry
            mock_exchange.get_price = AsyncMock(return_value=mock_price)

            mock_db.get_open_trade_by_group = AsyncMock(return_value={
                "id": "trade_breakeven",
                "group_id": "BTC_Binance_1h_001",
                "timeframe": "1h"
            })
            mock_db.get_pyramids_for_trade = AsyncMock(return_value=[
                {
                    "id": "pyr_1",
                    "pyramid_index": 0,
                    "entry_price": 50000.0,  # Same as exit
                    "position_size": 0.02,
                    "capital_usdt": 1000.0,
                    "fee_usdt": 1.0,
                    "entry_time": "2026-01-20T10:00:00"
                }
            ])
            mock_db.update_pyramid_pnl = AsyncMock()
            mock_db.add_exit = AsyncMock()
            mock_db.close_trade = AsyncMock()
            mock_db.mark_alert_processed = AsyncMock()
            mock_config.get_fee_rate = MagicMock(return_value=0.001)

            result, data = await TradeService._process_exit(
                alert, "binance", parsed, datetime.now(UTC)
            )

        assert result.success is True
        # Gross PnL should be exactly 0
        assert abs(data.gross_pnl) < 0.01
        # Net PnL should be negative due to fees
        assert data.net_pnl < 0, "Breakeven trade should be net negative due to fees"

    @pytest.mark.asyncio
    async def test_large_price_movement(self):
        """Test handling of large price movements (e.g., 100% gain)."""
        from app.services.trade_service import TradeService
        from app.services.symbol_normalizer import ParsedSymbol

        alert = create_test_alert(action="sell", position_side="flat")
        parsed = ParsedSymbol(base="BTC", quote="USDT")

        with patch("app.services.trade_service.exchange_service") as mock_exchange, \
             patch("app.services.trade_service.db") as mock_db, \
             patch("app.services.trade_service.exchange_config") as mock_config:

            mock_price = MagicMock()
            mock_price.price = 100000.0  # 100% gain from entry
            mock_exchange.get_price = AsyncMock(return_value=mock_price)

            mock_db.get_open_trade_by_group = AsyncMock(return_value={
                "id": "trade_moon",
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
                }
            ])
            mock_db.update_pyramid_pnl = AsyncMock()
            mock_db.add_exit = AsyncMock()
            mock_db.close_trade = AsyncMock()
            mock_db.mark_alert_processed = AsyncMock()
            mock_config.get_fee_rate = MagicMock(return_value=0.001)

            result, data = await TradeService._process_exit(
                alert, "binance", parsed, datetime.now(UTC)
            )

        assert result.success is True
        # 100% price gain means gross PnL = capital
        expected_gross = (100000.0 - 50000.0) * 0.02  # $1000
        assert abs(data.gross_pnl - expected_gross) < 0.01
        assert data.gross_pnl == 1000.0  # Should equal original capital

    @pytest.mark.asyncio
    async def test_zero_fee_rate(self):
        """Test handling when fee rate is zero."""
        from app.services.trade_service import TradeService
        from app.services.symbol_normalizer import ParsedSymbol

        alert = create_test_alert(action="sell", position_side="flat")
        parsed = ParsedSymbol(base="BTC", quote="USDT")

        with patch("app.services.trade_service.exchange_service") as mock_exchange, \
             patch("app.services.trade_service.db") as mock_db, \
             patch("app.services.trade_service.exchange_config") as mock_config:

            mock_price = MagicMock()
            mock_price.price = 52000.0
            mock_exchange.get_price = AsyncMock(return_value=mock_price)

            mock_db.get_open_trade_by_group = AsyncMock(return_value={
                "id": "trade_nofee",
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
                    "fee_usdt": 0.0,  # No entry fee
                    "entry_time": "2026-01-20T10:00:00"
                }
            ])
            mock_db.update_pyramid_pnl = AsyncMock()
            mock_db.add_exit = AsyncMock()
            mock_db.close_trade = AsyncMock()
            mock_db.mark_alert_processed = AsyncMock()
            mock_config.get_fee_rate = MagicMock(return_value=0.0)  # No fee

            result, data = await TradeService._process_exit(
                alert, "binance", parsed, datetime.now(UTC)
            )

        assert result.success is True
        # With no fees, net should equal gross
        assert abs(data.gross_pnl - data.net_pnl) < 0.01
