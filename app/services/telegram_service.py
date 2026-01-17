"""
Telegram Service

Handles sending trade notifications and daily reports to Telegram.
"""

import logging
from datetime import datetime

import pytz
from telegram import Bot
from telegram.error import TelegramError

from ..config import settings
from ..models import TradeClosedData, DailyReportData, PyramidEntryData

logger = logging.getLogger(__name__)


class TelegramService:
    """Service for sending Telegram notifications."""

    def __init__(self):
        self._bot: Bot | None = None

    @property
    def bot(self) -> Bot:
        """Get or create Telegram bot instance."""
        if not self._bot:
            if not settings.telegram_bot_token:
                raise ValueError("Telegram bot token not configured")
            self._bot = Bot(token=settings.telegram_bot_token)
        return self._bot

    @property
    def is_enabled(self) -> bool:
        """Check if Telegram notifications are enabled."""
        return (
            settings.telegram_enabled
            and bool(settings.telegram_bot_token)
            and bool(settings.telegram_channel_id)
        )

    @property
    def signals_channel_enabled(self) -> bool:
        """Check if signals-only channel is configured."""
        return (
            settings.telegram_enabled
            and bool(settings.telegram_bot_token)
            and bool(settings.telegram_signals_channel_id)
        )

    def _get_local_time(self, utc_time: datetime | None = None) -> datetime:
        """Convert UTC time to configured timezone."""
        tz = pytz.timezone(settings.timezone)
        if utc_time is None:
            utc_time = datetime.utcnow()
        if utc_time.tzinfo is None:
            utc_time = pytz.utc.localize(utc_time)
        return utc_time.astimezone(tz)

    def _format_time(self, dt: datetime) -> str:
        """Format datetime for display."""
        local_dt = self._get_local_time(dt)
        return local_dt.strftime("%H:%M:%S")

    def _format_date(self, dt: datetime) -> str:
        """Format date for display."""
        local_dt = self._get_local_time(dt)
        return local_dt.strftime("%Y-%m-%d")

    def _format_price(self, price: float) -> str:
        """Format price for display."""
        if price >= 1000:
            return f"${price:,.2f}"
        elif price >= 1:
            return f"${price:.4f}"
        else:
            return f"${price:.8f}"

    def _format_pnl(self, pnl: float) -> str:
        """Format PnL with + or - prefix."""
        sign = "+" if pnl >= 0 else ""
        return f"{sign}${pnl:.2f}"

    def _format_percent(self, percent: float) -> str:
        """Format percentage with + or - prefix."""
        sign = "+" if percent >= 0 else ""
        return f"{sign}{percent:.2f}%"

    def _format_quantity(self, qty: float) -> str:
        """Format quantity, removing unnecessary trailing zeros."""
        # Format with enough precision, then strip trailing zeros
        formatted = f"{qty:.8f}".rstrip('0').rstrip('.')
        return formatted

    def _parse_exchange_timestamp(self, timestamp: str) -> str:
        """Parse exchange timestamp and format it for display."""
        try:
            # Try ISO format (YYYY-MM-DDTHH:MM:SSZ)
            dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            return self._format_time(dt)
        except (ValueError, AttributeError):
            # Return as-is if parsing fails
            return timestamp or "N/A"

    def format_pyramid_entry_message(self, data: PyramidEntryData) -> str:
        """
        Format pyramid entry notification message.

        Args:
            data: Pyramid entry data

        Returns:
            Formatted message string
        """
        exchange_time_str = self._parse_exchange_timestamp(data.exchange_timestamp)
        received_time_str = self._format_time(data.received_timestamp)

        lines = [
            "📈 Pyramid Entry",
            "",
            f"Group: {data.group_id}",
            f"Pyramid #{data.pyramid_index}",
            "",
            f"Exchange: {data.exchange.capitalize()}",
            f"Pair: {data.base}/{data.quote}",
            f"Timeframe: {data.timeframe}",
            "",
            f"Entry Price: {self._format_price(data.entry_price)}",
            f"Size: {self._format_quantity(data.position_size)} {data.base}",
            f"Capital: ${data.capital_usdt:.2f}",
            "",
            "Timestamps:",
            f"├─ Exchange: {exchange_time_str}",
            f"└─ Received: {received_time_str} ({settings.timezone})",
        ]

        return "\n".join(lines)

    def format_trade_closed_message(self, data: TradeClosedData) -> str:
        """
        Format trade closed notification message with dual timestamps.

        Args:
            data: Trade closed data

        Returns:
            Formatted message string
        """
        # Parse timestamps
        exchange_time_str = self._parse_exchange_timestamp(data.exchange_timestamp)
        received_time_str = self._format_time(data.received_timestamp)

        lines = [
            "📊 Trade Closed",
            "",
            f"Group: {data.group_id}",
            f"Timeframe: {data.timeframe}",
            "",
            f"Date: {self._format_date(data.received_timestamp)}",
            "",
            f"Exchange: {data.exchange.capitalize()}",
            f"Pair: {data.base}/{data.quote}",
            "",
            "Entries:",
        ]

        # Add pyramid entries with their exchange timestamps
        for i, pyramid in enumerate(data.pyramids):
            is_last = i == len(data.pyramids) - 1
            prefix = "└─" if is_last else "├─"

            entry_time = pyramid.get("entry_time", "")
            if isinstance(entry_time, str):
                try:
                    entry_dt = datetime.fromisoformat(entry_time)
                    entry_time_str = self._format_time(entry_dt)
                except ValueError:
                    entry_time_str = entry_time
            else:
                entry_time_str = self._format_time(entry_time)

            price_str = self._format_price(pyramid["entry_price"])
            lines.append(
                f"{prefix} P{pyramid['index']}: {price_str} @ {entry_time_str} "
                f"({self._format_quantity(pyramid['size'])} {data.base})"
            )

        # Add exit with dual timestamps
        lines.extend([
            "",
            f"Exit: {self._format_price(data.exit_price)}",
            "Exit Timestamps:",
            f"├─ Exchange: {exchange_time_str}",
            f"└─ Received: {received_time_str} ({settings.timezone})",
            "",
            "Results:",
            f"├─ Gross PnL: {self._format_pnl(data.gross_pnl)}",
            f"├─ Fees: -${data.total_fees:.2f}",
            f"└─ Net PnL: {self._format_pnl(data.net_pnl)} ({self._format_percent(data.net_pnl_percent)})",
        ])

        return "\n".join(lines)

    def format_daily_report_message(self, data: DailyReportData) -> str:
        """
        Format daily report notification message.

        Args:
            data: Daily report data

        Returns:
            Formatted message string
        """
        lines = [
            f"📈 Daily Report - {data.date}",
            "",
            "Summary:",
            f"├─ Total Trades: {data.total_trades}",
            f"├─ Total Pyramids: {data.total_pyramids}",
            f"└─ Net PnL: {self._format_pnl(data.total_pnl_usdt)} ({self._format_percent(data.total_pnl_percent)})",
        ]

        # Trade history with group_id
        if data.trades:
            lines.extend(["", "Closed Trades:"])
            for i, trade in enumerate(data.trades):
                is_last = i == len(data.trades) - 1
                prefix = "└─" if is_last else "├─"
                pnl_str = self._format_pnl(trade.pnl_usdt)
                pct_str = self._format_percent(trade.pnl_percent)
                lines.append(
                    f"{prefix} {trade.group_id}: {pnl_str} ({pct_str})"
                )
                # Show details on next line
                detail_prefix = "   " if is_last else "│  "
                lines.append(
                    f"{detail_prefix} {trade.exchange.capitalize()} | {trade.pair} | {trade.timeframe} | {trade.pyramids_count}P"
                )

        # By exchange breakdown
        if data.by_exchange:
            lines.extend(["", "By Exchange:"])
            exchanges = list(data.by_exchange.items())
            for i, (exchange, stats) in enumerate(exchanges):
                is_last = i == len(exchanges) - 1
                prefix = "└─" if is_last else "├─"
                pnl = stats.get("pnl", 0)
                trades = stats.get("trades", 0)
                lines.append(
                    f"{prefix} {exchange.capitalize()}: {self._format_pnl(pnl)} ({trades} trades)"
                )

        # By timeframe breakdown
        if data.by_timeframe:
            lines.extend(["", "By Timeframe:"])
            timeframes = list(data.by_timeframe.items())
            for i, (timeframe, stats) in enumerate(timeframes):
                is_last = i == len(timeframes) - 1
                prefix = "└─" if is_last else "├─"
                pnl = stats.get("pnl", 0)
                trades = stats.get("trades", 0)
                lines.append(
                    f"{prefix} {timeframe}: {self._format_pnl(pnl)} ({trades} trades)"
                )

        # By pair breakdown
        if data.by_pair:
            lines.extend(["", "By Pair:"])
            # Sort by absolute PnL
            sorted_pairs = sorted(
                data.by_pair.items(), key=lambda x: abs(x[1]), reverse=True
            )
            for i, (pair, pnl) in enumerate(sorted_pairs):
                is_last = i == len(sorted_pairs) - 1
                prefix = "└─" if is_last else "├─"
                lines.append(f"{prefix} {pair}: {self._format_pnl(pnl)}")

        return "\n".join(lines)

    async def send_message(self, text: str) -> bool:
        """
        Send a message to the configured Telegram channel.

        Args:
            text: Message text

        Returns:
            True if sent successfully, False otherwise
        """
        if not self.is_enabled:
            logger.warning("Telegram notifications disabled, skipping send")
            return False

        try:
            await self.bot.send_message(
                chat_id=settings.telegram_channel_id,
                text=text,
                parse_mode=None,  # Plain text for better formatting
            )
            logger.info("Telegram message sent successfully")
            return True
        except TelegramError as e:
            logger.error(f"Failed to send Telegram message: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending Telegram message: {e}")
            return False

    async def send_to_signals_channel(self, text: str) -> bool:
        """
        Send a message to the signals-only channel.

        Args:
            text: Message text

        Returns:
            True if sent successfully, False otherwise
        """
        if not self.signals_channel_enabled:
            return False

        try:
            await self.bot.send_message(
                chat_id=settings.telegram_signals_channel_id,
                text=text,
                parse_mode=None,
            )
            logger.info("Telegram message sent to signals channel")
            return True
        except TelegramError as e:
            logger.error(f"Failed to send to signals channel: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending to signals channel: {e}")
            return False

    async def send_signal_message(self, text: str) -> bool:
        """
        Send a signal message to both main and signals-only channels.

        Args:
            text: Message text

        Returns:
            True if sent to at least one channel successfully
        """
        main_result = await self.send_message(text)
        signals_result = await self.send_to_signals_channel(text)
        return main_result or signals_result

    async def send_trade_closed(self, data: TradeClosedData) -> bool:
        """
        Send trade closed notification to both channels.

        Args:
            data: Trade closed data

        Returns:
            True if sent successfully
        """
        message = self.format_trade_closed_message(data)
        return await self.send_signal_message(message)

    async def send_pyramid_entry(self, data: PyramidEntryData) -> bool:
        """
        Send pyramid entry notification to both channels.

        Args:
            data: Pyramid entry data

        Returns:
            True if sent successfully
        """
        message = self.format_pyramid_entry_message(data)
        return await self.send_signal_message(message)

    async def send_daily_report(self, data: DailyReportData) -> bool:
        """
        Send daily report notification to both channels.

        Args:
            data: Daily report data

        Returns:
            True if sent successfully
        """
        message = self.format_daily_report_message(data)
        return await self.send_signal_message(message)


# Singleton instance
telegram_service = TelegramService()
