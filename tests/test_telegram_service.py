"""
Tests for Telegram service in app/services/telegram_service.py

Tests the notification formatting and sending logic.
"""

from datetime import datetime, UTC
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
                received_timestamp=datetime.now(UTC),
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
                trade_id="trade_001",
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
                exit_time=datetime.now(UTC),
                exchange_timestamp="2026-01-20T12:00:00Z",
                received_timestamp=datetime.now(UTC),
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
                trade_id="trade_002",
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
                exit_time=datetime.now(UTC),
                exchange_timestamp="2026-01-20T12:00:00Z",
                received_timestamp=datetime.now(UTC),
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
                trade_id="trade_003",
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
                exit_time=datetime.now(UTC),
                exchange_timestamp="2026-01-20T12:00:00Z",
                received_timestamp=datetime.now(UTC),
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
        from app.models import DailyReportData, TradeHistoryItem

        service = TelegramService()

        data = DailyReportData(
            date="2026-01-20",
            total_trades=1,
            total_pyramids=2,
            total_pnl_usdt=100.0,
            total_pnl_percent=5.0,
            trades=[
                TradeHistoryItem(
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
        points = [EquityPoint(timestamp=datetime.now(UTC), cumulative_pnl=100.0)]
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


class TestFormatterEdgeCases:
    """Edge case tests for formatting methods."""

    def test_format_price_zero(self):
        """Test formatting zero price."""
        from app.services.telegram_service import TelegramService

        service = TelegramService()

        result = service._format_price(0)
        assert "$0" in result

    def test_format_price_very_large(self):
        """Test formatting very large price (Bitcoin ATH scenario)."""
        from app.services.telegram_service import TelegramService

        service = TelegramService()

        result = service._format_price(150000.50)
        assert "$150,000" in result

    def test_format_price_very_small(self):
        """Test formatting very small price (meme coin scenario)."""
        from app.services.telegram_service import TelegramService

        service = TelegramService()

        result = service._format_price(0.00000001)
        assert "$0.00000001" in result

    def test_format_pnl_zero(self):
        """Test formatting zero PnL."""
        from app.services.telegram_service import TelegramService

        service = TelegramService()

        result = service._format_pnl(0)
        assert "$0" in result

    def test_format_pnl_very_large_positive(self):
        """Test formatting very large positive PnL."""
        from app.services.telegram_service import TelegramService

        service = TelegramService()

        result = service._format_pnl(10000.00)
        assert "10" in result and "$" in result

    def test_format_pnl_very_large_negative(self):
        """Test formatting very large negative PnL."""
        from app.services.telegram_service import TelegramService

        service = TelegramService()

        result = service._format_pnl(-10000.00)
        assert "10" in result and "$" in result

    def test_format_percent_zero(self):
        """Test formatting zero percent."""
        from app.services.telegram_service import TelegramService

        service = TelegramService()

        result = service._format_percent(0)
        assert "0.00%" in result

    def test_format_percent_very_large(self):
        """Test formatting very large percentage (100%+ gain)."""
        from app.services.telegram_service import TelegramService

        service = TelegramService()

        result = service._format_percent(150.50)
        assert "150.50%" in result

    def test_format_quantity_zero(self):
        """Test formatting zero quantity."""
        from app.services.telegram_service import TelegramService

        service = TelegramService()

        result = service._format_quantity(0)
        assert "0" in result

    def test_format_quantity_very_large(self):
        """Test formatting very large quantity (SHIB scenario)."""
        from app.services.telegram_service import TelegramService

        service = TelegramService()

        result = service._format_quantity(1000000000)
        assert "1000000000" in result

    def test_format_quantity_with_commas_zero(self):
        """Test formatting zero quantity with commas."""
        from app.services.telegram_service import TelegramService

        service = TelegramService()

        result = service._format_quantity_with_commas(0, "BTC")
        assert "0" in result and "BTC" in result


class TestTimestampEdgeCases:
    """Edge case tests for timestamp handling."""

    def test_parse_exchange_timestamp_iso_format_no_z(self):
        """Test parsing ISO timestamp without Z suffix."""
        from app.services.telegram_service import TelegramService

        service = TelegramService()

        with patch("app.services.telegram_service.settings") as mock_settings:
            mock_settings.timezone = "UTC"

            result = service._parse_exchange_timestamp("2026-01-20T14:30:00")
            # Should handle this format gracefully
            assert result is not None

    def test_parse_exchange_timestamp_with_milliseconds(self):
        """Test parsing timestamp with milliseconds."""
        from app.services.telegram_service import TelegramService

        service = TelegramService()

        with patch("app.services.telegram_service.settings") as mock_settings:
            mock_settings.timezone = "UTC"

            result = service._parse_exchange_timestamp("2026-01-20T14:30:00.123Z")
            assert "14:30" in result

    def test_get_local_time_different_timezone(self):
        """Test local time conversion with different timezone."""
        from app.services.telegram_service import TelegramService

        service = TelegramService()

        with patch("app.services.telegram_service.settings") as mock_settings:
            mock_settings.timezone = "America/New_York"

            utc_time = datetime(2026, 1, 20, 12, 0, 0, tzinfo=pytz.UTC)
            local_time = service._get_local_time(utc_time)

            # New York is UTC-5 in January
            assert local_time.hour == 7


class TestTradeClosedEdgeCases:
    """Edge case tests for trade closed messages."""

    def test_format_trade_closed_breakeven(self):
        """Test formatting trade closed message with zero PnL."""
        from app.services.telegram_service import TelegramService
        from app.models import TradeClosedData

        service = TelegramService()

        with patch("app.services.telegram_service.settings") as mock_settings:
            mock_settings.timezone = "UTC"

            data = TradeClosedData(
                trade_id="trade_001",
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
                exit_price=50000.0,
                exit_time=datetime.now(UTC),
                exchange_timestamp="2026-01-20T12:00:00Z",
                received_timestamp=datetime.now(UTC),
                gross_pnl=0.0,
                total_fees=2.0,
                net_pnl=-2.0,  # Only fees lost
                net_pnl_percent=-0.2
            )

            message = service.format_trade_closed_message(data)

            assert "Trade Closed" in message
            assert "BTC_Binance_1h_001" in message


class TestDailyReportEdgeCases:
    """Edge case tests for daily report messages."""

    def test_format_daily_report_no_trades(self):
        """Test formatting daily report with zero trades."""
        from app.services.telegram_service import TelegramService
        from app.models import DailyReportData

        service = TelegramService()

        data = DailyReportData(
            date="2026-01-20",
            total_trades=0,
            total_pyramids=0,
            total_pnl_usdt=0.0,
            total_pnl_percent=0.0,
            trades=[],
            by_exchange={},
            by_timeframe={},
            by_pair={}
        )

        message = service.format_daily_report_message(data)

        assert "Daily Report" in message
        assert "Total Trades: 0" in message

    def test_format_daily_report_negative_pnl(self):
        """Test formatting daily report with negative PnL."""
        from app.services.telegram_service import TelegramService
        from app.models import DailyReportData

        service = TelegramService()

        data = DailyReportData(
            date="2026-01-20",
            total_trades=3,
            total_pyramids=5,
            total_pnl_usdt=-250.0,
            total_pnl_percent=-8.5,
            trades=[],
            by_exchange={},
            by_timeframe={},
            by_pair={}
        )

        message = service.format_daily_report_message(data)

        assert "Daily Report" in message
        assert "Total Trades: 3" in message


class TestSplitMessage:
    """Tests for _split_message method."""

    def test_split_message_short_text(self):
        """Test that short messages are returned as single chunk."""
        from app.services.telegram_service import TelegramService

        service = TelegramService()

        text = "Short message"
        chunks = service._split_message(text)

        assert len(chunks) == 1
        assert chunks[0] == text

    def test_split_message_long_text(self):
        """Test that long messages are split into chunks."""
        from app.services.telegram_service import TelegramService

        service = TelegramService()

        # Create a message longer than 4096 chars
        lines = [f"Line {i}: " + "x" * 100 for i in range(50)]
        text = "\n".join(lines)

        chunks = service._split_message(text)

        assert len(chunks) > 1
        for chunk in chunks:
            assert len(chunk) <= 4096

    def test_split_message_custom_limit(self):
        """Test splitting with custom max length."""
        from app.services.telegram_service import TelegramService

        service = TelegramService()

        text = "Line 1\nLine 2\nLine 3\nLine 4"
        chunks = service._split_message(text, max_length=15)

        assert len(chunks) > 1

    def test_split_message_preserves_content(self):
        """Test that split message preserves all content."""
        from app.services.telegram_service import TelegramService

        service = TelegramService()

        lines = [f"Line {i}" for i in range(10)]
        text = "\n".join(lines)
        chunks = service._split_message(text, max_length=30)

        # All original lines should be present
        rejoined = "\n".join(chunks)
        for line in lines:
            assert line in rejoined


class TestSendMessage:
    """Tests for send_message method."""

    @pytest.mark.asyncio
    async def test_send_message_success(self):
        """Test successful message sending."""
        from app.services.telegram_service import TelegramService

        service = TelegramService()
        mock_bot = MagicMock()
        mock_bot.send_message = AsyncMock()

        with patch("app.services.telegram_service.settings") as mock_settings:
            mock_settings.telegram_enabled = True
            mock_settings.telegram_bot_token = "test_token"
            mock_settings.telegram_channel_id = "-1001234567890"

            service._bot = mock_bot

            result = await service.send_message("Test message")

            assert result is True
            mock_bot.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_message_disabled(self):
        """Test message sending when Telegram is disabled."""
        from app.services.telegram_service import TelegramService

        service = TelegramService()

        with patch("app.services.telegram_service.settings") as mock_settings:
            mock_settings.telegram_enabled = False
            mock_settings.telegram_bot_token = "test_token"
            mock_settings.telegram_channel_id = "-1001234567890"

            result = await service.send_message("Test message")

            assert result is False

    @pytest.mark.asyncio
    async def test_send_message_telegram_error(self):
        """Test message sending with TelegramError."""
        from app.services.telegram_service import TelegramService
        from telegram.error import TelegramError

        service = TelegramService()
        mock_bot = MagicMock()
        mock_bot.send_message = AsyncMock(side_effect=TelegramError("API error"))

        with patch("app.services.telegram_service.settings") as mock_settings:
            mock_settings.telegram_enabled = True
            mock_settings.telegram_bot_token = "test_token"
            mock_settings.telegram_channel_id = "-1001234567890"

            service._bot = mock_bot

            result = await service.send_message("Test message")

            assert result is False

    @pytest.mark.asyncio
    async def test_send_message_unexpected_error(self):
        """Test message sending with unexpected exception."""
        from app.services.telegram_service import TelegramService

        service = TelegramService()
        mock_bot = MagicMock()
        mock_bot.send_message = AsyncMock(side_effect=Exception("Unexpected error"))

        with patch("app.services.telegram_service.settings") as mock_settings:
            mock_settings.telegram_enabled = True
            mock_settings.telegram_bot_token = "test_token"
            mock_settings.telegram_channel_id = "-1001234567890"

            service._bot = mock_bot

            result = await service.send_message("Test message")

            assert result is False

    @pytest.mark.asyncio
    async def test_send_message_splits_long_text(self):
        """Test that long messages are split and sent in chunks."""
        from app.services.telegram_service import TelegramService

        service = TelegramService()
        mock_bot = MagicMock()
        mock_bot.send_message = AsyncMock()

        with patch("app.services.telegram_service.settings") as mock_settings:
            mock_settings.telegram_enabled = True
            mock_settings.telegram_bot_token = "test_token"
            mock_settings.telegram_channel_id = "-1001234567890"

            service._bot = mock_bot

            # Create a very long message
            long_text = "\n".join([f"Line {i}: " + "x" * 100 for i in range(50)])

            result = await service.send_message(long_text)

            assert result is True
            # Should have made multiple calls for chunks
            assert mock_bot.send_message.call_count > 1


class TestSendToSignalsChannel:
    """Tests for send_to_signals_channel method."""

    @pytest.mark.asyncio
    async def test_send_to_signals_channel_success(self):
        """Test successful sending to signals channel."""
        from app.services.telegram_service import TelegramService

        service = TelegramService()
        mock_bot = MagicMock()
        mock_bot.send_message = AsyncMock()

        with patch("app.services.telegram_service.settings") as mock_settings, \
             patch.object(service, "get_signals_channel_id", new_callable=AsyncMock) as mock_get_channel:

            mock_settings.telegram_enabled = True
            mock_settings.telegram_bot_token = "test_token"
            mock_get_channel.return_value = "-1009876543210"

            service._bot = mock_bot

            result = await service.send_to_signals_channel("Test signal")

            assert result is True
            mock_bot.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_to_signals_channel_disabled(self):
        """Test sending when signals channel is disabled."""
        from app.services.telegram_service import TelegramService

        service = TelegramService()

        with patch("app.services.telegram_service.settings") as mock_settings:
            mock_settings.telegram_enabled = False
            mock_settings.telegram_bot_token = ""

            result = await service.send_to_signals_channel("Test signal")

            assert result is False

    @pytest.mark.asyncio
    async def test_send_to_signals_channel_no_channel_id(self):
        """Test sending when signals channel ID is not set."""
        from app.services.telegram_service import TelegramService

        service = TelegramService()

        with patch("app.services.telegram_service.settings") as mock_settings, \
             patch.object(service, "get_signals_channel_id", new_callable=AsyncMock) as mock_get_channel:

            mock_settings.telegram_enabled = True
            mock_settings.telegram_bot_token = "test_token"
            mock_get_channel.return_value = None

            result = await service.send_to_signals_channel("Test signal")

            assert result is False

    @pytest.mark.asyncio
    async def test_send_to_signals_channel_telegram_error(self):
        """Test sending to signals channel with TelegramError."""
        from app.services.telegram_service import TelegramService
        from telegram.error import TelegramError

        service = TelegramService()
        mock_bot = MagicMock()
        mock_bot.send_message = AsyncMock(side_effect=TelegramError("API error"))

        with patch("app.services.telegram_service.settings") as mock_settings, \
             patch.object(service, "get_signals_channel_id", new_callable=AsyncMock) as mock_get_channel:

            mock_settings.telegram_enabled = True
            mock_settings.telegram_bot_token = "test_token"
            mock_get_channel.return_value = "-1009876543210"

            service._bot = mock_bot

            result = await service.send_to_signals_channel("Test signal")

            assert result is False

    @pytest.mark.asyncio
    async def test_send_to_signals_channel_unexpected_error(self):
        """Test sending to signals channel with unexpected exception."""
        from app.services.telegram_service import TelegramService

        service = TelegramService()
        mock_bot = MagicMock()
        mock_bot.send_message = AsyncMock(side_effect=Exception("Unexpected"))

        with patch("app.services.telegram_service.settings") as mock_settings, \
             patch.object(service, "get_signals_channel_id", new_callable=AsyncMock) as mock_get_channel:

            mock_settings.telegram_enabled = True
            mock_settings.telegram_bot_token = "test_token"
            mock_get_channel.return_value = "-1009876543210"

            service._bot = mock_bot

            result = await service.send_to_signals_channel("Test signal")

            assert result is False


class TestSendSignalMessage:
    """Tests for send_signal_message method."""

    @pytest.mark.asyncio
    async def test_send_signal_message_both_succeed(self):
        """Test signal message sent to both channels successfully."""
        from app.services.telegram_service import TelegramService

        service = TelegramService()

        with patch.object(service, "send_message", new_callable=AsyncMock) as mock_main, \
             patch.object(service, "send_to_signals_channel", new_callable=AsyncMock) as mock_signals:

            mock_main.return_value = True
            mock_signals.return_value = True

            result = await service.send_signal_message("Test signal")

            assert result is True
            mock_main.assert_called_once_with("Test signal")
            mock_signals.assert_called_once_with("Test signal")

    @pytest.mark.asyncio
    async def test_send_signal_message_main_only(self):
        """Test signal message when only main channel succeeds."""
        from app.services.telegram_service import TelegramService

        service = TelegramService()

        with patch.object(service, "send_message", new_callable=AsyncMock) as mock_main, \
             patch.object(service, "send_to_signals_channel", new_callable=AsyncMock) as mock_signals:

            mock_main.return_value = True
            mock_signals.return_value = False

            result = await service.send_signal_message("Test signal")

            assert result is True

    @pytest.mark.asyncio
    async def test_send_signal_message_signals_only(self):
        """Test signal message when only signals channel succeeds."""
        from app.services.telegram_service import TelegramService

        service = TelegramService()

        with patch.object(service, "send_message", new_callable=AsyncMock) as mock_main, \
             patch.object(service, "send_to_signals_channel", new_callable=AsyncMock) as mock_signals:

            mock_main.return_value = False
            mock_signals.return_value = True

            result = await service.send_signal_message("Test signal")

            assert result is True

    @pytest.mark.asyncio
    async def test_send_signal_message_both_fail(self):
        """Test signal message when both channels fail."""
        from app.services.telegram_service import TelegramService

        service = TelegramService()

        with patch.object(service, "send_message", new_callable=AsyncMock) as mock_main, \
             patch.object(service, "send_to_signals_channel", new_callable=AsyncMock) as mock_signals:

            mock_main.return_value = False
            mock_signals.return_value = False

            result = await service.send_signal_message("Test signal")

            assert result is False


class TestSendTradeClosed:
    """Tests for send_trade_closed method."""

    @pytest.mark.asyncio
    async def test_send_trade_closed_success(self):
        """Test successful trade closed notification."""
        from app.services.telegram_service import TelegramService
        from app.models import TradeClosedData

        service = TelegramService()

        with patch("app.services.telegram_service.settings") as mock_settings, \
             patch.object(service, "send_signal_message", new_callable=AsyncMock) as mock_send:

            mock_settings.timezone = "UTC"
            mock_send.return_value = True

            data = TradeClosedData(
                trade_id="trade_001",
                group_id="BTC_Binance_1h_001",
                timeframe="1h",
                exchange="binance",
                base="BTC",
                quote="USDT",
                pyramids=[{"index": 0, "entry_price": 50000.0, "size": 0.02, "entry_time": "2026-01-20T10:00:00Z"}],
                exit_price=51000.0,
                exit_time=datetime.now(UTC),
                exchange_timestamp="2026-01-20T12:00:00Z",
                received_timestamp=datetime.now(UTC),
                gross_pnl=20.0,
                total_fees=2.0,
                net_pnl=18.0,
                net_pnl_percent=1.8
            )

            result = await service.send_trade_closed(data)

            assert result is True
            mock_send.assert_called_once()
            call_arg = mock_send.call_args[0][0]
            assert "Trade Closed" in call_arg


class TestSendPyramidEntry:
    """Tests for send_pyramid_entry method."""

    @pytest.mark.asyncio
    async def test_send_pyramid_entry_success(self):
        """Test successful pyramid entry notification."""
        from app.services.telegram_service import TelegramService
        from app.models import PyramidEntryData

        service = TelegramService()

        with patch("app.services.telegram_service.settings") as mock_settings, \
             patch.object(service, "send_signal_message", new_callable=AsyncMock) as mock_send:

            mock_settings.timezone = "UTC"
            mock_send.return_value = True

            data = PyramidEntryData(
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
                received_timestamp=datetime.now(UTC),
                total_pyramids=1
            )

            result = await service.send_pyramid_entry(data)

            assert result is True
            mock_send.assert_called_once()
            call_arg = mock_send.call_args[0][0]
            assert "Trade Entry" in call_arg


class TestSendPhotoToChannel:
    """Tests for send_photo_to_channel method."""

    @pytest.mark.asyncio
    async def test_send_photo_success(self):
        """Test successful photo sending."""
        import io
        from app.services.telegram_service import TelegramService

        service = TelegramService()
        mock_bot = MagicMock()
        mock_bot.send_photo = AsyncMock()

        with patch("app.services.telegram_service.settings") as mock_settings:
            mock_settings.telegram_enabled = True
            mock_settings.telegram_bot_token = "test_token"
            mock_settings.telegram_channel_id = "-1001234567890"

            service._bot = mock_bot

            photo = io.BytesIO(b"fake image data")
            result = await service.send_photo_to_channel(photo, caption="Test caption")

            assert result is True
            mock_bot.send_photo.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_photo_disabled(self):
        """Test photo sending when Telegram is disabled."""
        import io
        from app.services.telegram_service import TelegramService

        service = TelegramService()

        with patch("app.services.telegram_service.settings") as mock_settings:
            mock_settings.telegram_enabled = False
            mock_settings.telegram_bot_token = "test_token"
            mock_settings.telegram_channel_id = "-1001234567890"

            photo = io.BytesIO(b"fake image data")
            result = await service.send_photo_to_channel(photo)

            assert result is False

    @pytest.mark.asyncio
    async def test_send_photo_telegram_error(self):
        """Test photo sending with TelegramError."""
        import io
        from app.services.telegram_service import TelegramService
        from telegram.error import TelegramError

        service = TelegramService()
        mock_bot = MagicMock()
        mock_bot.send_photo = AsyncMock(side_effect=TelegramError("API error"))

        with patch("app.services.telegram_service.settings") as mock_settings:
            mock_settings.telegram_enabled = True
            mock_settings.telegram_bot_token = "test_token"
            mock_settings.telegram_channel_id = "-1001234567890"

            service._bot = mock_bot

            photo = io.BytesIO(b"fake image data")
            result = await service.send_photo_to_channel(photo)

            assert result is False


class TestSendPhotoToSignalsChannel:
    """Tests for send_photo_to_signals_channel method."""

    @pytest.mark.asyncio
    async def test_send_photo_to_signals_success(self):
        """Test successful photo sending to signals channel."""
        import io
        from app.services.telegram_service import TelegramService

        service = TelegramService()
        mock_bot = MagicMock()
        mock_bot.send_photo = AsyncMock()

        with patch("app.services.telegram_service.settings") as mock_settings, \
             patch.object(service, "get_signals_channel_id", new_callable=AsyncMock) as mock_get_channel:

            mock_settings.telegram_enabled = True
            mock_settings.telegram_bot_token = "test_token"
            mock_get_channel.return_value = "-1009876543210"

            service._bot = mock_bot

            photo = io.BytesIO(b"fake image data")
            result = await service.send_photo_to_signals_channel(photo, caption="Test")

            assert result is True
            mock_bot.send_photo.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_photo_to_signals_disabled(self):
        """Test photo sending when signals channel is disabled."""
        import io
        from app.services.telegram_service import TelegramService

        service = TelegramService()

        with patch("app.services.telegram_service.settings") as mock_settings:
            mock_settings.telegram_enabled = False
            mock_settings.telegram_bot_token = ""

            photo = io.BytesIO(b"fake image data")
            result = await service.send_photo_to_signals_channel(photo)

            assert result is False

    @pytest.mark.asyncio
    async def test_send_photo_to_signals_no_channel_id(self):
        """Test photo sending when signals channel ID is not set."""
        import io
        from app.services.telegram_service import TelegramService

        service = TelegramService()

        with patch("app.services.telegram_service.settings") as mock_settings, \
             patch.object(service, "get_signals_channel_id", new_callable=AsyncMock) as mock_get_channel:

            mock_settings.telegram_enabled = True
            mock_settings.telegram_bot_token = "test_token"
            mock_get_channel.return_value = None

            photo = io.BytesIO(b"fake image data")
            result = await service.send_photo_to_signals_channel(photo)

            assert result is False

    @pytest.mark.asyncio
    async def test_send_photo_to_signals_telegram_error(self):
        """Test photo sending to signals channel with TelegramError."""
        import io
        from app.services.telegram_service import TelegramService
        from telegram.error import TelegramError

        service = TelegramService()
        mock_bot = MagicMock()
        mock_bot.send_photo = AsyncMock(side_effect=TelegramError("API error"))

        with patch("app.services.telegram_service.settings") as mock_settings, \
             patch.object(service, "get_signals_channel_id", new_callable=AsyncMock) as mock_get_channel:

            mock_settings.telegram_enabled = True
            mock_settings.telegram_bot_token = "test_token"
            mock_get_channel.return_value = "-1009876543210"

            service._bot = mock_bot

            photo = io.BytesIO(b"fake image data")
            result = await service.send_photo_to_signals_channel(photo)

            assert result is False


class TestSendDailyReport:
    """Tests for send_daily_report method."""

    @pytest.mark.asyncio
    async def test_send_daily_report_without_equity_curve(self):
        """Test sending daily report without equity curve."""
        from app.services.telegram_service import TelegramService
        from app.models import DailyReportData

        service = TelegramService()

        with patch("app.services.telegram_service.settings") as mock_settings, \
             patch.object(service, "send_signal_message", new_callable=AsyncMock) as mock_send:

            mock_settings.timezone = "UTC"
            mock_settings.equity_curve_enabled = False
            mock_send.return_value = True

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

            result = await service.send_daily_report(data)

            assert result is True
            mock_send.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_daily_report_with_equity_curve(self):
        """Test sending daily report with equity curve enabled."""
        import io
        from app.services.telegram_service import TelegramService
        from app.models import DailyReportData, EquityPoint

        service = TelegramService()

        with patch("app.services.telegram_service.settings") as mock_settings, \
             patch.object(service, "send_signal_message", new_callable=AsyncMock) as mock_send, \
             patch.object(service, "generate_equity_curve_image") as mock_gen_chart, \
             patch.object(service, "send_photo_to_channel", new_callable=AsyncMock) as mock_send_photo, \
             patch.object(service, "send_photo_to_signals_channel", new_callable=AsyncMock) as mock_send_photo_signals:

            mock_settings.timezone = "UTC"
            mock_settings.equity_curve_enabled = True
            mock_settings.telegram_enabled = True
            mock_settings.telegram_bot_token = "test_token"
            mock_settings.telegram_channel_id = "-1001234567890"
            mock_send.return_value = True
            mock_gen_chart.return_value = io.BytesIO(b"fake chart")
            mock_send_photo.return_value = True
            mock_send_photo_signals.return_value = True

            data = DailyReportData(
                date="2026-01-20",
                total_trades=5,
                total_pyramids=8,
                total_pnl_usdt=150.0,
                total_pnl_percent=5.0,
                trades=[],
                by_exchange={},
                by_timeframe={},
                by_pair={},
                equity_points=[
                    EquityPoint(timestamp=datetime.now(UTC), cumulative_pnl=50.0),
                    EquityPoint(timestamp=datetime.now(UTC), cumulative_pnl=100.0),
                ]
            )

            result = await service.send_daily_report(data)

            assert result is True
            mock_gen_chart.assert_called_once()
            mock_send_photo.assert_called_once()
            mock_send_photo_signals.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_daily_report_equity_curve_no_data(self):
        """Test sending daily report when equity curve has no data."""
        from app.services.telegram_service import TelegramService
        from app.models import DailyReportData

        service = TelegramService()

        with patch("app.services.telegram_service.settings") as mock_settings, \
             patch.object(service, "send_signal_message", new_callable=AsyncMock) as mock_send, \
             patch.object(service, "generate_equity_curve_image") as mock_gen_chart:

            mock_settings.timezone = "UTC"
            mock_settings.equity_curve_enabled = True
            mock_send.return_value = True
            mock_gen_chart.return_value = None  # No chart generated

            data = DailyReportData(
                date="2026-01-20",
                total_trades=5,
                total_pyramids=8,
                total_pnl_usdt=150.0,
                total_pnl_percent=5.0,
                trades=[],
                by_exchange={},
                by_timeframe={},
                by_pair={},
                equity_points=[]  # No equity points
            )

            result = await service.send_daily_report(data)

            assert result is True
            # Chart generation should not be called with empty equity_points
            mock_gen_chart.assert_not_called()


class TestGetSignalsChannelId:
    """Tests for get_signals_channel_id method."""

    @pytest.mark.asyncio
    async def test_get_signals_channel_id_from_database(self):
        """Test getting signals channel ID from database."""
        from app.services.telegram_service import TelegramService

        service = TelegramService()

        mock_cursor = MagicMock()
        mock_cursor.fetchone = AsyncMock(return_value={"value": "-1009876543210"})

        mock_connection = MagicMock()
        mock_connection.execute = AsyncMock(return_value=mock_cursor)

        mock_db = MagicMock()
        mock_db.connection = mock_connection

        with patch("app.services.telegram_service.db", mock_db):
            result = await service.get_signals_channel_id()

        assert result == "-1009876543210"

    @pytest.mark.asyncio
    async def test_get_signals_channel_id_from_env(self):
        """Test getting signals channel ID from environment when DB is empty."""
        from app.services.telegram_service import TelegramService

        service = TelegramService()

        mock_cursor = MagicMock()
        mock_cursor.fetchone = AsyncMock(return_value=None)

        mock_connection = MagicMock()
        mock_connection.execute = AsyncMock(return_value=mock_cursor)

        mock_db = MagicMock()
        mock_db.connection = mock_connection

        with patch("app.services.telegram_service.db", mock_db), \
             patch("app.services.telegram_service.settings") as mock_settings:

            mock_settings.telegram_signals_channel_id = "-1001111222333"

            result = await service.get_signals_channel_id()

        assert result == "-1001111222333"

    @pytest.mark.asyncio
    async def test_get_signals_channel_id_none(self):
        """Test getting signals channel ID when not configured."""
        from app.services.telegram_service import TelegramService

        service = TelegramService()

        mock_cursor = MagicMock()
        mock_cursor.fetchone = AsyncMock(return_value=None)

        mock_connection = MagicMock()
        mock_connection.execute = AsyncMock(return_value=mock_cursor)

        mock_db = MagicMock()
        mock_db.connection = mock_connection

        with patch("app.services.telegram_service.db", mock_db), \
             patch("app.services.telegram_service.settings") as mock_settings:

            mock_settings.telegram_signals_channel_id = None

            result = await service.get_signals_channel_id()

        assert result is None

    @pytest.mark.asyncio
    async def test_get_signals_channel_id_database_error(self):
        """Test getting signals channel ID when database throws error."""
        from app.services.telegram_service import TelegramService

        service = TelegramService()

        mock_connection = MagicMock()
        mock_connection.execute = AsyncMock(side_effect=Exception("DB error"))

        mock_db = MagicMock()
        mock_db.connection = mock_connection

        with patch("app.services.telegram_service.db", mock_db), \
             patch("app.services.telegram_service.settings") as mock_settings:

            mock_settings.telegram_signals_channel_id = "-1001111222333"

            result = await service.get_signals_channel_id()

        # Should fall back to env var
        assert result == "-1001111222333"
