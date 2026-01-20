"""
Tests for Telegram bot in app/bot/bot.py

Tests the bot initialization and validation.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestTelegramBot:
    """Tests for TelegramBot class."""

    def test_init(self):
        """Test TelegramBot initialization."""
        from app.bot.bot import TelegramBot

        bot = TelegramBot()
        assert bot._app is None
        assert bot._running is False

    def test_is_running_property(self):
        """Test is_running property."""
        from app.bot.bot import TelegramBot

        bot = TelegramBot()
        assert bot.is_running is False

        bot._running = True
        assert bot.is_running is True

    def test_app_property_raises_without_init(self):
        """Test that app property raises when not initialized."""
        from app.bot.bot import TelegramBot

        bot = TelegramBot()
        with pytest.raises(RuntimeError, match="not initialized"):
            _ = bot.app

    def test_app_property_returns_app(self):
        """Test that app property returns the application."""
        from app.bot.bot import TelegramBot

        bot = TelegramBot()
        mock_app = MagicMock()
        bot._app = mock_app

        assert bot.app is mock_app

    def test_is_valid_chat_no_effective_chat(self):
        """Test is_valid_chat returns False when no effective chat."""
        from app.bot.bot import TelegramBot

        bot = TelegramBot()
        mock_update = MagicMock()
        mock_update.effective_chat = None

        assert bot.is_valid_chat(mock_update) is False

    def test_is_valid_chat_wrong_chat_id(self):
        """Test is_valid_chat returns False for wrong chat ID."""
        from app.bot.bot import TelegramBot

        bot = TelegramBot()
        mock_update = MagicMock()
        mock_update.effective_chat.id = 12345

        with patch("app.bot.bot.settings") as mock_settings:
            mock_settings.telegram_channel_id = "99999"
            assert bot.is_valid_chat(mock_update) is False

    def test_is_valid_chat_correct_chat_id(self):
        """Test is_valid_chat returns True for correct chat ID."""
        from app.bot.bot import TelegramBot

        bot = TelegramBot()
        mock_update = MagicMock()
        mock_update.effective_chat.id = 12345

        with patch("app.bot.bot.settings") as mock_settings:
            mock_settings.telegram_channel_id = "12345"
            assert bot.is_valid_chat(mock_update) is True

    @pytest.mark.asyncio
    async def test_initialize_without_token(self):
        """Test initialize logs warning when no token."""
        from app.bot.bot import TelegramBot

        bot = TelegramBot()

        with patch("app.bot.bot.settings") as mock_settings:
            mock_settings.telegram_bot_token = ""

            await bot.initialize()

            assert bot._app is None

    @pytest.mark.asyncio
    async def test_start_without_app(self):
        """Test start does nothing when app not initialized."""
        from app.bot.bot import TelegramBot

        bot = TelegramBot()
        # Should not raise
        await bot.start()
        assert bot._running is False

    @pytest.mark.asyncio
    async def test_stop_without_app(self):
        """Test stop does nothing when app not initialized."""
        from app.bot.bot import TelegramBot

        bot = TelegramBot()
        # Should not raise
        await bot.stop()
        assert bot._running is False

    @pytest.mark.asyncio
    async def test_stop_when_not_running(self):
        """Test stop does nothing when not running."""
        from app.bot.bot import TelegramBot

        bot = TelegramBot()
        bot._app = MagicMock()
        bot._running = False

        await bot.stop()
        assert bot._running is False


class TestBotCommands:
    """Tests for BOT_COMMANDS constant."""

    def test_bot_commands_defined(self):
        """Test that BOT_COMMANDS is properly defined."""
        from app.bot.bot import BOT_COMMANDS

        assert len(BOT_COMMANDS) > 0

    def test_bot_commands_have_menu(self):
        """Test that menu command is in BOT_COMMANDS."""
        from app.bot.bot import BOT_COMMANDS

        commands = [cmd.command for cmd in BOT_COMMANDS]
        assert "menu" in commands

    def test_bot_commands_have_required_commands(self):
        """Test that all required commands are defined."""
        from app.bot.bot import BOT_COMMANDS

        commands = [cmd.command for cmd in BOT_COMMANDS]
        required = ["menu", "ping", "status", "stats", "pnl", "help"]

        for cmd in required:
            assert cmd in commands, f"Missing command: {cmd}"


class TestGlobalBotInstance:
    """Tests for global telegram_bot instance."""

    def test_global_instance_exists(self):
        """Test that global telegram_bot instance exists."""
        from app.bot.bot import telegram_bot

        assert telegram_bot is not None

    def test_global_instance_is_telegram_bot(self):
        """Test that global instance is TelegramBot."""
        from app.bot.bot import telegram_bot, TelegramBot

        assert isinstance(telegram_bot, TelegramBot)
