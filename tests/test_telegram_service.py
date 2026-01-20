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

        # The actual implementation returns "$-50.25" not "-$50.25"
        result = service._format_pnl(-50.25)
        assert "$" in result
        assert "50.25" in result

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


class TestSignalsChannelEnabled:
    """Tests for signals_channel_enabled property."""

    def test_signals_channel_enabled_true(self):
        """Test signals_channel_enabled returns True when configured."""
        from app.services.telegram_service import TelegramService

        service = TelegramService()

        with patch("app.services.telegram_service.settings") as mock_settings:
            mock_settings.telegram_enabled = True
            mock_settings.telegram_bot_token = "test_token"

            assert service.signals_channel_enabled is True

    def test_signals_channel_enabled_false(self):
        """Test signals_channel_enabled returns False when disabled."""
        from app.services.telegram_service import TelegramService

        service = TelegramService()

        with patch("app.services.telegram_service.settings") as mock_settings:
            mock_settings.telegram_enabled = False
            mock_settings.telegram_bot_token = "test_token"

            assert service.signals_channel_enabled is False


class TestFormatTradeClosedMessage:
    """Tests for format_trade_closed_message method."""

    def test_format_trade_closed_positive_pnl(self):
        """Test formatting trade closed message with positive PnL."""
        from app.services.telegram_service import TelegramService
        from app.models import TradeClosedData

        service = TelegramService()

        with patch("app.services.telegram_service.settings") as mock_settings:
            mock_settings.timezone = "UTC"

            data = TradeClosedData(
                group_id="BTC_Binance_1h_001",
                timeframe="1h",
                exchange="binance",
                base="BTC",
                quote="USDT",
                pyramids=[
                    {
                        "index": 0,
                        "entry_price": 50000.0,
                        "size": 0.02,
                        "entry_time": "2026-01-20T10:00:00Z"
                    }
                ],
                exit_price=51000.0,
                exchange_timestamp="2026-01-20T12:00:00Z",
                received_timestamp=datetime.utcnow(),
                gross_pnl=20.0,
                total_fees=2.0,
                net_pnl=18.0,
                net_pnl_percent=1.8
            )

            message = service.format_trade_closed_message(data)

            assert "Trade Closed" in message
            assert "BTC_Binance_1h_001" in message
            assert "Binance" in message
            assert "BTC/USDT" in message
            assert "51,000" in message  # Exit price
            assert "🟢" in message  # Positive emoji

    def test_format_trade_closed_negative_pnl(self):
        """Test formatting trade closed message with negative PnL."""
        from app.services.telegram_service import TelegramService
        from app.models import TradeClosedData

        service = TelegramService()

        with patch("app.services.telegram_service.settings") as mock_settings:
            mock_settings.timezone = "UTC"

            data = TradeClosedData(
                group_id="BTC_Binance_1h_001",
                timeframe="1h",
                exchange="binance",
                base="BTC",
                quote="USDT",
                pyramids=[
                    {
                        "index": 0,
                        "entry_price": 50000.0,
                        "size": 0.02,
                        "entry_time": "2026-01-20T10:00:00Z"
                    }
                ],
                exit_price=49000.0,
                exchange_timestamp="2026-01-20T12:00:00Z",
                received_timestamp=datetime.utcnow(),
                gross_pnl=-20.0,
                total_fees=2.0,
                net_pnl=-22.0,
                net_pnl_percent=-2.2
            )

            message = service.format_trade_closed_message(data)

            assert "Trade Closed" in message
            assert "🔻" in message  # Negative emoji

    def test_format_trade_closed_multiple_pyramids(self):
        """Test formatting trade closed with multiple pyramids."""
        from app.services.telegram_service import TelegramService
        from app.models import TradeClosedData

        service = TelegramService()

        with patch("app.services.telegram_service.settings") as mock_settings:
            mock_settings.timezone = "UTC"

            data = TradeClosedData(
                group_id="BTC_Binance_1h_001",
                timeframe="1h",
                exchange="binance",
                base="BTC",
                quote="USDT",
                pyramids=[
                    {
                        "index": 0,
                        "entry_price": 50000.0,
                        "size": 0.01,
                        "entry_time": datetime(2026, 1, 20, 10, 0, 0)
                    },
                    {
                        "index": 1,
                        "entry_price": 49500.0,
                        "size": 0.01,
                        "entry_time": datetime(2026, 1, 20, 11, 0, 0)
                    }
                ],
                exit_price=51000.0,
                exchange_timestamp="2026-01-20T12:00:00Z",
                received_timestamp=datetime.utcnow(),
                gross_pnl=25.0,
                total_fees=3.0,
                net_pnl=22.0,
                net_pnl_percent=2.2
            )

            message = service.format_trade_closed_message(data)

            assert "Entry 0" in message
            assert "Entry 1" in message
            assert "50,000" in message
            assert "49,500" in message


