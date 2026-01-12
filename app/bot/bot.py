"""
Telegram Bot Setup

Initializes and runs the Telegram bot alongside FastAPI.
"""

import logging
from telegram import BotCommand, Update
from telegram.ext import Application, ContextTypes

from ..config import settings

# Commands to register with Telegram menu
BOT_COMMANDS = [
    BotCommand("ping", "Health check"),
    BotCommand("status", "Open trades with unrealized PnL"),
    BotCommand("live", "Real-time prices"),
    BotCommand("report", "Performance report"),
    BotCommand("stats", "Overall statistics"),
    BotCommand("pnl", "Total PnL summary"),
    BotCommand("best", "Top 5 profitable pairs"),
    BotCommand("worst", "Top 5 losing pairs"),
    BotCommand("streak", "Win/loss streak"),
    BotCommand("drawdown", "Drawdown info"),
    BotCommand("trades", "Recent trades"),
    BotCommand("history", "History for pair"),
    BotCommand("exchange", "Stats by exchange"),
    BotCommand("fees", "Show exchange fees"),
    BotCommand("setfee", "Update fee rate"),
    BotCommand("timezone", "View/set timezone"),
    BotCommand("reporttime", "Set report time"),
    BotCommand("set_capital", "Set capital for sizing"),
    BotCommand("pause", "Pause signals"),
    BotCommand("resume", "Resume signals"),
    BotCommand("ignore", "Ignore pair"),
    BotCommand("unignore", "Resume pair"),
    BotCommand("export", "Export to CSV"),
    BotCommand("help", "Show all commands"),
]

logger = logging.getLogger(__name__)


class TelegramBot:
    """Telegram bot manager."""

    def __init__(self):
        self._app: Application | None = None
        self._running = False

    @property
    def app(self) -> Application:
        """Get the bot application."""
        if not self._app:
            raise RuntimeError("Bot not initialized")
        return self._app

    @property
    def is_running(self) -> bool:
        """Check if bot is running."""
        return self._running

    def is_valid_chat(self, update: Update) -> bool:
        """Check if message is from the configured channel."""
        if not update.effective_chat:
            return False

        chat_id = str(update.effective_chat.id)
        allowed_id = str(settings.telegram_channel_id)

        return chat_id == allowed_id

    async def initialize(self) -> None:
        """Initialize the bot application."""
        if not settings.telegram_bot_token:
            logger.warning("Telegram bot token not configured, bot disabled")
            return

        self._app = (
            Application.builder()
            .token(settings.telegram_bot_token)
            .build()
        )

        # Import and setup handlers
        from .handlers import setup_handlers
        setup_handlers(self._app, self)

        logger.info("Telegram bot initialized")

    async def start(self) -> None:
        """Start the bot polling."""
        if not self._app:
            logger.warning("Bot not initialized, skipping start")
            return

        await self._app.initialize()
        await self._app.start()

        # Register commands with Telegram to show in menu
        try:
            await self._app.bot.set_my_commands(BOT_COMMANDS)
            logger.info("Bot commands registered with Telegram")
        except Exception as e:
            logger.error(f"Failed to register bot commands: {e}")

        await self._app.updater.start_polling(drop_pending_updates=True)

        self._running = True
        logger.info("Telegram bot started polling")

    async def stop(self) -> None:
        """Stop the bot."""
        if not self._app or not self._running:
            return

        self._running = False
        await self._app.updater.stop()
        await self._app.stop()
        await self._app.shutdown()

        logger.info("Telegram bot stopped")


# Global bot instance
telegram_bot = TelegramBot()
