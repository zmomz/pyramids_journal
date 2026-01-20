"""
Tests for Telegram service in app/services/telegram_service.py

Tests the notification formatting and sending logic.
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytz


class TestTelegramServiceProperties:
    """Tests for TelegramService properties."""

    def test_bot_creates_instance(self):
        """Test that bot property creates Bot instance."""
        from app.services.telegram_service import TelegramService

        service = TelegramService()

        with patch("app.services.telegram_service.settings") as mock_settings, \
             patch("app.services.telegram_service.Bot") as mock_bot_class:

            mock_settings.telegram_bot_token = "test_token"
            mock_bot_class.return_value = MagicMock()

            bot = service.bot

            mock_bot_class.assert_called_once_with(token="test_token")

    def test_bot_raises_without_token(self):
        """Test that bot property raises without token."""
        from app.services.telegram_service import TelegramService

        service = TelegramService()

        with patch("app.services.telegram_service.settings") as mock_settings:
            mock_settings.telegram_bot_token = ""

            with pytest.raises(ValueError, match="not configured"):
                _ = service.bot

    def test_is_enabled_true(self):
        """Test is_enabled returns True when all conditions met."""
        from app.services.telegram_service import TelegramService

        service = TelegramService()

        with patch("app.services.telegram_service.settings") as mock_settings:
            mock_settings.telegram_enabled = True
            mock_settings.telegram_bot_token = "test_token"
            mock_settings.telegram_channel_id = "-1001234567890"

            assert service.is_enabled is True

    def test_is_enabled_false_no_token(self):
        """Test is_enabled returns False without token."""
        from app.services.telegram_service import TelegramService

        service = TelegramService()

        with patch("app.services.telegram_service.settings") as mock_settings:
            mock_settings.telegram_enabled = True
            mock_settings.telegram_bot_token = ""
            mock_settings.telegram_channel_id = "-1001234567890"

            assert service.is_enabled is False

    def test_is_enabled_false_disabled(self):
        """Test is_enabled returns False when disabled."""
        from app.services.telegram_service import TelegramService

        service = TelegramService()

        with patch("app.services.telegram_service.settings") as mock_settings:
            mock_settings.telegram_enabled = False
            mock_settings.telegram_bot_token = "test_token"
            mock_settings.telegram_channel_id = "-1001234567890"

            assert service.is_enabled is False


class TestTelegramServiceFormatters:
    """Tests for TelegramService formatting methods."""

    def test_format_price_large(self):
        """Test formatting large prices."""
        from app.services.telegram_service import TelegramService

        service = TelegramService()

        assert service._format_price(50000.5) == "$50,000.50"
        assert service._format_price(1234.56) == "$1,234.56"

    def test_format_price_medium(self):
        """Test formatting medium prices."""
        from app.services.telegram_service import TelegramService

        service = TelegramService()

        assert service._format_price(15.5678) == "$15.5678"
        assert service._format_price(1.0) == "$1.0000"

    def test_format_price_small(self):
        """Test formatting small prices."""
        from app.services.telegram_service import TelegramService

        service = TelegramService()

        assert service._format_price(0.00012345) == "$0.00012345"

    def test_format_pnl_positive(self):
        """Test formatting positive PnL."""
        from app.services.telegram_service import TelegramService

        service = TelegramService()

        assert service._format_pnl(150.50) == "+$150.50"
        assert service._format_pnl(0) == "+$0.00"

    def test_format_pnl_negative(self):
        """Test formatting negative PnL."""
        from app.services.telegram_service import TelegramService

        service = TelegramService()

        assert service._format_pnl(-50.25) == "-$50.25"

    def test_format_percent_positive(self):
        """Test formatting positive percentages."""
        from app.services.telegram_service import TelegramService

        service = TelegramService()

        assert service._format_percent(5.25) == "+5.25%"
        assert service._format_percent(0) == "+0.00%"

    def test_format_percent_negative(self):
        """Test formatting negative percentages."""
        from app.services.telegram_service import TelegramService

        service = TelegramService()

        assert service._format_percent(-2.15) == "-2.15%"

    def test_format_quantity(self):
        """Test formatting quantities."""
        from app.services.telegram_service import TelegramService

        service = TelegramService()

        assert service._format_quantity(0.02000000) == "0.02"
        assert service._format_quantity(1.5) == "1.5"
        assert service._format_quantity(100) == "100"

    def test_format_quantity_with_commas_large(self):
        """Test formatting large quantities with commas."""
        from app.services.telegram_service import TelegramService

        service = TelegramService()

        assert service._format_quantity_with_commas(10000, "BTC") == "10,000 BTC"

    def test_format_quantity_with_commas_medium(self):
        """Test formatting medium quantities."""
        from app.services.telegram_service import TelegramService

        service = TelegramService()

        assert service._format_quantity_with_commas(5.5, "ETH") == "5.5 ETH"

    def test_format_quantity_with_commas_small(self):
        """Test formatting small quantities."""
        from app.services.telegram_service import TelegramService

        service = TelegramService()

        assert service._format_quantity_with_commas(0.0025, "BTC") == "0.0025 BTC"


class TestTelegramServiceTimeFormatters:
    """Tests for time-related formatting methods."""

    def test_get_local_time(self):
        """Test converting UTC to local time."""
        from app.services.telegram_service import TelegramService

        service = TelegramService()

        with patch("app.services.telegram_service.settings") as mock_settings:
            mock_settings.timezone = "UTC"

            utc_time = datetime(2026, 1, 20, 12, 0, 0, tzinfo=pytz.UTC)
            local_time = service._get_local_time(utc_time)

            assert local_time.hour == 12  # Same as UTC

    def test_format_time(self):
        """Test time formatting."""
        from app.services.telegram_service import TelegramService

        service = TelegramService()

        with patch("app.services.telegram_service.settings") as mock_settings:
            mock_settings.timezone = "UTC"

            utc_time = datetime(2026, 1, 20, 14, 30, 45, tzinfo=pytz.UTC)
            formatted = service._format_time(utc_time)

            assert formatted == "14:30:45"

    def test_format_date(self):
        """Test date formatting."""
        from app.services.telegram_service import TelegramService

        service = TelegramService()

        with patch("app.services.telegram_service.settings") as mock_settings:
            mock_settings.timezone = "UTC"

            utc_time = datetime(2026, 1, 20, 14, 30, 45, tzinfo=pytz.UTC)
            formatted = service._format_date(utc_time)

            assert formatted == "2026-01-20"

    def test_parse_exchange_timestamp_valid(self):
        """Test parsing valid exchange timestamp."""
        from app.services.telegram_service import TelegramService

        service = TelegramService()

        with patch("app.services.telegram_service.settings") as mock_settings:
            mock_settings.timezone = "UTC"

            result = service._parse_exchange_timestamp("2026-01-20T14:30:00Z")
            assert "14:30:00" in result

    def test_parse_exchange_timestamp_invalid(self):
        """Test parsing invalid exchange timestamp."""
        from app.services.telegram_service import TelegramService

        service = TelegramService()

        result = service._parse_exchange_timestamp("invalid")
        assert result == "invalid"

    def test_parse_exchange_timestamp_empty(self):
        """Test parsing empty exchange timestamp."""
        from app.services.telegram_service import TelegramService

        service = TelegramService()

        result = service._parse_exchange_timestamp("")
        assert result == "N/A"


class TestFormatPyramidEntryMessage:
    """Tests for format_pyramid_entry_message method."""

    def test_format_pyramid_entry(self):
        """Test formatting pyramid entry message."""
        from app.services.telegram_service import TelegramService
        from app.models import PyramidEntryData

        service = TelegramService()

        with patch("app.services.telegram_service.settings") as mock_settings:
            mock_settings.timezone = "UTC"

            entry_data = PyramidEntryData(
                group_id="BTC_Binance_1h_001",
                pyramid_index=0,
                exchange="binance",
                base="BTC",
                quote="USDT",
                timeframe="1h",
                entry_price=50000.0,
                position_size=0.02,
                capital_usdt=1000.0,
                exchange_timestamp="2026-01-20T10:00:00Z",
                received_timestamp=datetime.utcnow(),
                total_pyramids=1
            )

            message = service.format_pyramid_entry_message(entry_data)

            assert "Trade Entry" in message
            assert "BTC_Binance_1h_001" in message
            assert "Binance" in message
            assert "BTC/USDT" in message
            assert "50,000" in message


class TestGetSignalsChannelId:
    """Tests for get_signals_channel_id method."""

    @pytest.mark.asyncio
    async def test_from_database(self):
        """Test getting signals channel ID from database."""
        from app.services.telegram_service import TelegramService

        service = TelegramService()

        with patch("app.services.telegram_service.db") as mock_db:
            mock_cursor = MagicMock()
            mock_cursor.fetchone = AsyncMock(return_value={"value": "-1009876543210"})
            mock_db.connection.execute = AsyncMock(return_value=mock_cursor)

            channel_id = await service.get_signals_channel_id()

            assert channel_id == "-1009876543210"

    @pytest.mark.asyncio
    async def test_from_settings_fallback(self):
        """Test falling back to settings when database empty."""
        from app.services.telegram_service import TelegramService

        service = TelegramService()

        with patch("app.services.telegram_service.db") as mock_db, \
             patch("app.services.telegram_service.settings") as mock_settings:

            mock_cursor = MagicMock()
            mock_cursor.fetchone = AsyncMock(return_value=None)
            mock_db.connection.execute = AsyncMock(return_value=mock_cursor)
            mock_settings.telegram_signals_channel_id = "-1001111222333"

            channel_id = await service.get_signals_channel_id()

            assert channel_id == "-1001111222333"

    @pytest.mark.asyncio
    async def test_database_error_fallback(self):
        """Test falling back to settings on database error."""
        from app.services.telegram_service import TelegramService

        service = TelegramService()

        with patch("app.services.telegram_service.db") as mock_db, \
             patch("app.services.telegram_service.settings") as mock_settings:

            mock_db.connection.execute = AsyncMock(side_effect=Exception("DB error"))
            mock_settings.telegram_signals_channel_id = "-1001111222333"

            channel_id = await service.get_signals_channel_id()

            assert channel_id == "-1001111222333"