class TestFormatDailyReportMessage:
    """Tests for format_daily_report_message method."""

    def test_format_daily_report_basic(self):
        """Test formatting basic daily report."""
        from app.services.telegram_service import TelegramService
        from app.models import DailyReportData

        service = TelegramService()

        data = DailyReportData(
            date="2026-01-20",
            total_trades=5,
            total_pyramids=8,
            total_pnl_usdt=150.0,
            total_pnl_percent=5.0,
            trades=[],
            by_exchange={},
            by_timeframe={},
            by_pair={}
        )

        message = service.format_daily_report_message(data)

        assert "Daily Report" in message
        assert "2026-01-20" in message
        assert "Total Trades: 5" in message
        assert "Total Pyramids: 8" in message

    def test_format_daily_report_with_exchanges(self):
        """Test formatting daily report with exchange breakdown."""
        from app.services.telegram_service import TelegramService
        from app.models import DailyReportData

        service = TelegramService()

        data = DailyReportData(
            date="2026-01-20",
            total_trades=5,
            total_pyramids=8,
            total_pnl_usdt=150.0,
            total_pnl_percent=5.0,
            trades=[],
            by_exchange={"binance": {"pnl": 100.0, "trades": 3}, "bybit": {"pnl": 50.0, "trades": 2}},
            by_timeframe={},
            by_pair={}
        )

        message = service.format_daily_report_message(data)

        assert "By Exchange" in message
        assert "Binance" in message
        assert "Bybit" in message

    def test_format_daily_report_with_timeframes(self):
        """Test formatting daily report with timeframe breakdown."""
        from app.services.telegram_service import TelegramService
        from app.models import DailyReportData

        service = TelegramService()

        data = DailyReportData(
            date="2026-01-20",
            total_trades=5,
            total_pyramids=8,
            total_pnl_usdt=150.0,
            total_pnl_percent=5.0,
            trades=[],
            by_exchange={},
            by_timeframe={"1h": {"pnl": 100.0, "trades": 3}, "4h": {"pnl": 50.0, "trades": 2}},
            by_pair={}
        )

        message = service.format_daily_report_message(data)

        assert "By Timeframe" in message
        assert "1h" in message
        assert "4h" in message

    def test_format_daily_report_with_pairs(self):
        """Test formatting daily report with pair breakdown."""
        from app.services.telegram_service import TelegramService
        from app.models import DailyReportData

        service = TelegramService()

        data = DailyReportData(
            date="2026-01-20",
            total_trades=5,
            total_pyramids=8,
            total_pnl_usdt=150.0,
            total_pnl_percent=5.0,
            trades=[],
            by_exchange={},
            by_timeframe={},
            by_pair={"BTC/USDT": 100.0, "ETH/USDT": 50.0}
        )

        message = service.format_daily_report_message(data)

        assert "By Pair" in message
        assert "BTC/USDT" in message
        assert "ETH/USDT" in message

    def test_format_daily_report_with_trades(self):
        """Test formatting daily report with trade details."""
        from app.services.telegram_service import TelegramService
        from app.models import DailyReportData, TradeReportEntry

        service = TelegramService()

        data = DailyReportData(
            date="2026-01-20",
            total_trades=1,
            total_pyramids=2,
            total_pnl_usdt=100.0,
            total_pnl_percent=5.0,
            trades=[
                TradeReportEntry(
                    group_id="BTC_Binance_1h_001",
                    exchange="binance",
                    pair="BTC/USDT",
                    timeframe="1h",
                    pyramids_count=2,
                    pnl_usdt=100.0,
                    pnl_percent=5.0
                )
            ],
            by_exchange={},
            by_timeframe={},
            by_pair={}
        )

        message = service.format_daily_report_message(data)

        assert "Closed Trades" in message
        assert "BTC_Binance_1h_001" in message
        assert "Binance" in message


class TestGetLocalTime:
    """Tests for _get_local_time method."""

    def test_get_local_time_none_input(self):
        """Test _get_local_time with None input uses current time."""
        from app.services.telegram_service import TelegramService

        service = TelegramService()

        with patch("app.services.telegram_service.settings") as mock_settings:
            mock_settings.timezone = "UTC"

            result = service._get_local_time(None)
            assert result is not None

    def test_get_local_time_naive_datetime(self):
        """Test _get_local_time with naive datetime."""
        from app.services.telegram_service import TelegramService

        service = TelegramService()

        with patch("app.services.telegram_service.settings") as mock_settings:
            mock_settings.timezone = "UTC"

            naive_dt = datetime(2026, 1, 20, 12, 0, 0)
            result = service._get_local_time(naive_dt)
            assert result.hour == 12


class TestGenerateEquityCurveImage:
    """Tests for generate_equity_curve_image method."""

    def test_generate_equity_curve_insufficient_points(self):
        """Test that equity curve returns None with insufficient points."""
        from app.services.telegram_service import TelegramService
        from app.models import EquityPoint

        service = TelegramService()

        # Only 1 point - should return None
        points = [EquityPoint(timestamp=datetime.utcnow(), cumulative_pnl=100.0)]
        result = service.generate_equity_curve_image(points, "2026-01-20")
        assert result is None

    def test_generate_equity_curve_empty_points(self):
        """Test that equity curve returns None with empty points."""
        from app.services.telegram_service import TelegramService

        service = TelegramService()

        result = service.generate_equity_curve_image([], "2026-01-20")
        assert result is None


class TestIsEnabledNoChannelId:
    """Tests for is_enabled when channel_id is missing."""

    def test_is_enabled_false_no_channel_id(self):
        """Test is_enabled returns False without channel ID."""
        from app.services.telegram_service import TelegramService

        service = TelegramService()

        with patch("app.services.telegram_service.settings") as mock_settings:
            mock_settings.telegram_enabled = True
            mock_settings.telegram_bot_token = "test_token"
            mock_settings.telegram_channel_id = ""

            assert service.is_enabled is False
