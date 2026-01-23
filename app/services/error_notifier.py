"""
Error Notification Service

Handles sending error notifications to Telegram for monitoring and alerting.
"""

import logging
import traceback
from enum import Enum

logger = logging.getLogger(__name__)


class ErrorLevel(Enum):
    """Error severity levels."""

    INFO = "ℹ️"  # Informational (no notification)
    WARNING = "⚠️"  # Warning (no notification)
    ERROR = "🔴"  # Error (notify Telegram)
    CRITICAL = "🚨"  # Critical (notify with stack trace)


class ErrorNotifier:
    """Service for sending error notifications to Telegram."""

    def __init__(self):
        self._telegram_service = None

    @property
    def telegram_service(self):
        """Lazy load telegram service to avoid circular imports."""
        if self._telegram_service is None:
            from .telegram_service import telegram_service

            self._telegram_service = telegram_service
        return self._telegram_service

    async def notify(
        self,
        level: ErrorLevel,
        error_type: str,
        message: str,
        details: str | None = None,
    ) -> bool:
        """
        Send error notification based on severity level.

        Args:
            level: Error severity level
            error_type: Type/category of error (e.g., "Price Fetch Failed")
            message: Human-readable error message
            details: Optional technical details (truncated to 500 chars)

        Returns:
            True if notification sent, False otherwise
        """
        # Only notify on ERROR and CRITICAL levels
        if level not in (ErrorLevel.ERROR, ErrorLevel.CRITICAL):
            logger.debug(f"Skipping notification for {level.name}: {error_type}")
            return False

        text = f"{level.value} **{error_type}**\n\n{message}"

        if details:
            # Truncate details to prevent huge messages
            truncated = details[:500]
            if len(details) > 500:
                truncated += "..."
            text += f"\n\n```\n{truncated}\n```"

        try:
            return await self.telegram_service.send_message(text)
        except Exception as e:
            # Don't let notification failures crash the app
            logger.error(f"Failed to send error notification: {e}")
            return False

    async def notify_error(
        self,
        error_type: str,
        message: str,
        details: str | None = None,
    ) -> bool:
        """Convenience method for ERROR level notifications."""
        return await self.notify(ErrorLevel.ERROR, error_type, message, details)

    async def notify_critical(
        self,
        error: Exception,
        context: str,
    ) -> bool:
        """
        Send critical error notification with stack trace.

        Args:
            error: The exception that occurred
            context: Where the error occurred (e.g., "Webhook /webhook")

        Returns:
            True if notification sent, False otherwise
        """
        error_type = type(error).__name__
        message = f"Context: {context}\n\nError: {str(error)}"

        # Get stack trace
        tb = traceback.format_exc()

        return await self.notify(ErrorLevel.CRITICAL, error_type, message, tb)

    async def notify_trade_error(
        self,
        pair: str,
        exchange: str,
        error_msg: str,
    ) -> bool:
        """Send notification for trade-related errors."""
        return await self.notify_error(
            error_type="Trade Error",
            message=f"Pair: {pair}\nExchange: {exchange}\n\n{error_msg}",
        )

    async def notify_exchange_error(
        self,
        exchange: str,
        error_msg: str,
    ) -> bool:
        """Send notification for exchange connectivity errors."""
        return await self.notify_error(
            error_type="Exchange Error",
            message=f"Exchange: {exchange}\n\n{error_msg}",
        )

    async def notify_pyramid_limit(
        self,
        pair: str,
        exchange: str,
        current_pyramids: int,
        max_pyramids: int,
    ) -> bool:
        """Send notification when pyramid limit is reached."""
        return await self.notify(
            level=ErrorLevel.ERROR,
            error_type="Pyramid Limit Reached",
            message=(
                f"Signal ignored for {pair} on {exchange}\n\n"
                f"Current pyramids: {current_pyramids}\n"
                f"Maximum allowed: {max_pyramids}"
            ),
        )


# Global instance
error_notifier = ErrorNotifier()
