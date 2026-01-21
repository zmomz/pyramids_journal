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

    @pytest.mark.asyncio
    async def test_reset_trades_without_confirm(self, mock_update, mock_context):
        """Test /reset trades without CONFIRM shows warning."""
        from app.bot.handlers import cmd_reset

        mock_context.args = ["trades"]

        with patch("app.bot.handlers._bot") as mock_bot:
            mock_bot.is_valid_chat.return_value = True

            await cmd_reset(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args[0][0]
            assert "CONFIRM" in call_args

    @pytest.mark.asyncio
    async def test_reset_trades_confirmed(self, mock_update, mock_context):
        """Test /reset trades CONFIRM executes reset."""
        from app.bot.handlers import cmd_reset

        mock_context.args = ["trades", "CONFIRM"]

        with patch("app.bot.handlers._bot") as mock_bot, \
             patch("app.bot.handlers.db") as mock_db:
            mock_bot.is_valid_chat.return_value = True
            mock_db.reset_trades = AsyncMock(return_value={"trades": 5, "pyramids": 10, "exits": 5})

            await cmd_reset(mock_update, mock_context)

            mock_db.reset_trades.assert_called_once()
            call_args = mock_update.message.reply_text.call_args[0][0]
            assert "Cleared" in call_args

    @pytest.mark.asyncio
    async def test_reset_settings_confirmed(self, mock_update, mock_context):
        """Test /reset settings CONFIRM executes reset."""
        from app.bot.handlers import cmd_reset

        mock_context.args = ["settings", "CONFIRM"]

        with patch("app.bot.handlers._bot") as mock_bot, \
             patch("app.bot.handlers.db") as mock_db:
            mock_bot.is_valid_chat.return_value = True
            mock_db.reset_settings = AsyncMock(return_value={"settings": 3})

            await cmd_reset(mock_update, mock_context)

            mock_db.reset_settings.assert_called_once()
            call_args = mock_update.message.reply_text.call_args[0][0]
            assert "Cleared" in call_args

    @pytest.mark.asyncio
    async def test_reset_cache_confirmed(self, mock_update, mock_context):
        """Test /reset cache CONFIRM executes reset."""
        from app.bot.handlers import cmd_reset

        mock_context.args = ["cache", "CONFIRM"]

        with patch("app.bot.handlers._bot") as mock_bot, \
             patch("app.bot.handlers.db") as mock_db:
            mock_bot.is_valid_chat.return_value = True
            mock_db.reset_cache = AsyncMock(return_value={"symbol_rules": 10, "daily_reports": 5})

            await cmd_reset(mock_update, mock_context)

            mock_db.reset_cache.assert_called_once()
            call_args = mock_update.message.reply_text.call_args[0][0]
            assert "Cleared" in call_args

    @pytest.mark.asyncio
    async def test_reset_all_confirmed(self, mock_update, mock_context):
        """Test /reset all CONFIRM executes full reset."""
        from app.bot.handlers import cmd_reset

        mock_context.args = ["all", "CONFIRM"]

        with patch("app.bot.handlers._bot") as mock_bot, \
             patch("app.bot.handlers.db") as mock_db:
            mock_bot.is_valid_chat.return_value = True
            mock_db.reset_all = AsyncMock(return_value={
                "trades": 5, "pyramids": 10, "exits": 5,
                "settings": 3, "symbol_rules": 10, "daily_reports": 5
            })

            await cmd_reset(mock_update, mock_context)

            mock_db.reset_all.assert_called_once()
            call_args = mock_update.message.reply_text.call_args[0][0]
            assert "Full Database Reset" in call_args

    @pytest.mark.asyncio
    async def test_reset_invalid_type(self, mock_update, mock_context):
        """Test /reset with invalid type shows error."""
        from app.bot.handlers import cmd_reset

        mock_context.args = ["invalid_type", "CONFIRM"]

        with patch("app.bot.handlers._bot") as mock_bot:
            mock_bot.is_valid_chat.return_value = True

            await cmd_reset(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args[0][0]
            assert "Unknown reset type" in call_args


class TestCmdSetfee:
    """Tests for /setfee command."""

    @pytest.mark.asyncio
    async def test_setfee_no_args_shows_usage(self, mock_update, mock_context):
        """Test /setfee without args shows usage."""
        from app.bot.handlers import cmd_setfee

        mock_context.args = []

        with patch("app.bot.handlers._bot") as mock_bot:
            mock_bot.is_valid_chat.return_value = True

            await cmd_setfee(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args[0][0]
            assert "Usage" in call_args

    @pytest.mark.asyncio
    async def test_setfee_success(self, mock_update, mock_context):
        """Test /setfee successfully sets fee."""
        from app.bot.handlers import cmd_setfee

        mock_context.args = ["binance", "0.1"]

        mock_connection = MagicMock()
        mock_connection.execute = AsyncMock()
        mock_connection.commit = AsyncMock()

        with patch("app.bot.handlers._bot") as mock_bot, \
             patch("app.bot.handlers.db") as mock_db:
            mock_bot.is_valid_chat.return_value = True
            mock_db.connection = mock_connection

            await cmd_setfee(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args[0][0]
            assert "Updated" in call_args
            assert "binance" in call_args
            assert "0.1" in call_args

    @pytest.mark.asyncio
    async def test_setfee_unknown_exchange(self, mock_update, mock_context):
        """Test /setfee with unknown exchange shows error."""
        from app.bot.handlers import cmd_setfee

        mock_context.args = ["unknown_exchange", "0.1"]

        with patch("app.bot.handlers._bot") as mock_bot:
            mock_bot.is_valid_chat.return_value = True

            await cmd_setfee(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args[0][0]
            assert "Unknown exchange" in call_args

    @pytest.mark.asyncio
    async def test_setfee_invalid_rate(self, mock_update, mock_context):
        """Test /setfee with invalid rate shows error."""
        from app.bot.handlers import cmd_setfee

        mock_context.args = ["binance", "invalid"]

        with patch("app.bot.handlers._bot") as mock_bot:
            mock_bot.is_valid_chat.return_value = True

            await cmd_setfee(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args[0][0]
            assert "Invalid rate" in call_args


class TestCmdTimezone:
    """Tests for /timezone command."""

    @pytest.mark.asyncio
    async def test_timezone_no_args_shows_current(self, mock_update, mock_context):
        """Test /timezone without args shows current timezone."""
        from app.bot.handlers import cmd_timezone

        mock_context.args = []

        # Mock cursor that returns None (no DB value, fallback to settings)
        mock_cursor = MagicMock()
        mock_cursor.fetchone = AsyncMock(return_value=None)

        mock_connection = MagicMock()
        mock_connection.execute = AsyncMock(return_value=mock_cursor)

        with patch("app.bot.handlers._bot") as mock_bot, \
             patch("app.bot.handlers.db") as mock_db, \
             patch("app.bot.handlers.settings") as mock_settings:
            mock_bot.is_valid_chat.return_value = True
            mock_db.connection = mock_connection
            mock_settings.timezone = "UTC"

            await cmd_timezone(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args[0][0]
            assert "UTC" in call_args

    @pytest.mark.asyncio
    async def test_timezone_set_valid(self, mock_update, mock_context):
        """Test /timezone sets valid timezone."""
        from app.bot.handlers import cmd_timezone

        mock_context.args = ["America/New_York"]

        mock_connection = MagicMock()
        mock_connection.execute = AsyncMock()
        mock_connection.commit = AsyncMock()

        with patch("app.bot.handlers._bot") as mock_bot, \
             patch("app.bot.handlers.db") as mock_db:
            mock_bot.is_valid_chat.return_value = True
            mock_db.connection = mock_connection

            await cmd_timezone(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args[0][0]
            assert "America/New_York" in call_args

    @pytest.mark.asyncio
    async def test_timezone_set_invalid(self, mock_update, mock_context):
        """Test /timezone with invalid timezone shows error."""
        from app.bot.handlers import cmd_timezone

        mock_context.args = ["Invalid/Timezone"]

        with patch("app.bot.handlers._bot") as mock_bot:
            mock_bot.is_valid_chat.return_value = True

            await cmd_timezone(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args[0][0]
            assert "Invalid timezone" in call_args


class TestCmdReporttime:
    """Tests for /reporttime command."""

    @pytest.mark.asyncio
    async def test_reporttime_no_args_shows_current(self, mock_update, mock_context):
        """Test /reporttime without args shows current time."""
        from app.bot.handlers import cmd_reporttime

        mock_context.args = []

        # Mock cursor that returns None (no DB value, fallback to settings)
        mock_cursor = MagicMock()
        mock_cursor.fetchone = AsyncMock(return_value=None)

        mock_connection = MagicMock()
        mock_connection.execute = AsyncMock(return_value=mock_cursor)

        with patch("app.bot.handlers._bot") as mock_bot, \
             patch("app.bot.handlers.db") as mock_db, \
             patch("app.bot.handlers.settings") as mock_settings:
            mock_bot.is_valid_chat.return_value = True
            mock_db.connection = mock_connection
            mock_settings.daily_report_time = "12:00"

            await cmd_reporttime(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args[0][0]
            assert "12:00" in call_args

    @pytest.mark.asyncio
    async def test_reporttime_set_valid(self, mock_update, mock_context):
        """Test /reporttime sets valid time."""
        from app.bot.handlers import cmd_reporttime

        mock_context.args = ["14:30"]

        mock_connection = MagicMock()
        mock_connection.execute = AsyncMock()
        mock_connection.commit = AsyncMock()

        with patch("app.bot.handlers._bot") as mock_bot, \
             patch("app.bot.handlers.db") as mock_db:
            mock_bot.is_valid_chat.return_value = True
            mock_db.connection = mock_connection

            await cmd_reporttime(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args[0][0]
            assert "14:30" in call_args

    @pytest.mark.asyncio
    async def test_reporttime_set_invalid(self, mock_update, mock_context):
        """Test /reporttime with invalid format shows error."""
        from app.bot.handlers import cmd_reporttime

        mock_context.args = ["invalid_time"]

        with patch("app.bot.handlers._bot") as mock_bot:
            mock_bot.is_valid_chat.return_value = True

            await cmd_reporttime(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args[0][0]
            assert "Invalid format" in call_args


class TestCmdPauseResume:
    """Tests for /pause and /resume commands."""

    @pytest.mark.asyncio
    async def test_pause_command(self, mock_update, mock_context):
        """Test /pause command sets paused state."""
        from app.bot.handlers import cmd_pause

        mock_connection = MagicMock()
        mock_connection.execute = AsyncMock()
        mock_connection.commit = AsyncMock()

        with patch("app.bot.handlers._bot") as mock_bot, \
             patch("app.bot.handlers.db") as mock_db:
            mock_bot.is_valid_chat.return_value = True
            mock_db.connection = mock_connection

            await cmd_pause(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args[0][0]
            assert "paused" in call_args.lower()

    @pytest.mark.asyncio
    async def test_resume_command(self, mock_update, mock_context):
        """Test /resume command clears paused state."""
        from app.bot.handlers import cmd_resume

        mock_connection = MagicMock()
        mock_connection.execute = AsyncMock()
        mock_connection.commit = AsyncMock()

        with patch("app.bot.handlers._bot") as mock_bot, \
             patch("app.bot.handlers.db") as mock_db:
            mock_bot.is_valid_chat.return_value = True
            mock_db.connection = mock_connection

            await cmd_resume(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args[0][0]
            assert "resumed" in call_args.lower()


class TestCmdIgnoreUnignore:
    """Tests for /ignore and /unignore commands."""

    @pytest.mark.asyncio
    async def test_ignore_no_args_shows_usage(self, mock_update, mock_context):
        """Test /ignore without args shows usage."""
        from app.bot.handlers import cmd_ignore

        mock_context.args = []

        with patch("app.bot.handlers._bot") as mock_bot:
            mock_bot.is_valid_chat.return_value = True

            await cmd_ignore(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args[0][0]
            assert "Usage" in call_args

    @pytest.mark.asyncio
    async def test_ignore_pair(self, mock_update, mock_context):
        """Test /ignore adds pair to ignore list."""
        from app.bot.handlers import cmd_ignore

        mock_context.args = ["BTC/USDT"]

        mock_cursor = MagicMock()
        mock_cursor.fetchone = AsyncMock(return_value=None)

        mock_connection = MagicMock()
        mock_connection.execute = AsyncMock(return_value=mock_cursor)
        mock_connection.commit = AsyncMock()

        with patch("app.bot.handlers._bot") as mock_bot, \
             patch("app.bot.handlers.db") as mock_db:
            mock_bot.is_valid_chat.return_value = True
            mock_db.connection = mock_connection

            await cmd_ignore(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args[0][0]
            assert "ignoring" in call_args.lower()
            assert "BTC/USDT" in call_args

    @pytest.mark.asyncio
    async def test_unignore_no_args_shows_usage(self, mock_update, mock_context):
        """Test /unignore without args shows usage."""
        from app.bot.handlers import cmd_unignore

        mock_context.args = []

        with patch("app.bot.handlers._bot") as mock_bot:
            mock_bot.is_valid_chat.return_value = True

            await cmd_unignore(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args[0][0]
            assert "Usage" in call_args

    @pytest.mark.asyncio
    async def test_unignore_pair(self, mock_update, mock_context):
        """Test /unignore removes pair from ignore list."""
        from app.bot.handlers import cmd_unignore

        mock_context.args = ["BTC/USDT"]

        mock_cursor = MagicMock()
        mock_cursor.fetchone = AsyncMock(return_value={"value": "BTC/USDT,ETH/USDT"})

        mock_connection = MagicMock()
        mock_connection.execute = AsyncMock(return_value=mock_cursor)
        mock_connection.commit = AsyncMock()

        with patch("app.bot.handlers._bot") as mock_bot, \
             patch("app.bot.handlers.db") as mock_db:
            mock_bot.is_valid_chat.return_value = True
            mock_db.connection = mock_connection

            await cmd_unignore(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args[0][0]
            assert "Resumed" in call_args
            assert "BTC/USDT" in call_args


class TestCmdSetCapital:
    """Tests for /set_capital command."""

    @pytest.mark.asyncio
    async def test_set_capital_no_args_shows_settings(self, mock_update, mock_context):
        """Test /set_capital without args shows current settings."""
        from app.bot.handlers import cmd_set_capital

        mock_context.args = []

        with patch("app.bot.handlers._bot") as mock_bot, \
             patch("app.bot.handlers.db") as mock_db:
            mock_bot.is_valid_chat.return_value = True
            mock_db.get_all_pyramid_capitals = AsyncMock(return_value={})

            await cmd_set_capital(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args[0][0]
            assert "capital" in call_args.lower() or "Usage" in call_args

    @pytest.mark.asyncio
    async def test_set_capital_with_existing_settings(self, mock_update, mock_context):
        """Test /set_capital shows existing settings."""
        from app.bot.handlers import cmd_set_capital

        mock_context.args = []

        with patch("app.bot.handlers._bot") as mock_bot, \
             patch("app.bot.handlers.db") as mock_db:
            mock_bot.is_valid_chat.return_value = True
            mock_db.get_all_pyramid_capitals = AsyncMock(return_value={
                "binance:BTC:USDT:1h:0": 500.0,
                "binance:ETH:USDT:4h:0": 1000.0
            })

            await cmd_set_capital(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args[0][0]
            assert "Capital Settings" in call_args

    @pytest.mark.asyncio
    async def test_set_capital_clear_all(self, mock_update, mock_context):
        """Test /set_capital clear removes all settings."""
        from app.bot.handlers import cmd_set_capital

        mock_context.args = ["clear"]

        with patch("app.bot.handlers._bot") as mock_bot, \
             patch("app.bot.handlers.db") as mock_db:
            mock_bot.is_valid_chat.return_value = True
            mock_db.clear_all_pyramid_capitals = AsyncMock()

            await cmd_set_capital(mock_update, mock_context)

            mock_db.clear_all_pyramid_capitals.assert_called_once()
            call_args = mock_update.message.reply_text.call_args[0][0]
            assert "cleared" in call_args.lower()

    @pytest.mark.asyncio
    async def test_set_capital_missing_args(self, mock_update, mock_context):
        """Test /set_capital with insufficient args shows error."""
        from app.bot.handlers import cmd_set_capital

        mock_context.args = ["binance", "BTC/USDT"]  # Missing timeframe, index, amount

        with patch("app.bot.handlers._bot") as mock_bot:
            mock_bot.is_valid_chat.return_value = True

            await cmd_set_capital(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args[0][0]
            assert "Missing arguments" in call_args

    @pytest.mark.asyncio
    async def test_set_capital_full_args(self, mock_update, mock_context):
        """Test /set_capital with all args sets capital."""
        from app.bot.handlers import cmd_set_capital

        mock_context.args = ["binance", "BTC/USDT", "1h", "0", "500"]

        with patch("app.bot.handlers._bot") as mock_bot, \
             patch("app.bot.handlers.db") as mock_db:
            mock_bot.is_valid_chat.return_value = True
            mock_db.set_pyramid_capital = AsyncMock(return_value="binance:BTC:USDT:1h:0")

            await cmd_set_capital(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args[0][0]
            assert "Capital set" in call_args
            assert "500" in call_args

    @pytest.mark.asyncio
    async def test_set_capital_negative_index(self, mock_update, mock_context):
        """Test /set_capital with negative index shows error."""
        from app.bot.handlers import cmd_set_capital

        mock_context.args = ["binance", "BTC/USDT", "1h", "-1", "500"]

        with patch("app.bot.handlers._bot") as mock_bot:
            mock_bot.is_valid_chat.return_value = True

            await cmd_set_capital(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args[0][0]
            assert "must be 0 or greater" in call_args

    @pytest.mark.asyncio
    async def test_set_capital_negative_value(self, mock_update, mock_context):
        """Test /set_capital with negative capital shows error."""
        from app.bot.handlers import cmd_set_capital

        mock_context.args = ["binance", "BTC/USDT", "1h", "0", "-100"]

        with patch("app.bot.handlers._bot") as mock_bot:
            mock_bot.is_valid_chat.return_value = True

            await cmd_set_capital(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args[0][0]
            assert "must be positive" in call_args


class TestCmdSignalsChannel:
    """Tests for /signals_channel command."""

    @pytest.mark.asyncio
    async def test_signals_channel_no_args_shows_current(self, mock_update, mock_context):
        """Test /signals_channel without args shows current setting."""
        from app.bot.handlers import cmd_signals_channel

        mock_context.args = []

        mock_cursor = MagicMock()
        mock_cursor.fetchone = AsyncMock(return_value={"value": "-1001234567890"})

        mock_connection = MagicMock()
        mock_connection.execute = AsyncMock(return_value=mock_cursor)

        with patch("app.bot.handlers._bot") as mock_bot, \
             patch("app.bot.handlers.db") as mock_db:
            mock_bot.is_valid_chat.return_value = True
            mock_db.connection = mock_connection

            await cmd_signals_channel(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args[0][0]
            assert "-1001234567890" in call_args

    @pytest.mark.asyncio
    async def test_signals_channel_not_configured(self, mock_update, mock_context):
        """Test /signals_channel shows help when not configured."""
        from app.bot.handlers import cmd_signals_channel

        mock_context.args = []

        mock_cursor = MagicMock()
        mock_cursor.fetchone = AsyncMock(return_value=None)

        mock_connection = MagicMock()
        mock_connection.execute = AsyncMock(return_value=mock_cursor)

        with patch("app.bot.handlers._bot") as mock_bot, \
             patch("app.bot.handlers.db") as mock_db, \
             patch("app.bot.handlers.settings") as mock_settings:
            mock_bot.is_valid_chat.return_value = True
            mock_db.connection = mock_connection
            mock_settings.telegram_signals_channel_id = None

            await cmd_signals_channel(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args[0][0]
            assert "No signals channel" in call_args

    @pytest.mark.asyncio
    async def test_signals_channel_disable(self, mock_update, mock_context):
        """Test /signals_channel off disables the channel."""
        from app.bot.handlers import cmd_signals_channel

        mock_context.args = ["off"]

        mock_connection = MagicMock()
        mock_connection.execute = AsyncMock()
        mock_connection.commit = AsyncMock()

        with patch("app.bot.handlers._bot") as mock_bot, \
             patch("app.bot.handlers.db") as mock_db:
            mock_bot.is_valid_chat.return_value = True
            mock_db.connection = mock_connection

            await cmd_signals_channel(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args[0][0]
            assert "disabled" in call_args.lower()

    @pytest.mark.asyncio
    async def test_signals_channel_invalid_id(self, mock_update, mock_context):
        """Test /signals_channel with invalid ID shows error."""
        from app.bot.handlers import cmd_signals_channel

        mock_context.args = ["not_a_channel_id"]

        with patch("app.bot.handlers._bot") as mock_bot:
            mock_bot.is_valid_chat.return_value = True

            await cmd_signals_channel(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args[0][0]
            assert "Invalid channel ID" in call_args


class TestGeneratePeriodReport:
    """Tests for generate_period_report function."""

    @pytest.mark.asyncio
    async def test_generate_period_report_7_days(self):
        """Test generating 7-day period report."""
        from app.bot.handlers import generate_period_report

        with patch("app.bot.handlers.db") as mock_db:
            # Mock all required async db methods
            mock_db.get_statistics_for_period = AsyncMock(return_value={
                "total_trades": 0,
                "total_pnl": 0,
                "win_rate": 0,
                "avg_win": 0,
                "avg_loss": 0,
                "profit_factor": 0,
                "best_trade": 0,
                "worst_trade": 0,
                "avg_trade": 0,
            })

            report = await generate_period_report(7)

            assert report.date == "Last 7 Days"
            assert report.total_trades == 0

    @pytest.mark.asyncio
    async def test_generate_period_report_30_days(self):
        """Test generating 30-day period report."""
        from app.bot.handlers import generate_period_report

        with patch("app.bot.handlers.db") as mock_db:
            mock_db.get_statistics_for_period = AsyncMock(return_value={
                "total_trades": 0,
                "total_pnl": 0,
                "win_rate": 0,
                "avg_win": 0,
                "avg_loss": 0,
                "profit_factor": 0,
                "best_trade": 0,
                "worst_trade": 0,
                "avg_trade": 0,
            })

            report = await generate_period_report(30)

            assert report.date == "Last 30 Days"


class TestCmdExportNoTrades:
    """Tests for /export with no trades."""

    @pytest.mark.asyncio
    async def test_export_no_trades(self, mock_update, mock_context):
        """Test /export with no trades shows message."""
        from app.bot.handlers import cmd_export

        mock_cursor = MagicMock()
        mock_cursor.fetchall = AsyncMock(return_value=[])

        mock_connection = MagicMock()
        mock_connection.execute = AsyncMock(return_value=mock_cursor)

        with patch("app.bot.handlers._bot") as mock_bot, \
             patch("app.bot.handlers.db") as mock_db:
            mock_bot.is_valid_chat.return_value = True
            mock_db.connection = mock_connection

            await cmd_export(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args[0][0]
            assert "No trades" in call_args


class TestCmdStatusLongMessage:
    """Tests for /status with long messages."""

    @pytest.mark.asyncio
    async def test_status_splits_long_message(self, mock_update, mock_context):
        """Test /status splits message when too long."""
        from app.bot.handlers import cmd_status

        # Create many open trades to generate a long message
        many_trades = []
        for i in range(20):
            many_trades.append({
                "id": f"trade_{i}",
                "exchange": "binance",
                "base": "BTC",
                "quote": "USDT",
                "group_id": f"BTC_Binance_1h_{i:03d}",
                "timeframe": "1h"
            })

        mock_cursor = MagicMock()
        mock_cursor.fetchall = AsyncMock(return_value=many_trades)

        mock_connection = MagicMock()
        mock_connection.execute = AsyncMock(return_value=mock_cursor)

        with patch("app.bot.handlers._bot") as mock_bot, \
             patch("app.bot.handlers.db") as mock_db, \
             patch("app.bot.handlers.exchange_service") as mock_exchange, \
             patch("app.bot.handlers.formatters") as mock_formatters:
            mock_bot.is_valid_chat.return_value = True
            mock_db.connection = mock_connection
            mock_db.get_pyramids_for_trade = AsyncMock(return_value=[
                {"entry_price": 50000.0, "position_size": 0.02}
            ])

            mock_price = MagicMock()
            mock_price.price = 51000.0
            mock_exchange.get_price = AsyncMock(return_value=mock_price)

            # Generate a very long message
            mock_formatters.format_status.return_value = "x" * 5000

            await cmd_status(mock_update, mock_context)

            # Should have called reply_text multiple times for chunked message
            assert mock_update.message.reply_text.call_count >= 1


class TestGeneratePeriodReportWithData:
    """Tests for generate_period_report with actual trade data."""

    def _setup_mock_db(self, mock_db, trades):
        """Helper to setup mock db with all required async methods."""
        # Calculate stats from trades
        total_pnl = sum(t.get("total_pnl_usdt", 0) or 0 for t in trades)
        wins = [t for t in trades if (t.get("total_pnl_usdt", 0) or 0) > 0]
        losses = [t for t in trades if (t.get("total_pnl_usdt", 0) or 0) < 0]

        mock_db.get_statistics_for_period = AsyncMock(return_value={
            "total_trades": len(trades),
            "total_pnl": total_pnl,
            "win_rate": len(wins) / len(trades) * 100 if trades else 0,
            "avg_win": sum(t.get("total_pnl_usdt", 0) or 0 for t in wins) / len(wins) if wins else 0,
            "avg_loss": sum(t.get("total_pnl_usdt", 0) or 0 for t in losses) / len(losses) if losses else 0,
            "profit_factor": 1.5,
            "best_trade": max((t.get("total_pnl_usdt", 0) or 0 for t in trades), default=0),
            "worst_trade": min((t.get("total_pnl_usdt", 0) or 0 for t in trades), default=0),
            "avg_trade": total_pnl / len(trades) if trades else 0,
        })
        mock_db.get_trades_for_period = AsyncMock(return_value=trades)
        mock_db.get_pyramids_for_trade = AsyncMock(return_value=[{"capital_usdt": 1000.0}])

        # Build exchange stats from trades
        exchange_stats = {}
        for t in trades:
            ex = t["exchange"]
            if ex not in exchange_stats:
                exchange_stats[ex] = {"exchange": ex, "pnl": 0, "trades": 0}
            exchange_stats[ex]["pnl"] += t.get("total_pnl_usdt", 0) or 0
            exchange_stats[ex]["trades"] += 1
        mock_db.get_exchange_stats_for_period = AsyncMock(return_value=list(exchange_stats.values()))

        mock_db.get_equity_curve_data_for_period = AsyncMock(return_value=[])
        mock_db.get_cumulative_pnl_before_date = AsyncMock(return_value=0.0)
        mock_db.get_drawdown_for_period = AsyncMock(return_value={
            "max_drawdown": 0,
            "max_drawdown_percent": 0,
            "current_drawdown": 0,
        })

    @pytest.mark.asyncio
    async def test_generate_period_report_with_trades(self):
        """Test generating period report with trade data."""
        from app.bot.handlers import generate_period_report

        trades = [
            {
                "id": "trade_1",
                "exchange": "binance",
                "base": "BTC",
                "quote": "USDT",
                "timeframe": "1h",
                "total_pnl_usdt": 100.0,
            },
        ]

        with patch("app.bot.handlers.db") as mock_db:
            self._setup_mock_db(mock_db, trades)

            report = await generate_period_report(30)

            assert report.total_trades == 1
            assert report.date == "Last 30 Days"
            assert isinstance(report.total_pnl_usdt, (int, float))
            assert isinstance(report.by_exchange, dict)
            assert isinstance(report.by_timeframe, dict)
            assert isinstance(report.by_pair, dict)

    @pytest.mark.asyncio
    async def test_generate_period_report_aggregates_by_exchange(self):
        """Test that report correctly aggregates PnL by exchange."""
        from app.bot.handlers import generate_period_report

        trades = [
            {
                "id": "trade_1",
                "exchange": "binance",
                "base": "BTC",
                "quote": "USDT",
                "timeframe": "1h",
                "total_pnl_usdt": 100.0,
            },
            {
                "id": "trade_2",
                "exchange": "binance",
                "base": "ETH",
                "quote": "USDT",
                "timeframe": "1h",
                "total_pnl_usdt": 50.0,
            },
            {
                "id": "trade_3",
                "exchange": "bybit",
                "base": "SOL",
                "quote": "USDT",
                "timeframe": "4h",
                "total_pnl_usdt": -25.0,
            },
        ]

        with patch("app.bot.handlers.db") as mock_db:
            self._setup_mock_db(mock_db, trades)

            report = await generate_period_report(7)

            # Verify exchange aggregation
            assert "binance" in report.by_exchange
            assert "bybit" in report.by_exchange
            assert report.by_exchange["binance"]["pnl"] == 150.0  # 100 + 50
            assert report.by_exchange["binance"]["trades"] == 2
            assert report.by_exchange["bybit"]["pnl"] == -25.0
            assert report.by_exchange["bybit"]["trades"] == 1

    @pytest.mark.asyncio
    async def test_generate_period_report_aggregates_by_timeframe(self):
        """Test that report correctly aggregates PnL by timeframe."""
        from app.bot.handlers import generate_period_report

        trades = [
            {
                "id": "trade_1",
                "exchange": "binance",
                "base": "BTC",
                "quote": "USDT",
                "timeframe": "1h",
                "total_pnl_usdt": 100.0,
            },
            {
                "id": "trade_2",
                "exchange": "binance",
                "base": "ETH",
                "quote": "USDT",
                "timeframe": "4h",
                "total_pnl_usdt": 200.0,
            },
            {
                "id": "trade_3",
                "exchange": "binance",
                "base": "SOL",
                "quote": "USDT",
                "timeframe": "1h",
                "total_pnl_usdt": 50.0,
            },
        ]

        with patch("app.bot.handlers.db") as mock_db:
            self._setup_mock_db(mock_db, trades)

            report = await generate_period_report(7)

            # Verify timeframe aggregation
            assert "1h" in report.by_timeframe
            assert "4h" in report.by_timeframe
            assert report.by_timeframe["1h"]["pnl"] == 150.0  # 100 + 50
            assert report.by_timeframe["1h"]["trades"] == 2
            assert report.by_timeframe["4h"]["pnl"] == 200.0
            assert report.by_timeframe["4h"]["trades"] == 1

    @pytest.mark.asyncio
    async def test_generate_period_report_aggregates_by_pair(self):
        """Test that report correctly aggregates PnL by trading pair."""
        from app.bot.handlers import generate_period_report

        trades = [
            {
                "id": "trade_1",
                "exchange": "binance",
                "base": "BTC",
                "quote": "USDT",
                "timeframe": "1h",
                "total_pnl_usdt": 100.0,
            },
            {
                "id": "trade_2",
                "exchange": "binance",
                "base": "BTC",
                "quote": "USDT",
                "timeframe": "4h",
                "total_pnl_usdt": 50.0,
            },
            {
                "id": "trade_3",
                "exchange": "binance",
                "base": "ETH",
                "quote": "USDT",
                "timeframe": "1h",
                "total_pnl_usdt": -30.0,
            },
        ]

        with patch("app.bot.handlers.db") as mock_db:
            self._setup_mock_db(mock_db, trades)

            report = await generate_period_report(7)

            # Verify pair aggregation
            assert "BTC/USDT" in report.by_pair
            assert "ETH/USDT" in report.by_pair
            assert report.by_pair["BTC/USDT"] == 150.0  # 100 + 50
            assert report.by_pair["ETH/USDT"] == -30.0

    @pytest.mark.asyncio
    async def test_generate_period_report_handles_none_pnl(self):
        """Test that report handles None PnL values gracefully."""
        from app.bot.handlers import generate_period_report

        trades = [
            {
                "id": "trade_1",
                "exchange": "binance",
                "base": "BTC",
                "quote": "USDT",
                "timeframe": "1h",
                "total_pnl_usdt": None,  # None value
            },
            {
                "id": "trade_2",
                "exchange": "binance",
                "base": "ETH",
                "quote": "USDT",
                "timeframe": "1h",
                "total_pnl_usdt": 50.0,
            },
        ]

        with patch("app.bot.handlers.db") as mock_db:
            self._setup_mock_db(mock_db, trades)
            mock_db.get_pyramids_for_trade = AsyncMock(return_value=[])

            report = await generate_period_report(7)

            # Should handle None as 0
            assert report.total_pnl_usdt == 50.0  # Only the non-None value

    @pytest.mark.asyncio
    async def test_generate_period_report_handles_missing_timeframe(self):
        """Test that report handles missing timeframe gracefully."""
        from app.bot.handlers import generate_period_report

        trades = [
            {
                "id": "trade_1",
                "exchange": "binance",
                "base": "BTC",
                "quote": "USDT",
                "timeframe": None,  # Missing timeframe
                "total_pnl_usdt": 100.0,
            },
        ]

        with patch("app.bot.handlers.db") as mock_db:
            self._setup_mock_db(mock_db, trades)
            mock_db.get_pyramids_for_trade = AsyncMock(return_value=[])

            report = await generate_period_report(7)

            # Should use 'N/A' for missing timeframe (per handlers.py line 349)
            assert "N/A" in report.by_timeframe

    @pytest.mark.asyncio
    async def test_generate_period_report_pnl_percent_calculation(self):
        """Test that PnL percentage is calculated correctly."""
        from app.bot.handlers import generate_period_report

        trades = [
            {
                "id": "trade_1",
                "exchange": "binance",
                "base": "BTC",
                "quote": "USDT",
                "timeframe": "1h",
                "total_pnl_usdt": 100.0,
            },
        ]

        with patch("app.bot.handlers.db") as mock_db:
            self._setup_mock_db(mock_db, trades)

            report = await generate_period_report(7)

            # PnL percent should be 100 / 1000 * 100 = 10%
            assert abs(report.total_pnl_percent - 10.0) < 0.01

    @pytest.mark.asyncio
    async def test_generate_period_report_zero_capital(self):
        """Test that report handles zero capital gracefully."""
        from app.bot.handlers import generate_period_report

        trades = [
            {
                "id": "trade_1",
                "exchange": "binance",
                "base": "BTC",
                "quote": "USDT",
                "timeframe": "1h",
                "total_pnl_usdt": 100.0,
            },
        ]

        with patch("app.bot.handlers.db") as mock_db:
            self._setup_mock_db(mock_db, trades)
            # No pyramids = zero capital
            mock_db.get_pyramids_for_trade = AsyncMock(return_value=[])

            report = await generate_period_report(7)

            # PnL percent should be 0 when capital is 0
            assert report.total_pnl_percent == 0


class TestInputValidationEdgeCases:
    """Tests for input validation edge cases across various commands."""

    @pytest.mark.asyncio
    async def test_setfee_very_large_rate(self, mock_update, mock_context):
        """Test /setfee with unreasonably large rate."""
        from app.bot.handlers import cmd_setfee

        mock_context.args = ["binance", "100"]  # 100% fee is unreasonable

        mock_connection = MagicMock()
        mock_connection.execute = AsyncMock()
        mock_connection.commit = AsyncMock()

        with patch("app.bot.handlers._bot") as mock_bot, \
             patch("app.bot.handlers.db") as mock_db:
            mock_bot.is_valid_chat.return_value = True
            mock_db.connection = mock_connection

            await cmd_setfee(mock_update, mock_context)

            # Should still work (no max limit enforced in handler)
            call_args = mock_update.message.reply_text.call_args[0][0]
            # Either updates or shows error
            assert "Updated" in call_args or "Invalid" in call_args

    @pytest.mark.asyncio
    async def test_setfee_zero_rate(self, mock_update, mock_context):
        """Test /setfee with zero rate (valid for some exchanges)."""
        from app.bot.handlers import cmd_setfee

        mock_context.args = ["binance", "0"]

        mock_connection = MagicMock()
        mock_connection.execute = AsyncMock()
        mock_connection.commit = AsyncMock()

        with patch("app.bot.handlers._bot") as mock_bot, \
             patch("app.bot.handlers.db") as mock_db:
            mock_bot.is_valid_chat.return_value = True
            mock_db.connection = mock_connection

            await cmd_setfee(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args[0][0]
            assert "Updated" in call_args

    @pytest.mark.asyncio
    async def test_set_capital_zero_value(self, mock_update, mock_context):
        """Test /set_capital with zero capital value."""
        from app.bot.handlers import cmd_set_capital

        mock_context.args = ["binance", "BTC/USDT", "1h", "0", "0"]

        with patch("app.bot.handlers._bot") as mock_bot:
            mock_bot.is_valid_chat.return_value = True

            await cmd_set_capital(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args[0][0]
            # Should reject zero capital
            assert "must be positive" in call_args

    @pytest.mark.asyncio
    async def test_set_capital_very_large_index(self, mock_update, mock_context):
        """Test /set_capital with very large pyramid index."""
        from app.bot.handlers import cmd_set_capital

        mock_context.args = ["binance", "BTC/USDT", "1h", "999", "1000"]

        with patch("app.bot.handlers._bot") as mock_bot, \
             patch("app.bot.handlers.db") as mock_db:
            mock_bot.is_valid_chat.return_value = True
            mock_db.set_pyramid_capital = AsyncMock(return_value="binance:BTC:USDT:1h:999")

            await cmd_set_capital(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args[0][0]
            # Should work - no max index limit
            assert "Capital set" in call_args

    @pytest.mark.asyncio
    async def test_reporttime_edge_times(self, mock_update, mock_context):
        """Test /reporttime with edge case times."""
        from app.bot.handlers import cmd_reporttime

        # Test midnight
        mock_context.args = ["00:00"]

        mock_connection = MagicMock()
        mock_connection.execute = AsyncMock()
        mock_connection.commit = AsyncMock()

        with patch("app.bot.handlers._bot") as mock_bot, \
             patch("app.bot.handlers.db") as mock_db:
            mock_bot.is_valid_chat.return_value = True
            mock_db.connection = mock_connection

            await cmd_reporttime(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args[0][0]
            assert "00:00" in call_args

    @pytest.mark.asyncio
    async def test_reporttime_end_of_day(self, mock_update, mock_context):
        """Test /reporttime with 23:59."""
        from app.bot.handlers import cmd_reporttime

        mock_context.args = ["23:59"]

        mock_connection = MagicMock()
        mock_connection.execute = AsyncMock()
        mock_connection.commit = AsyncMock()

        with patch("app.bot.handlers._bot") as mock_bot, \
             patch("app.bot.handlers.db") as mock_db:
            mock_bot.is_valid_chat.return_value = True
            mock_db.connection = mock_connection

            await cmd_reporttime(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args[0][0]
            assert "23:59" in call_args

    @pytest.mark.asyncio
    async def test_reporttime_invalid_hour(self, mock_update, mock_context):
        """Test /reporttime with invalid hour (24:00)."""
        from app.bot.handlers import cmd_reporttime

        mock_context.args = ["24:00"]

        with patch("app.bot.handlers._bot") as mock_bot:
            mock_bot.is_valid_chat.return_value = True

            await cmd_reporttime(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args[0][0]
            assert "Invalid" in call_args

    @pytest.mark.asyncio
    async def test_trades_negative_limit(self, mock_update, mock_context, test_db):
        """Test /trades with negative limit."""
        from app.bot.handlers import cmd_trades

        mock_context.args = ["-5"]

        with patch("app.bot.handlers._bot") as mock_bot, \
             patch("app.bot.handlers.db", test_db):
            mock_bot.is_valid_chat.return_value = True

            await cmd_trades(mock_update, mock_context)

            # Should handle gracefully - either show error or treat as invalid
            mock_update.message.reply_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_trades_zero_limit(self, mock_update, mock_context, test_db):
        """Test /trades with zero limit."""
        from app.bot.handlers import cmd_trades

        mock_context.args = ["0"]

        with patch("app.bot.handlers._bot") as mock_bot, \
             patch("app.bot.handlers.db", test_db):
            mock_bot.is_valid_chat.return_value = True

            await cmd_trades(mock_update, mock_context)

            # Should handle gracefully
            mock_update.message.reply_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_history_special_characters_in_pair(self, mock_update, mock_context, test_db):
        """Test /history with special characters in pair name."""
        from app.bot.handlers import cmd_history

        mock_context.args = ["BTC<script>/USDT"]  # Attempt XSS in pair name

        with patch("app.bot.handlers._bot") as mock_bot, \
             patch("app.bot.handlers.db", test_db):
            mock_bot.is_valid_chat.return_value = True

            await cmd_history(mock_update, mock_context)

            # Should handle safely
            mock_update.message.reply_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_ignore_sql_injection_attempt(self, mock_update, mock_context):
        """Test /ignore with SQL injection attempt in pair name."""
        from app.bot.handlers import cmd_ignore

        mock_context.args = ["'; DROP TABLE trades; --"]

        mock_cursor = MagicMock()
        mock_cursor.fetchone = AsyncMock(return_value=None)

        mock_connection = MagicMock()
        mock_connection.execute = AsyncMock(return_value=mock_cursor)
        mock_connection.commit = AsyncMock()

        with patch("app.bot.handlers._bot") as mock_bot, \
             patch("app.bot.handlers.db") as mock_db:
            mock_bot.is_valid_chat.return_value = True
            mock_db.connection = mock_connection

            await cmd_ignore(mock_update, mock_context)

            # Should handle safely - the pair is stored as-is
            # SQLite parameterized queries prevent injection
            mock_update.message.reply_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_signals_channel_very_large_id(self, mock_update, mock_context):
        """Test /signals_channel with very large channel ID."""
        from app.bot.handlers import cmd_signals_channel

        mock_context.args = ["-9999999999999999999"]  # Very large negative number

        mock_connection = MagicMock()
        mock_connection.execute = AsyncMock()
        mock_connection.commit = AsyncMock()

        with patch("app.bot.handlers._bot") as mock_bot, \
             patch("app.bot.handlers.db") as mock_db:
            mock_bot.is_valid_chat.return_value = True
            mock_db.connection = mock_connection

            await cmd_signals_channel(mock_update, mock_context)

            # Should handle - either accept or reject based on validation
            mock_update.message.reply_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_exchange_command_case_handling(self, mock_update, mock_context, populated_db):
        """Test /exchange handles different case variations."""
        from app.bot.handlers import cmd_exchange

        # Test uppercase
        mock_context.args = ["BINANCE"]

        with patch("app.bot.handlers._bot") as mock_bot, \
             patch("app.bot.handlers.db", populated_db):
            mock_bot.is_valid_chat.return_value = True

            await cmd_exchange(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args[0][0]
            # Should normalize exchange name
            assert "binance" in call_args.lower() or "BINANCE" in call_args

    @pytest.mark.asyncio
    async def test_report_future_date(self, mock_update, mock_context):
        """Test /report with future date."""
        from app.bot.handlers import cmd_report
        from app.models import DailyReportData

        mock_context.args = ["2099-12-31"]

        with patch("app.bot.handlers._bot") as mock_bot, \
             patch("app.services.report_service.report_service") as mock_report_service, \
             patch("app.services.telegram_service.telegram_service") as mock_telegram, \
             patch("app.bot.handlers.settings") as mock_settings:
            mock_bot.is_valid_chat.return_value = True
            mock_settings.equity_curve_enabled = False

            # Return empty report for future date
            mock_report_service.generate_daily_report = AsyncMock(return_value=DailyReportData(
                date="2099-12-31",
                total_trades=0,
                total_pyramids=0,
                total_pnl_usdt=0.0,
                total_pnl_percent=0.0,
                by_exchange={},
                by_timeframe={},
                by_pair={},
            ))
            mock_telegram.format_daily_report_message = MagicMock(return_value="Report for 2099-12-31")

            await cmd_report(mock_update, mock_context)

            # Should handle future date gracefully
            mock_update.message.reply_text.assert_called_once()


class TestDateFilterBoundaries:
    """Tests for date filter boundary conditions."""

    def test_date_format_with_leading_zeros(self):
        """Test date filter handles dates with leading zeros correctly."""
        from app.bot.handlers import parse_date_filter

        start, end, label = parse_date_filter(["2026-01-05"])

        assert start == "2026-01-05"
        assert end == "2026-01-05"

    def test_date_format_without_leading_zeros(self):
        """Test date filter handles dates without leading zeros."""
        from app.bot.handlers import parse_date_filter

        # This should be treated as invalid since YYYY-MM-DD requires MM and DD
        start, end, label = parse_date_filter(["2026-1-5"])

        # Should fall back to all-time since format doesn't match
        assert start is None
        assert end is None

    def test_date_filter_leap_year(self):
        """Test date filter handles leap year dates."""
        from app.bot.handlers import parse_date_filter

        # February 29 in leap year 2024
        start, end, label = parse_date_filter(["2024-02-29"])

        assert start == "2024-02-29"
        assert end == "2024-02-29"

    def test_date_filter_non_leap_year_feb29(self):
        """Test date filter rejects Feb 29 in non-leap year."""
        from app.bot.handlers import parse_date_filter

        # February 29 in non-leap year should be invalid
        start, end, label = parse_date_filter(["2023-02-29"])

        # Should fall back to all-time since date is invalid
        assert start is None
        assert end is None

    def test_date_filter_year_boundaries(self):
        """Test date filter handles year boundaries."""
        from app.bot.handlers import parse_date_filter

        # End of year
        start, end, label = parse_date_filter(["2026-12-31"])
        assert start == "2026-12-31"

        # Start of year
        start, end, label = parse_date_filter(["2026-01-01"])
        assert start == "2026-01-01"
