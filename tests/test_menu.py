"""
Tests for interactive menu system in app/bot/menu.py
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio


class TestMenuKeyboards:
    """Tests for keyboard generation functions."""

    def test_get_main_menu(self):
        """Test main menu keyboard generation."""
        from app.bot.menu import get_main_menu

        keyboard = get_main_menu()

        assert keyboard is not None
        # Should have 3 rows
        assert len(keyboard.inline_keyboard) == 3

        # Check first row has Performance and PnL
        row1 = keyboard.inline_keyboard[0]
        assert len(row1) == 2
        assert "Performance" in row1[0].text
        assert "PnL" in row1[1].text

        # Check second row has Trades and Settings
        row2 = keyboard.inline_keyboard[1]
        assert "Trades" in row2[0].text
        assert "Settings" in row2[1].text

        # Check third row has Export and Help
        row3 = keyboard.inline_keyboard[2]
        assert "Export" in row3[0].text
        assert "Help" in row3[1].text

    def test_get_performance_menu_default(self):
        """Test performance menu with default selection."""
        from app.bot.menu import get_performance_menu

        keyboard = get_performance_menu()

        assert keyboard is not None
        # Should have period row, command rows, and back button
        assert len(keyboard.inline_keyboard) >= 5

        # Check period row
        period_row = keyboard.inline_keyboard[0]
        assert len(period_row) == 4
        assert any("All" in btn.text for btn in period_row)

    def test_get_performance_menu_with_selection(self):
        """Test performance menu with specific period selected."""
        from app.bot.menu import get_performance_menu

        keyboard = get_performance_menu(selected_period="today")

        # Check that Today has checkmark
        period_row = keyboard.inline_keyboard[0]
        today_btn = next(btn for btn in period_row if "Today" in btn.text)
        assert "✓" in today_btn.text

    def test_get_pnl_menu_default(self):
        """Test PnL menu with default selection."""
        from app.bot.menu import get_pnl_menu

        keyboard = get_pnl_menu()

        assert keyboard is not None
        # Should have period row, show button, and back button
        assert len(keyboard.inline_keyboard) >= 3

    def test_get_pnl_menu_with_selection(self):
        """Test PnL menu with specific period selected."""
        from app.bot.menu import get_pnl_menu

        keyboard = get_pnl_menu(selected_period="week")

        period_row = keyboard.inline_keyboard[0]
        week_btn = next(btn for btn in period_row if "Week" in btn.text)
        assert "✓" in week_btn.text

    def test_get_trades_menu(self):
        """Test trades menu keyboard generation."""
        from app.bot.menu import get_trades_menu

        keyboard = get_trades_menu()

        assert keyboard is not None
        # Should have option rows and back button
        assert len(keyboard.inline_keyboard) >= 4

        # Check for expected buttons
        all_buttons = [btn for row in keyboard.inline_keyboard for btn in row]
        button_texts = [btn.text for btn in all_buttons]

        assert any("Open Positions" in text for text in button_texts)
        assert any("Live" in text for text in button_texts)
        assert any("Recent" in text for text in button_texts)
        assert any("Back" in text for text in button_texts)

    def test_get_settings_menu(self):
        """Test settings menu keyboard generation."""
        from app.bot.menu import get_settings_menu

        keyboard = get_settings_menu()

        assert keyboard is not None

        all_buttons = [btn for row in keyboard.inline_keyboard for btn in row]
        button_texts = [btn.text for btn in all_buttons]

        assert any("Timezone" in text for text in button_texts)
        assert any("Fees" in text for text in button_texts)
        assert any("Pause" in text for text in button_texts)
        assert any("Resume" in text for text in button_texts)


class TestMenuState:
    """Tests for menu state management."""

    def test_get_user_period_default(self):
        """Test getting default period for new user."""
        from app.bot.menu import get_user_period, _user_periods

        # Clear state
        _user_periods.clear()

        period = get_user_period(chat_id=12345, menu="performance")
        assert period == "all"

    def test_set_and_get_user_period(self):
        """Test setting and getting user period."""
        from app.bot.menu import get_user_period, set_user_period, _user_periods

        # Clear state
        _user_periods.clear()

        set_user_period(chat_id=12345, menu="performance", period="today")
        period = get_user_period(chat_id=12345, menu="performance")

        assert period == "today"

    def test_different_menus_different_periods(self):
        """Test that different menus can have different periods."""
        from app.bot.menu import get_user_period, set_user_period, _user_periods

        # Clear state
        _user_periods.clear()

        set_user_period(chat_id=12345, menu="performance", period="today")
        set_user_period(chat_id=12345, menu="pnl", period="week")

        assert get_user_period(12345, "performance") == "today"
        assert get_user_period(12345, "pnl") == "week"

    def test_period_to_args(self):
        """Test converting period to command args."""
        from app.bot.menu import period_to_args

        assert period_to_args("all") == []
        assert period_to_args("today") == ["today"]
        assert period_to_args("week") == ["week"]
        assert period_to_args("month") == ["month"]


class TestCallbackAdapters:
    """Tests for callback adapters."""

    def test_callback_message_adapter(self):
        """Test CallbackMessageAdapter initialization."""
        from app.bot.menu import CallbackMessageAdapter

        mock_query = MagicMock()
        mock_query.message.chat_id = 12345

        adapter = CallbackMessageAdapter(mock_query)

        assert adapter.chat_id == 12345

    def test_callback_update_adapter(self):
        """Test CallbackUpdateAdapter initialization."""
        from app.bot.menu import CallbackUpdateAdapter

        mock_query = MagicMock()
        mock_query.message.chat = MagicMock(id=12345)

        adapter = CallbackUpdateAdapter(mock_query)

        assert adapter.effective_chat == mock_query.message.chat


class TestMenuCallbackHandler:
    """Tests for menu callback handler."""

    @pytest.fixture
    def mock_callback_update(self):
        """Create a mock callback update."""
        update = MagicMock()
        update.callback_query.message.chat_id = -1001234567890
        update.callback_query.message.chat = MagicMock(id=-1001234567890)
        update.callback_query.answer = AsyncMock()
        update.callback_query.edit_message_text = AsyncMock()
        update.callback_query.message.reply_text = AsyncMock()
        return update

    @pytest.fixture
    def mock_callback_context(self):
        """Create a mock callback context."""
        context = MagicMock()
        context.args = []
        return context

    @pytest.mark.asyncio
    async def test_main_menu_callback(self, mock_callback_update, mock_callback_context):
        """Test navigating to main menu."""
        from app.bot.menu import menu_callback_handler, _bot

        mock_callback_update.callback_query.data = "menu_main"

        with patch("app.bot.menu._bot") as mock_bot:
            mock_bot.is_valid_chat.return_value = True

            await menu_callback_handler(mock_callback_update, mock_callback_context)

            mock_callback_update.callback_query.answer.assert_called_once()
            mock_callback_update.callback_query.edit_message_text.assert_called_once()
            call_args = mock_callback_update.callback_query.edit_message_text.call_args
            assert "Menu" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_performance_menu_callback(self, mock_callback_update, mock_callback_context):
        """Test navigating to performance menu."""
        from app.bot.menu import menu_callback_handler

        mock_callback_update.callback_query.data = "menu_performance"

        with patch("app.bot.menu._bot") as mock_bot:
            mock_bot.is_valid_chat.return_value = True

            await menu_callback_handler(mock_callback_update, mock_callback_context)

            call_args = mock_callback_update.callback_query.edit_message_text.call_args
            assert "Performance" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_pnl_menu_callback(self, mock_callback_update, mock_callback_context):
        """Test navigating to PnL menu."""
        from app.bot.menu import menu_callback_handler

        mock_callback_update.callback_query.data = "menu_pnl"

        with patch("app.bot.menu._bot") as mock_bot:
            mock_bot.is_valid_chat.return_value = True

            await menu_callback_handler(mock_callback_update, mock_callback_context)

            call_args = mock_callback_update.callback_query.edit_message_text.call_args
            assert "PnL" in call_args[0][0] or "Profit" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_trades_menu_callback(self, mock_callback_update, mock_callback_context):
        """Test navigating to trades menu."""
        from app.bot.menu import menu_callback_handler

        mock_callback_update.callback_query.data = "menu_trades"

        with patch("app.bot.menu._bot") as mock_bot:
            mock_bot.is_valid_chat.return_value = True

            await menu_callback_handler(mock_callback_update, mock_callback_context)

            call_args = mock_callback_update.callback_query.edit_message_text.call_args
            assert "Trade" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_settings_menu_callback(self, mock_callback_update, mock_callback_context):
        """Test navigating to settings menu."""
        from app.bot.menu import menu_callback_handler

        mock_callback_update.callback_query.data = "menu_settings"

        with patch("app.bot.menu._bot") as mock_bot:
            mock_bot.is_valid_chat.return_value = True

            await menu_callback_handler(mock_callback_update, mock_callback_context)

            call_args = mock_callback_update.callback_query.edit_message_text.call_args
            assert "Settings" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_period_selection_callback(self, mock_callback_update, mock_callback_context):
        """Test period selection updates menu state."""
        from app.bot.menu import menu_callback_handler, get_user_period, _user_periods

        # Clear state
        _user_periods.clear()

        mock_callback_update.callback_query.data = "period_today"

        with patch("app.bot.menu._bot") as mock_bot:
            mock_bot.is_valid_chat.return_value = True

            await menu_callback_handler(mock_callback_update, mock_callback_context)

            # Verify period was set
            period = get_user_period(-1001234567890, "performance")
            assert period == "today"

    @pytest.mark.asyncio
    async def test_invalid_chat_rejected(self, mock_callback_update, mock_callback_context):
        """Test that callbacks from invalid chats are rejected."""
        from app.bot.menu import menu_callback_handler

        mock_callback_update.callback_query.data = "menu_main"

        with patch("app.bot.menu._bot") as mock_bot:
            mock_bot.is_valid_chat.return_value = False

            await menu_callback_handler(mock_callback_update, mock_callback_context)

            # Should not edit message when chat is invalid
            mock_callback_update.callback_query.edit_message_text.assert_not_called()


class TestCmdMenu:
    """Tests for /menu command."""

    @pytest.mark.asyncio
    async def test_menu_command(self, mock_update, mock_context):
        """Test /menu command shows main menu."""
        from app.bot.menu import cmd_menu

        with patch("app.bot.menu._bot") as mock_bot:
            mock_bot.is_valid_chat.return_value = True

            await cmd_menu(mock_update, mock_context)

            mock_update.message.reply_text.assert_called_once()
            call_args = mock_update.message.reply_text.call_args
            assert "Menu" in call_args[0][0]
            assert "reply_markup" in call_args[1]

    @pytest.mark.asyncio
    async def test_menu_command_invalid_chat(self, mock_update, mock_context):
        """Test /menu command rejected for invalid chat."""
        from app.bot.menu import cmd_menu

        with patch("app.bot.menu._bot") as mock_bot:
            mock_bot.is_valid_chat.return_value = False

            await cmd_menu(mock_update, mock_context)

            mock_update.message.reply_text.assert_not_called()


class TestSetupMenuHandlers:
    """Tests for setup_menu_handlers function."""

    def test_setup_menu_handlers(self):
        """Test that menu handlers are registered."""
        from app.bot.menu import setup_menu_handlers

        mock_app = MagicMock()
        mock_bot = MagicMock()

        setup_menu_handlers(mock_app, mock_bot)

        # Should add command handler for /menu
        assert mock_app.add_handler.call_count >= 2  # menu command + callback handler

    def test_setup_stores_bot_reference(self):
        """Test that setup stores bot reference for validation."""
        from app.bot.menu import setup_menu_handlers, _bot

        mock_app = MagicMock()
        mock_bot = MagicMock()

        setup_menu_handlers(mock_app, mock_bot)

        # After setup, _bot should reference mock_bot
        from app.bot.menu import _bot as stored_bot
        assert stored_bot == mock_bot


class TestCallbackCommandExecution:
    """Tests for callback commands that execute handlers."""

    @pytest.fixture
    def mock_callback_update(self):
        """Create a mock callback update."""
        update = MagicMock()
        update.callback_query.message.chat_id = -1001234567890
        update.callback_query.message.chat = MagicMock(id=-1001234567890)
        update.callback_query.answer = AsyncMock()
        update.callback_query.edit_message_text = AsyncMock()
        update.callback_query.message.reply_text = AsyncMock()
        update.callback_query.message.reply_photo = AsyncMock()
        update.callback_query.message.reply_document = AsyncMock()
        return update

    @pytest.fixture
    def mock_callback_context(self):
        """Create a mock callback context."""
        context = MagicMock()
        context.args = []
        return context

    @pytest.mark.asyncio
    async def test_perf_stats_callback(self, mock_callback_update, mock_callback_context):
        """Test perf_stats callback executes stats command."""
        from app.bot.menu import menu_callback_handler

        mock_callback_update.callback_query.data = "perf_stats"

        with patch("app.bot.menu._bot") as mock_bot, \
             patch("app.bot.handlers.cmd_stats", new_callable=AsyncMock) as mock_cmd:
            mock_bot.is_valid_chat.return_value = True

            await menu_callback_handler(mock_callback_update, mock_callback_context)

            mock_cmd.assert_called_once()

    @pytest.mark.asyncio
    async def test_perf_best_callback(self, mock_callback_update, mock_callback_context):
        """Test perf_best callback executes best command."""
        from app.bot.menu import menu_callback_handler

        mock_callback_update.callback_query.data = "perf_best"

        with patch("app.bot.menu._bot") as mock_bot, \
             patch("app.bot.handlers.cmd_best", new_callable=AsyncMock) as mock_cmd:
            mock_bot.is_valid_chat.return_value = True

            await menu_callback_handler(mock_callback_update, mock_callback_context)

            mock_cmd.assert_called_once()

    @pytest.mark.asyncio
    async def test_perf_worst_callback(self, mock_callback_update, mock_callback_context):
        """Test perf_worst callback executes worst command."""
        from app.bot.menu import menu_callback_handler

        mock_callback_update.callback_query.data = "perf_worst"

        with patch("app.bot.menu._bot") as mock_bot, \
             patch("app.bot.handlers.cmd_worst", new_callable=AsyncMock) as mock_cmd:
            mock_bot.is_valid_chat.return_value = True

            await menu_callback_handler(mock_callback_update, mock_callback_context)

            mock_cmd.assert_called_once()

    @pytest.mark.asyncio
    async def test_perf_drawdown_callback(self, mock_callback_update, mock_callback_context):
        """Test perf_drawdown callback executes drawdown command."""
        from app.bot.menu import menu_callback_handler

        mock_callback_update.callback_query.data = "perf_drawdown"

        with patch("app.bot.menu._bot") as mock_bot, \
             patch("app.bot.handlers.cmd_drawdown", new_callable=AsyncMock) as mock_cmd:
            mock_bot.is_valid_chat.return_value = True

            await menu_callback_handler(mock_callback_update, mock_callback_context)

            mock_cmd.assert_called_once()

    @pytest.mark.asyncio
    async def test_perf_streak_callback(self, mock_callback_update, mock_callback_context):
        """Test perf_streak callback executes streak command."""
        from app.bot.menu import menu_callback_handler

        mock_callback_update.callback_query.data = "perf_streak"

        with patch("app.bot.menu._bot") as mock_bot, \
             patch("app.bot.handlers.cmd_streak", new_callable=AsyncMock) as mock_cmd:
            mock_bot.is_valid_chat.return_value = True

            await menu_callback_handler(mock_callback_update, mock_callback_context)

            mock_cmd.assert_called_once()

    @pytest.mark.asyncio
    async def test_pnl_show_callback(self, mock_callback_update, mock_callback_context):
        """Test pnl_show callback executes pnl command."""
        from app.bot.menu import menu_callback_handler

        mock_callback_update.callback_query.data = "pnl_show"

        with patch("app.bot.menu._bot") as mock_bot, \
             patch("app.bot.handlers.cmd_pnl", new_callable=AsyncMock) as mock_cmd:
            mock_bot.is_valid_chat.return_value = True

            await menu_callback_handler(mock_callback_update, mock_callback_context)

            mock_cmd.assert_called_once()

    @pytest.mark.asyncio
    async def test_trades_status_callback(self, mock_callback_update, mock_callback_context):
        """Test trades_status callback executes status command."""
        from app.bot.menu import menu_callback_handler

        mock_callback_update.callback_query.data = "trades_status"

        with patch("app.bot.menu._bot") as mock_bot, \
             patch("app.bot.handlers.cmd_status", new_callable=AsyncMock) as mock_cmd:
            mock_bot.is_valid_chat.return_value = True

            await menu_callback_handler(mock_callback_update, mock_callback_context)

            mock_cmd.assert_called_once()

    @pytest.mark.asyncio
    async def test_trades_live_callback(self, mock_callback_update, mock_callback_context):
        """Test trades_live callback executes live command."""
        from app.bot.menu import menu_callback_handler

        mock_callback_update.callback_query.data = "trades_live"

        with patch("app.bot.menu._bot") as mock_bot, \
             patch("app.bot.handlers.cmd_live", new_callable=AsyncMock) as mock_cmd:
            mock_bot.is_valid_chat.return_value = True

            await menu_callback_handler(mock_callback_update, mock_callback_context)

            mock_cmd.assert_called_once()

    @pytest.mark.asyncio
    async def test_trades_recent_callback(self, mock_callback_update, mock_callback_context):
        """Test trades_recent callback executes trades command."""
        from app.bot.menu import menu_callback_handler

        mock_callback_update.callback_query.data = "trades_recent"

        with patch("app.bot.menu._bot") as mock_bot, \
             patch("app.bot.handlers.cmd_trades", new_callable=AsyncMock) as mock_cmd:
            mock_bot.is_valid_chat.return_value = True

            await menu_callback_handler(mock_callback_update, mock_callback_context)

            mock_cmd.assert_called_once()

    @pytest.mark.asyncio
    async def test_trades_today_callback(self, mock_callback_update, mock_callback_context):
        """Test trades_today callback sets args and executes trades command."""
        from app.bot.menu import menu_callback_handler

        mock_callback_update.callback_query.data = "trades_today"

        with patch("app.bot.menu._bot") as mock_bot, \
             patch("app.bot.handlers.cmd_trades", new_callable=AsyncMock) as mock_cmd:
            mock_bot.is_valid_chat.return_value = True

            await menu_callback_handler(mock_callback_update, mock_callback_context)

            mock_cmd.assert_called_once()
            assert mock_callback_context.args == ["today"]

    @pytest.mark.asyncio
    async def test_trades_week_callback(self, mock_callback_update, mock_callback_context):
        """Test trades_week callback sets args and executes trades command."""
        from app.bot.menu import menu_callback_handler

        mock_callback_update.callback_query.data = "trades_week"

        with patch("app.bot.menu._bot") as mock_bot, \
             patch("app.bot.handlers.cmd_trades", new_callable=AsyncMock) as mock_cmd:
            mock_bot.is_valid_chat.return_value = True

            await menu_callback_handler(mock_callback_update, mock_callback_context)

            mock_cmd.assert_called_once()
            assert mock_callback_context.args == ["week"]

    @pytest.mark.asyncio
    async def test_settings_timezone_callback(self, mock_callback_update, mock_callback_context):
        """Test settings_timezone callback shows timezone menu."""
        from app.bot.menu import menu_callback_handler

        mock_callback_update.callback_query.data = "settings_timezone"

        # Mock cursor that returns None (no DB value, fallback to settings)
        mock_cursor = MagicMock()
        mock_cursor.fetchone = AsyncMock(return_value=None)

        mock_connection = MagicMock()
        mock_connection.execute = AsyncMock(return_value=mock_cursor)

        with patch("app.bot.menu._bot") as mock_bot, \
             patch("app.database.db") as mock_db, \
             patch("app.config.settings") as mock_settings:
            mock_bot.is_valid_chat.return_value = True
            mock_db.connection = mock_connection
            mock_settings.timezone = "UTC"

            await menu_callback_handler(mock_callback_update, mock_callback_context)

            # Verify menu is shown via edit_message_text
            mock_callback_update.callback_query.edit_message_text.assert_called_once()
            call_args = mock_callback_update.callback_query.edit_message_text.call_args
            assert "Timezone" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_settings_reporttime_callback(self, mock_callback_update, mock_callback_context):
        """Test settings_reporttime callback shows reporttime menu."""
        from app.bot.menu import menu_callback_handler

        mock_callback_update.callback_query.data = "settings_reporttime"

        # Mock cursor that returns None (no DB value, fallback to settings)
        mock_cursor = MagicMock()
        mock_cursor.fetchone = AsyncMock(return_value=None)

        mock_connection = MagicMock()
        mock_connection.execute = AsyncMock(return_value=mock_cursor)

        with patch("app.bot.menu._bot") as mock_bot, \
             patch("app.database.db") as mock_db, \
             patch("app.config.settings") as mock_settings:
            mock_bot.is_valid_chat.return_value = True
            mock_db.connection = mock_connection
            mock_settings.daily_report_time = "12:00"

            await menu_callback_handler(mock_callback_update, mock_callback_context)

            # Verify menu is shown via edit_message_text
            mock_callback_update.callback_query.edit_message_text.assert_called_once()
            call_args = mock_callback_update.callback_query.edit_message_text.call_args
            assert "Report Time" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_settings_fees_callback(self, mock_callback_update, mock_callback_context):
        """Test settings_fees callback executes fees command."""
        from app.bot.menu import menu_callback_handler

        mock_callback_update.callback_query.data = "settings_fees"

        with patch("app.bot.menu._bot") as mock_bot, \
             patch("app.bot.handlers.cmd_fees", new_callable=AsyncMock) as mock_cmd:
            mock_bot.is_valid_chat.return_value = True

            await menu_callback_handler(mock_callback_update, mock_callback_context)

            mock_cmd.assert_called_once()

    @pytest.mark.asyncio
    async def test_settings_capital_callback(self, mock_callback_update, mock_callback_context):
        """Test settings_capital callback executes set_capital command."""
        from app.bot.menu import menu_callback_handler

        mock_callback_update.callback_query.data = "settings_capital"

        with patch("app.bot.menu._bot") as mock_bot, \
             patch("app.bot.handlers.cmd_set_capital", new_callable=AsyncMock) as mock_cmd:
            mock_bot.is_valid_chat.return_value = True

            await menu_callback_handler(mock_callback_update, mock_callback_context)

            mock_cmd.assert_called_once()

    @pytest.mark.asyncio
    async def test_settings_pause_callback(self, mock_callback_update, mock_callback_context):
        """Test settings_pause callback executes pause command."""
        from app.bot.menu import menu_callback_handler

        mock_callback_update.callback_query.data = "settings_pause"

        with patch("app.bot.menu._bot") as mock_bot, \
             patch("app.bot.handlers.cmd_pause", new_callable=AsyncMock) as mock_cmd:
            mock_bot.is_valid_chat.return_value = True

            await menu_callback_handler(mock_callback_update, mock_callback_context)

            mock_cmd.assert_called_once()

    @pytest.mark.asyncio
    async def test_settings_resume_callback(self, mock_callback_update, mock_callback_context):
        """Test settings_resume callback executes resume command."""
        from app.bot.menu import menu_callback_handler

        mock_callback_update.callback_query.data = "settings_resume"

        with patch("app.bot.menu._bot") as mock_bot, \
             patch("app.bot.handlers.cmd_resume", new_callable=AsyncMock) as mock_cmd:
            mock_bot.is_valid_chat.return_value = True

            await menu_callback_handler(mock_callback_update, mock_callback_context)

            mock_cmd.assert_called_once()

    @pytest.mark.asyncio
    async def test_cmd_export_callback(self, mock_callback_update, mock_callback_context):
        """Test cmd_export callback executes export command."""
        from app.bot.menu import menu_callback_handler

        mock_callback_update.callback_query.data = "cmd_export"

        with patch("app.bot.menu._bot") as mock_bot, \
             patch("app.bot.handlers.cmd_export", new_callable=AsyncMock) as mock_cmd:
            mock_bot.is_valid_chat.return_value = True

            await menu_callback_handler(mock_callback_update, mock_callback_context)

            mock_cmd.assert_called_once()

    @pytest.mark.asyncio
    async def test_cmd_help_callback(self, mock_callback_update, mock_callback_context):
        """Test cmd_help callback executes help command."""
        from app.bot.menu import menu_callback_handler

        mock_callback_update.callback_query.data = "cmd_help"

        with patch("app.bot.menu._bot") as mock_bot, \
             patch("app.bot.handlers.cmd_help", new_callable=AsyncMock) as mock_cmd:
            mock_bot.is_valid_chat.return_value = True

            await menu_callback_handler(mock_callback_update, mock_callback_context)

            mock_cmd.assert_called_once()

    @pytest.mark.asyncio
    async def test_pnl_period_selection(self, mock_callback_update, mock_callback_context):
        """Test pnl_period_ callback updates PnL menu state."""
        from app.bot.menu import menu_callback_handler, get_user_period, _user_periods

        # Clear state
        _user_periods.clear()

        mock_callback_update.callback_query.data = "pnl_period_week"

        with patch("app.bot.menu._bot") as mock_bot:
            mock_bot.is_valid_chat.return_value = True

            await menu_callback_handler(mock_callback_update, mock_callback_context)

            # Verify period was set
            period = get_user_period(-1001234567890, "pnl")
            assert period == "week"

    @pytest.mark.asyncio
    async def test_callback_error_handling(self, mock_callback_update, mock_callback_context):
        """Test callback error handling sends error message."""
        from app.bot.menu import menu_callback_handler

        mock_callback_update.callback_query.data = "perf_stats"

        with patch("app.bot.menu._bot") as mock_bot, \
             patch("app.bot.handlers.cmd_stats", new_callable=AsyncMock) as mock_cmd:
            mock_bot.is_valid_chat.return_value = True
            mock_cmd.side_effect = Exception("Test error")

            await menu_callback_handler(mock_callback_update, mock_callback_context)

            # Should have sent error message
            mock_callback_update.callback_query.message.reply_text.assert_called_once()
            call_args = mock_callback_update.callback_query.message.reply_text.call_args[0][0]
            assert "Error" in call_args


class TestCallbackMessageAdapterMethods:
    """Tests for CallbackMessageAdapter async methods."""

    @pytest.mark.asyncio
    async def test_adapter_reply_text(self):
        """Test CallbackMessageAdapter reply_text method."""
        from app.bot.menu import CallbackMessageAdapter

        mock_query = MagicMock()
        mock_query.message.reply_text = AsyncMock(return_value="sent")

        adapter = CallbackMessageAdapter(mock_query)
        result = await adapter.reply_text("Test message")

        mock_query.message.reply_text.assert_called_once_with("Test message")
        assert result == "sent"

    @pytest.mark.asyncio
    async def test_adapter_reply_photo(self):
        """Test CallbackMessageAdapter reply_photo method."""
        from app.bot.menu import CallbackMessageAdapter

        mock_query = MagicMock()
        mock_query.message.reply_photo = AsyncMock(return_value="photo_sent")

        adapter = CallbackMessageAdapter(mock_query)
        result = await adapter.reply_photo(photo="test_photo")

        mock_query.message.reply_photo.assert_called_once_with(photo="test_photo")
        assert result == "photo_sent"

    @pytest.mark.asyncio
    async def test_adapter_reply_document(self):
        """Test CallbackMessageAdapter reply_document method."""
        from app.bot.menu import CallbackMessageAdapter

        mock_query = MagicMock()
        mock_query.message.reply_document = AsyncMock(return_value="doc_sent")

        adapter = CallbackMessageAdapter(mock_query)
        result = await adapter.reply_document(document="test_doc")

        mock_query.message.reply_document.assert_called_once_with(document="test_doc")
        assert result == "doc_sent"


class TestExecuteCommandFromCallback:
    """Tests for _execute_command_from_callback function."""

    @pytest.mark.asyncio
    async def test_execute_command_creates_adapter(self):
        """Test that execute creates proper adapters."""
        from app.bot.menu import _execute_command_from_callback, CallbackUpdateAdapter

        mock_query = MagicMock()
        mock_query.message.chat = MagicMock(id=12345)
        mock_context = MagicMock()
        mock_command = AsyncMock()

        await _execute_command_from_callback(mock_query, mock_context, mock_command)

        mock_command.assert_called_once()
        call_args = mock_command.call_args[0]
        adapted_update = call_args[0]
        assert isinstance(adapted_update, CallbackUpdateAdapter)
        assert adapted_update.effective_chat == mock_query.message.chat
