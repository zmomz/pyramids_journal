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
