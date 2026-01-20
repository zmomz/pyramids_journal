"""
Tests for bot command handlers in app/bot/handlers.py

Tests the command handling logic and date filtering.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
import pytz


class TestParseDateFilter:
    """Tests for parse_date_filter helper function."""

    def test_empty_args_returns_all_time(self):
        """Test that empty args return all-time (None, None)."""
        from app.bot.handlers import parse_date_filter

        start, end, label = parse_date_filter([])

        assert start is None
        assert end is None
        assert label == "All-Time"

    def test_today_filter(self):
        """Test 'today' filter."""
        from app.bot.handlers import parse_date_filter
        from app.config import settings

        start, end, label = parse_date_filter(["today"])
        # Use same timezone as the handler
        tz = pytz.timezone(settings.timezone)
        now = datetime.now(tz)
        today = now.strftime("%Y-%m-%d")

        assert start == today
        assert end == today
        assert label == f"Today ({today})"

    def test_yesterday_filter(self):
        """Test 'yesterday' filter."""
        from app.bot.handlers import parse_date_filter
        from app.config import settings

        start, end, label = parse_date_filter(["yesterday"])
        # Use same timezone as the handler
        tz = pytz.timezone(settings.timezone)
        now = datetime.now(tz)
        yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d")

        assert start == yesterday
        assert end == yesterday
        assert label == f"Yesterday ({yesterday})"

    def test_week_filter(self):
        """Test 'week' filter."""
        from app.bot.handlers import parse_date_filter
        from app.config import settings

        start, end, label = parse_date_filter(["week"])
        # Use same timezone as the handler
        tz = pytz.timezone(settings.timezone)
        now = datetime.now(tz)
        today = now.strftime("%Y-%m-%d")
        # 6 days ago + today = 7 days total
        week_start = (now - timedelta(days=6)).strftime("%Y-%m-%d")

        assert start == week_start
        assert end == today
        assert label == "Last 7 Days"

    def test_month_filter(self):
        """Test 'month' filter."""
        from app.bot.handlers import parse_date_filter
        from app.config import settings

        start, end, label = parse_date_filter(["month"])
        # Use same timezone as the handler
        tz = pytz.timezone(settings.timezone)
        now = datetime.now(tz)
        today = now.strftime("%Y-%m-%d")
        # 29 days ago + today = 30 days total
        month_start = (now - timedelta(days=29)).strftime("%Y-%m-%d")

        assert start == month_start
        assert end == today
        assert label == "Last 30 Days"

    def test_specific_date_filter(self):
        """Test specific date filter (YYYY-MM-DD)."""
        from app.bot.handlers import parse_date_filter

        start, end, label = parse_date_filter(["2026-01-15"])

        assert start == "2026-01-15"
        assert end == "2026-01-15"
        assert label == "2026-01-15"

    def test_invalid_filter_returns_all_time(self):
        """Test that invalid filter returns all-time."""
        from app.bot.handlers import parse_date_filter

        start, end, label = parse_date_filter(["invalid"])

        assert start is None
        assert end is None
        assert label == "All-Time"


class TestCmdPing:
    """Tests for /ping command."""

    @pytest.mark.asyncio
    async def test_ping_responds(self, mock_update, mock_context):
        """Test that ping command responds."""
        from app.bot.handlers import cmd_ping

        # Mock bot validation
        with patch("app.bot.handlers._bot") as mock_bot:
            mock_bot.is_valid_chat.return_value = True

            await cmd_ping(mock_update, mock_context)

            mock_update.message.reply_text.assert_called_once()
            call_args = mock_update.message.reply_text.call_args[0][0]
            assert "pong" in call_args.lower()


class TestCmdStats:
    """Tests for /stats command."""

    @pytest.mark.asyncio
    async def test_stats_all_time(self, mock_update, mock_context, populated_db):
        """Test /stats command for all-time."""
        from app.bot.handlers import cmd_stats

        mock_context.args = []

        with patch("app.bot.handlers._bot") as mock_bot:
            mock_bot.is_valid_chat.return_value = True

            with patch("app.bot.handlers.db", populated_db):
                await cmd_stats(mock_update, mock_context)

                mock_update.message.reply_text.assert_called_once()
                call_args = mock_update.message.reply_text.call_args[0][0]
                assert "Statistics" in call_args
                assert "All-Time" in call_args

    @pytest.mark.asyncio
    async def test_stats_today(self, mock_update, mock_context, populated_db):
        """Test /stats today command."""
        from app.bot.handlers import cmd_stats

        mock_context.args = ["today"]

        with patch("app.bot.handlers._bot") as mock_bot:
            mock_bot.is_valid_chat.return_value = True

            with patch("app.bot.handlers.db", populated_db):
                await cmd_stats(mock_update, mock_context)

                call_args = mock_update.message.reply_text.call_args[0][0]
                assert "Today" in call_args


class TestCmdPnl:
    """Tests for /pnl command."""

    @pytest.mark.asyncio
    async def test_pnl_all_time(self, mock_update, mock_context, populated_db):
        """Test /pnl command for all-time."""
        from app.bot.handlers import cmd_pnl

        mock_context.args = []

        with patch("app.bot.handlers._bot") as mock_bot:
            mock_bot.is_valid_chat.return_value = True

            with patch("app.bot.handlers.db", populated_db):
                await cmd_pnl(mock_update, mock_context)

                mock_update.message.reply_text.assert_called_once()
                call_args = mock_update.message.reply_text.call_args[0][0]
                assert "PnL" in call_args

    @pytest.mark.asyncio
    async def test_pnl_week(self, mock_update, mock_context, populated_db):
        """Test /pnl week command."""
        from app.bot.handlers import cmd_pnl

        mock_context.args = ["week"]

        with patch("app.bot.handlers._bot") as mock_bot:
            mock_bot.is_valid_chat.return_value = True

            with patch("app.bot.handlers.db", populated_db):
                await cmd_pnl(mock_update, mock_context)

                call_args = mock_update.message.reply_text.call_args[0][0]
                assert "7 Days" in call_args or "Week" in call_args


class TestCmdBest:
    """Tests for /best command."""

    @pytest.mark.asyncio
    async def test_best_all_time(self, mock_update, mock_context, populated_db):
        """Test /best command for all-time."""
        from app.bot.handlers import cmd_best

        mock_context.args = []

        with patch("app.bot.handlers._bot") as mock_bot:
            mock_bot.is_valid_chat.return_value = True

            with patch("app.bot.handlers.db", populated_db):
                await cmd_best(mock_update, mock_context)

                mock_update.message.reply_text.assert_called_once()
                call_args = mock_update.message.reply_text.call_args[0][0]
                assert "Best Pairs" in call_args

    @pytest.mark.asyncio
    async def test_best_today(self, mock_update, mock_context, populated_db):
        """Test /best today command."""
        from app.bot.handlers import cmd_best

        mock_context.args = ["today"]

        with patch("app.bot.handlers._bot") as mock_bot:
            mock_bot.is_valid_chat.return_value = True

            with patch("app.bot.handlers.db", populated_db):
                await cmd_best(mock_update, mock_context)

                call_args = mock_update.message.reply_text.call_args[0][0]
                assert "Today" in call_args


class TestCmdWorst:
    """Tests for /worst command."""

    @pytest.mark.asyncio
    async def test_worst_all_time(self, mock_update, mock_context, populated_db):
        """Test /worst command for all-time."""
        from app.bot.handlers import cmd_worst

        mock_context.args = []

        with patch("app.bot.handlers._bot") as mock_bot:
            mock_bot.is_valid_chat.return_value = True

            with patch("app.bot.handlers.db", populated_db):
                await cmd_worst(mock_update, mock_context)

                mock_update.message.reply_text.assert_called_once()
                call_args = mock_update.message.reply_text.call_args[0][0]
                assert "Worst Pairs" in call_args


class TestCmdStreak:
    """Tests for /streak command."""

    @pytest.mark.asyncio
    async def test_streak_all_time(self, mock_update, mock_context, populated_db):
        """Test /streak command for all-time."""
        from app.bot.handlers import cmd_streak

        mock_context.args = []

        with patch("app.bot.handlers._bot") as mock_bot:
            mock_bot.is_valid_chat.return_value = True

            with patch("app.bot.handlers.db", populated_db):
                await cmd_streak(mock_update, mock_context)

                mock_update.message.reply_text.assert_called_once()
                call_args = mock_update.message.reply_text.call_args[0][0]
                assert "Streak" in call_args


class TestCmdDrawdown:
    """Tests for /drawdown command."""

    @pytest.mark.asyncio
    async def test_drawdown_all_time(self, mock_update, mock_context, populated_db):
        """Test /drawdown command for all-time."""
        from app.bot.handlers import cmd_drawdown

        mock_context.args = []

        with patch("app.bot.handlers._bot") as mock_bot:
            mock_bot.is_valid_chat.return_value = True

            with patch("app.bot.handlers.db", populated_db):
                await cmd_drawdown(mock_update, mock_context)

                mock_update.message.reply_text.assert_called_once()
                call_args = mock_update.message.reply_text.call_args[0][0]
                assert "Drawdown" in call_args

    @pytest.mark.asyncio
    async def test_drawdown_no_trades(self, mock_update, mock_context, test_db):
        """Test /drawdown with no trades returns appropriate message."""
        from app.bot.handlers import cmd_drawdown

        mock_context.args = ["2030-01-01"]

        with patch("app.bot.handlers._bot") as mock_bot:
            mock_bot.is_valid_chat.return_value = True

            with patch("app.bot.handlers.db", test_db):
                await cmd_drawdown(mock_update, mock_context)

                call_args = mock_update.message.reply_text.call_args[0][0]
                assert "No closed trades" in call_args


class TestCmdTrades:
    """Tests for /trades command."""

    @pytest.mark.asyncio
    async def test_trades_default(self, mock_update, mock_context, populated_db):
        """Test /trades command with default (last 10)."""
        from app.bot.handlers import cmd_trades

        mock_context.args = []

        with patch("app.bot.handlers._bot") as mock_bot:
            mock_bot.is_valid_chat.return_value = True

            with patch("app.bot.handlers.db", populated_db):
                await cmd_trades(mock_update, mock_context)

                mock_update.message.reply_text.assert_called_once()
                call_args = mock_update.message.reply_text.call_args[0][0]
                assert "Recent Trades" in call_args

    @pytest.mark.asyncio
    async def test_trades_with_limit(self, mock_update, mock_context, populated_db):
        """Test /trades N command with numeric limit."""
        from app.bot.handlers import cmd_trades

        mock_context.args = ["5"]

        with patch("app.bot.handlers._bot") as mock_bot:
            mock_bot.is_valid_chat.return_value = True

            with patch("app.bot.handlers.db", populated_db):
                await cmd_trades(mock_update, mock_context)

                mock_update.message.reply_text.assert_called_once()
                call_args = mock_update.message.reply_text.call_args[0][0]
                assert "Recent Trades" in call_args or "Trade" in call_args

    @pytest.mark.asyncio
    async def test_trades_today(self, mock_update, mock_context, populated_db):
        """Test /trades today command."""
        from app.bot.handlers import cmd_trades

        mock_context.args = ["today"]

        with patch("app.bot.handlers._bot") as mock_bot:
            mock_bot.is_valid_chat.return_value = True

            with patch("app.bot.handlers.db", populated_db):
                await cmd_trades(mock_update, mock_context)

                call_args = mock_update.message.reply_text.call_args[0][0]
                assert "Today" in call_args


class TestCmdStatus:
    """Tests for /status command."""

    @pytest.mark.asyncio
    async def test_status_with_open_trades(self, mock_update, mock_context, populated_db):
        """Test /status command with open trades."""
        from app.bot.handlers import cmd_status

        mock_context.args = []

        with patch("app.bot.handlers._bot") as mock_bot:
            mock_bot.is_valid_chat.return_value = True

            with patch("app.bot.handlers.db", populated_db):
                # Mock exchange_service.get_price
                with patch("app.bot.handlers.exchange_service") as mock_exchange:
                    mock_price = MagicMock()
                    mock_price.price = 50000.0
                    mock_exchange.get_price = AsyncMock(return_value=mock_price)

                    await cmd_status(mock_update, mock_context)

                    mock_update.message.reply_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_status_no_open_trades(self, mock_update, mock_context, test_db):
        """Test /status with no open trades shows appropriate message."""
        from app.bot.handlers import cmd_status

        mock_context.args = []

        with patch("app.bot.handlers._bot") as mock_bot:
            mock_bot.is_valid_chat.return_value = True

            with patch("app.bot.handlers.db", test_db):
                await cmd_status(mock_update, mock_context)

                call_args = mock_update.message.reply_text.call_args[0][0]
                assert "No open" in call_args or "no open" in call_args


class TestCmdHelp:
    """Tests for /help command."""

    @pytest.mark.asyncio
    async def test_help_shows_all_commands(self, mock_update, mock_context):
        """Test that /help shows all available commands."""
        from app.bot.handlers import cmd_help

        with patch("app.bot.handlers._bot") as mock_bot:
            mock_bot.is_valid_chat.return_value = True

            await cmd_help(mock_update, mock_context)

            mock_update.message.reply_text.assert_called_once()
            call_args = mock_update.message.reply_text.call_args[0][0]

            # Verify all major commands are listed
            assert "/menu" in call_args
            assert "/stats" in call_args
            assert "/pnl" in call_args
            assert "/best" in call_args
            assert "/worst" in call_args
            assert "/drawdown" in call_args
            assert "/streak" in call_args
            assert "/trades" in call_args


class TestCmdExport:
    """Tests for /export command."""

    @pytest.mark.asyncio
    async def test_export_with_trades(self, mock_update, mock_context, populated_db):
        """Test /export command with trades."""
        from app.bot.handlers import cmd_export

        mock_context.args = []

        with patch("app.bot.handlers._bot") as mock_bot:
            mock_bot.is_valid_chat.return_value = True

            with patch("app.bot.handlers.db", populated_db):
                await cmd_export(mock_update, mock_context)

                # Should send document (CSV file)
                mock_update.message.reply_document.assert_called_once()


class TestCmdFees:
    """Tests for /fees command."""

    @pytest.mark.asyncio
    async def test_fees_shows_exchange_fees(self, mock_update, mock_context):
        """Test /fees command shows exchange fees."""
        from app.bot.handlers import cmd_fees

        mock_context.args = []

        with patch("app.bot.handlers._bot") as mock_bot:
            mock_bot.is_valid_chat.return_value = True

            # Mock exchange_config with sample fees
            mock_fee = MagicMock()
            mock_fee.maker_fee = 0.001
            mock_fee.taker_fee = 0.001

            with patch("app.bot.handlers.exchange_config") as mock_config:
                mock_config.exchanges = {"binance": mock_fee}

                await cmd_fees(mock_update, mock_context)

                mock_update.message.reply_text.assert_called_once()
                call_args = mock_update.message.reply_text.call_args[0][0]
                assert "Fees" in call_args


class TestChannelValidation:
    """Tests for channel validation decorator."""

    @pytest.mark.asyncio
    async def test_invalid_chat_rejected(self, mock_update, mock_context):
        """Test that commands from invalid chats are rejected."""
        from app.bot.handlers import cmd_stats

        mock_context.args = []

        with patch("app.bot.handlers._bot") as mock_bot:
            mock_bot.is_valid_chat.return_value = False

            await cmd_stats(mock_update, mock_context)

            # Should not reply when chat is invalid
            mock_update.message.reply_text.assert_not_called()


class TestErrorHandling:
    """Tests for error handling in handlers."""

    @pytest.mark.asyncio
    async def test_stats_handles_db_error(self, mock_update, mock_context):
        """Test that /stats handles database errors gracefully."""
        from app.bot.handlers import cmd_stats

        mock_context.args = []

        with patch("app.bot.handlers._bot") as mock_bot:
            mock_bot.is_valid_chat.return_value = True

            with patch("app.bot.handlers.db") as mock_db:
                mock_db.get_statistics_for_period = AsyncMock(
                    side_effect=Exception("Database error")
                )

                await cmd_stats(mock_update, mock_context)

                call_args = mock_update.message.reply_text.call_args[0][0]
                assert "Error" in call_args


class TestCmdExchange:
    """Tests for /exchange command."""

    @pytest.mark.asyncio
    async def test_exchange_no_args_shows_usage(self, mock_update, mock_context):
        """Test /exchange without args shows usage message."""
        from app.bot.handlers import cmd_exchange

        mock_context.args = []

        with patch("app.bot.handlers._bot") as mock_bot:
            mock_bot.is_valid_chat.return_value = True

            await cmd_exchange(mock_update, mock_context)

            mock_update.message.reply_text.assert_called_once()
            call_args = mock_update.message.reply_text.call_args[0][0]
            assert "Usage" in call_args

    @pytest.mark.asyncio
    async def test_exchange_with_name(self, mock_update, mock_context, populated_db):
        """Test /exchange <name> command for all-time stats."""
        from app.bot.handlers import cmd_exchange

        mock_context.args = ["binance"]

        with patch("app.bot.handlers._bot") as mock_bot:
            mock_bot.is_valid_chat.return_value = True

            with patch("app.bot.handlers.db", populated_db):
                await cmd_exchange(mock_update, mock_context)

                mock_update.message.reply_text.assert_called_once()
                call_args = mock_update.message.reply_text.call_args[0][0]
                # Should contain exchange name and stats
                assert "Binance" in call_args or "binance" in call_args.lower()

    @pytest.mark.asyncio
    async def test_exchange_with_name_and_period(self, mock_update, mock_context, populated_db):
        """Test /exchange <name> today command."""
        from app.bot.handlers import cmd_exchange

        mock_context.args = ["binance", "today"]

        with patch("app.bot.handlers._bot") as mock_bot:
            mock_bot.is_valid_chat.return_value = True

            with patch("app.bot.handlers.db", populated_db):
                await cmd_exchange(mock_update, mock_context)

                call_args = mock_update.message.reply_text.call_args[0][0]
                assert "Today" in call_args or "Binance" in call_args


class TestCmdLive:
    """Tests for /live command."""

    @pytest.mark.asyncio
    async def test_live_no_positions(self, mock_update, mock_context, test_db):
        """Test /live command with no open positions."""
        from app.bot.handlers import cmd_live

        with patch("app.bot.handlers._bot") as mock_bot:
            mock_bot.is_valid_chat.return_value = True

            with patch("app.bot.handlers.db", test_db):
                await cmd_live(mock_update, mock_context)

                call_args = mock_update.message.reply_text.call_args[0][0]
                assert "No open positions" in call_args


class TestCmdReport:
    """Tests for /report command."""

    @pytest.mark.asyncio
    async def test_report_invalid_period(self, mock_update, mock_context):
        """Test /report with invalid period shows usage."""
        from app.bot.handlers import cmd_report

        mock_context.args = ["invalid_period"]

        with patch("app.bot.handlers._bot") as mock_bot:
            mock_bot.is_valid_chat.return_value = True

            await cmd_report(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args[0][0]
            assert "Usage" in call_args


class TestParseDateFilterEdgeCases:
    """Additional tests for parse_date_filter edge cases."""

    def test_invalid_date_format(self):
        """Test that invalid date format returns all-time."""
        from app.bot.handlers import parse_date_filter

        start, end, label = parse_date_filter(["2026-13-45"])  # Invalid date

        assert start is None
        assert end is None
        assert label == "All-Time"

    def test_case_insensitive_period(self):
        """Test that period is case insensitive."""
        from app.bot.handlers import parse_date_filter

        start1, _, label1 = parse_date_filter(["TODAY"])
        start2, _, label2 = parse_date_filter(["Today"])
        start3, _, label3 = parse_date_filter(["today"])

        assert start1 == start2 == start3
        assert "Today" in label1 and "Today" in label2 and "Today" in label3


class TestBotNotSet:
    """Tests for when _bot is None."""

    @pytest.mark.asyncio
    async def test_command_when_bot_none(self, mock_update, mock_context):
        """Test that commands silently fail when _bot is None."""
        from app.bot.handlers import cmd_ping

        with patch("app.bot.handlers._bot", None):
            await cmd_ping(mock_update, mock_context)

            # Should not reply when bot is None
            mock_update.message.reply_text.assert_not_called()


class TestSetupHandlers:
    """Tests for setup_handlers function."""

    def test_setup_handlers_registers_commands(self):
        """Test that setup_handlers registers all commands."""
        from app.bot.handlers import setup_handlers

        mock_app = MagicMock()
        mock_bot = MagicMock()

        setup_handlers(mock_app, mock_bot)

        # Verify add_handler was called multiple times
        assert mock_app.add_handler.call_count > 0


class TestCmdHistory:
    """Tests for /history command."""

    @pytest.mark.asyncio
    async def test_history_no_args_shows_usage(self, mock_update, mock_context):
        """Test /history without args shows usage."""
        from app.bot.handlers import cmd_history

        mock_context.args = []

        with patch("app.bot.handlers._bot") as mock_bot:
            mock_bot.is_valid_chat.return_value = True

            await cmd_history(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args[0][0]
            assert "Usage" in call_args

    @pytest.mark.asyncio
    async def test_history_with_pair(self, mock_update, mock_context, populated_db):
        """Test /history with pair argument."""
        from app.bot.handlers import cmd_history

        mock_context.args = ["BTC/USDT"]

        with patch("app.bot.handlers._bot") as mock_bot:
            mock_bot.is_valid_chat.return_value = True

            with patch("app.bot.handlers.db", populated_db):
                await cmd_history(mock_update, mock_context)

                mock_update.message.reply_text.assert_called_once()
                call_args = mock_update.message.reply_text.call_args[0][0]
                # Should contain the pair name
                assert "BTC" in call_args or "History" in call_args


class TestCmdReset:
    """Tests for /reset command."""

    @pytest.mark.asyncio
    async def test_reset_requires_confirmation(self, mock_update, mock_context):
        """Test /reset without confirmation shows warning."""
        from app.bot.handlers import cmd_reset

        mock_context.args = []

        with patch("app.bot.handlers._bot") as mock_bot:
            mock_bot.is_valid_chat.return_value = True

            await cmd_reset(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args[0][0]
            # Should warn about confirmation
            assert "CONFIRM" in call_args or "confirm" in call_args or "warning" in call_args.lower()
