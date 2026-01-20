"""
Telegram Service

Handles sending trade notifications and daily reports to Telegram.
"""

import io
import logging
from datetime import datetime

import pytz
from telegram import Bot
from telegram.error import TelegramError

from ..config import settings
from ..models import TradeClosedData, DailyReportData, PyramidEntryData, EquityPoint, ChartStats

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

    async def get_signals_channel_id(self) -> str | None:
        """Get signals channel ID from database or env."""
        from ..database import db
        try:
            cursor = await db.connection.execute(
                "SELECT value FROM settings WHERE key = 'signals_channel_id'"
            )
            row = await cursor.fetchone()
            if row and row['value']:
                return row['value']
        except Exception:
            pass
        return settings.telegram_signals_channel_id or None

    @property
    def signals_channel_enabled(self) -> bool:
        """Check if signals-only channel could be configured (sync check)."""
        return (
            settings.telegram_enabled
            and bool(settings.telegram_bot_token)
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

    def _format_quantity_with_commas(self, qty: float, symbol: str) -> str:
        """Format quantity with thousand separators."""
        if qty >= 1000:
            return f"{qty:,.0f} {symbol}"
        elif qty >= 1:
            return f"{qty:,.1f} {symbol}"
        else:
            return f"{qty:.4f} {symbol}"

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
        separator = "- - - - - - - - - - - - - - - - - - "

        lines = [
            "📥 Trade Entry",
            separator,
            f"📌 Group: {data.group_id}",
            f"🧱 Entry: #{data.pyramid_index}",
            separator,
            f"🏦 Exchange: {data.exchange.capitalize()}",
            f"💱 Pair: {data.base}/{data.quote}",
            f"⏱ Timeframe: {data.timeframe}",
            separator,
            "📥 Entry Details",
            f"⏰ Entry Time: {exchange_time_str}",
            f"💰 Entry Price: {self._format_price(data.entry_price)}",
            f"📦 Size: {self._format_quantity_with_commas(data.position_size, data.base)}",
            f"💵 Capital: ${data.capital_usdt:,.2f}",
            separator,
            "⏱ System Timestamps",
            f"🕒 Exchange Time: {exchange_time_str}",
            f"📍 Received: {received_time_str} ({settings.timezone})",
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
        separator = "- - - - - - - - - - - - - - - - - - "

        lines = [
            "📊 Trade Closed",
            separator,
            f"📌 Group: {data.group_id}",
            f"⏱ Timeframe: {data.timeframe}",
            f"📅 Date: {self._format_date(data.received_timestamp)}",
            separator,
            f"🏦 Exchange: {data.exchange.capitalize()}",
            f"💱 Pair: {data.base}/{data.quote}",
            separator,
            "📥 Entries:",
            "",
        ]

        # Add pyramid entries with their exchange timestamps
        for i, pyramid in enumerate(data.pyramids):
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
            qty_str = self._format_quantity_with_commas(pyramid['size'], data.base)

            lines.extend([
                f"* Entry {pyramid['index']}",
                f"💰 Price: {price_str}",
                f"⏰ Time: {entry_time_str}",
                f"📦 QTY: {qty_str}",
                "",
            ])

        # Add exit with dual timestamps
        lines.extend([
            separator,
            "📤 Exit:",
            f"💰 Exit Price: {self._format_price(data.exit_price)}",
            f"⏰ Exchange Time: {exchange_time_str}",
            f"📍 Confirmed: {received_time_str} ({settings.timezone})",
            separator,
            "📉 Results:",
            f"💵 Gross PnL: {self._format_pnl(data.gross_pnl)}",
            f"💸 Fees: -${data.total_fees:.2f}",
        ])

        # Use 🟢 for positive, 🔻 for negative net PnL
        pnl_emoji = "🟢" if data.net_pnl >= 0 else "🔻"
        lines.append(f"{pnl_emoji} Net PnL: {self._format_pnl(data.net_pnl)} ({self._format_percent(data.net_pnl_percent)})")

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

    def generate_equity_curve_image(
        self,
        equity_points: list[EquityPoint],
        date: str,
        chart_stats: ChartStats | None = None
    ) -> io.BytesIO | None:
        """
        Generate a professional equity curve chart image with stats footer.

        Args:
            equity_points: List of equity curve data points
            date: Report date for the title
            chart_stats: Optional statistics for the footer

        Returns:
            BytesIO buffer containing the PNG image, or None if not enough data
        """
        if len(equity_points) < 2:
            return None

        try:
            import matplotlib.pyplot as plt
            import matplotlib.dates as mdates
            from matplotlib.ticker import FuncFormatter
            from matplotlib.patches import FancyBboxPatch
            import matplotlib.gridspec as gridspec
            from matplotlib.offsetbox import OffsetImage, AnnotationBbox
            from PIL import Image
            import os
        except ImportError:
            logger.warning("matplotlib not installed, skipping equity curve")
            return None

        # Extract data
        timestamps = [p.timestamp for p in equity_points]
        cumulative_pnls = [p.cumulative_pnl for p in equity_points]
        final_pnl = cumulative_pnls[-1]

        # Determine color based on final PnL
        line_color = '#00C853' if final_pnl >= 0 else '#FF1744'  # Green or Red

        # Create figure with dark theme
        plt.style.use('dark_background')

        # Figure with stats footer - add extra space at top for header
        # Background color matching logo
        bg_color = '#1c1520'  # Dark purple-black matching logo
        chart_bg = '#16213e'  # Slightly different for chart area

        if chart_stats:
            fig = plt.figure(figsize=(12, 11), dpi=150)
            gs = gridspec.GridSpec(3, 1, height_ratios=[0.7, 3, 1.1], hspace=0.18)
            ax_header = fig.add_subplot(gs[0])
            ax = fig.add_subplot(gs[1])
            ax_footer = fig.add_subplot(gs[2])
        else:
            fig = plt.figure(figsize=(10, 7), dpi=150)
            gs = gridspec.GridSpec(2, 1, height_ratios=[0.8, 4], hspace=0.12)
            ax_header = fig.add_subplot(gs[0])
            ax = fig.add_subplot(gs[1])

        # Set background colors
        fig.patch.set_facecolor(bg_color)
        ax.set_facecolor(chart_bg)
        ax_header.set_facecolor(bg_color)
        ax_header.axis('off')

        # Plot the equity curve
        ax.plot(timestamps, cumulative_pnls, color=line_color, linewidth=2.5,
                marker='o', markersize=4, markerfacecolor=line_color, markeredgecolor='white',
                markeredgewidth=0.5, zorder=5)

        # Fill area under curve
        ax.fill_between(timestamps, cumulative_pnls, alpha=0.3, color=line_color)

        # Add horizontal line at zero
        ax.axhline(y=0, color='#ffffff', linewidth=0.8, linestyle='--', alpha=0.4)

        # Format x-axis (time)
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
        plt.sca(ax)
        plt.xticks(rotation=45, ha='right')

        # Format y-axis (currency)
        def currency_formatter(x, p):
            if x >= 0:
                return f'+${x:,.0f}'
            return f'-${abs(x):,.0f}'
        ax.yaxis.set_major_formatter(FuncFormatter(currency_formatter))

        # Add logo and title in header area
        logo_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'logo.jpg')
        try:
            if os.path.exists(logo_path):
                logo_img = Image.open(logo_path)
                # Resize logo to fit nicely
                logo_img.thumbnail((120, 120), Image.Resampling.LANCZOS)
                imagebox = OffsetImage(logo_img, zoom=0.6)
                ab = AnnotationBbox(imagebox, (0.08, 0.5), frameon=False,
                                    xycoords=ax_header.transAxes, box_alignment=(0.5, 0.5))
                ax_header.add_artist(ab)
        except Exception as e:
            logger.warning(f"Could not load logo: {e}")

        # Title in header (no overlap now)
        ax_header.text(0.18, 0.65, 'Equity Curve', transform=ax_header.transAxes,
                       fontsize=20, color='white', fontweight='bold', va='center')
        ax_header.text(0.18, 0.25, f'Time vs Cumulative Net PnL (USDT) - {date}',
                       transform=ax_header.transAxes, fontsize=11, color='#888888', va='center')

        # Style the spines
        for spine in ax.spines.values():
            spine.set_color('#404040')
            spine.set_linewidth(1)

        # Grid styling
        ax.grid(True, linestyle='--', alpha=0.2, color='#ffffff')
        ax.tick_params(colors='#b0b0b0', labelsize=9)

        # Add final value annotation (only the last point)
        sign = '+' if final_pnl >= 0 else ''
        annotation_text = f'Cumulative PnL: {sign}${final_pnl:,.2f}'

        ax.annotate(
            annotation_text,
            xy=(timestamps[-1], final_pnl),
            xytext=(15, 15),
            textcoords='offset points',
            fontsize=11,
            fontweight='bold',
            color='white',
            bbox=dict(
                boxstyle='round,pad=0.5',
                facecolor=line_color,
                edgecolor='white',
                linewidth=1,
                alpha=0.9
            ),
            arrowprops=dict(
                arrowstyle='->',
                color='white',
                connectionstyle='arc3,rad=0.2',
                linewidth=1.5
            ),
            zorder=10
        )

        # Highlight final point
        ax.scatter([timestamps[-1]], [final_pnl], color='white', s=80, zorder=6,
                   edgecolors=line_color, linewidths=2)

        # Add stats footer if provided
        if chart_stats:
            ax_footer.set_facecolor(bg_color)
            ax_footer.axis('off')

            # Stats box styling
            box_color = '#252540'
            border_color = '#404060'

            # Define stats data for two rows
            row1_stats = [
                ('Total Net PnL (USDT)', f'{"+$" if chart_stats.total_net_pnl >= 0 else "-$"}{abs(chart_stats.total_net_pnl):,.2f}'),
                ('Max Drawdown (%)', f'{chart_stats.max_drawdown_percent:.2f}%'),
                ('Number of Trades', f'{chart_stats.num_trades}'),
                ('Win Rate (%)', f'{chart_stats.win_rate:.2f}%'),
            ]
            row2_stats = [
                ('Total Used Equity (USDT)', f'{chart_stats.total_used_equity:,.2f}'),
                ('Max Drawdown (USDT)', f'-{chart_stats.max_drawdown_usdt:,.2f}'),
                ('Profit Factor', f'{chart_stats.profit_factor:.2f}'),
                ('Win / Loss Ratio', f'{chart_stats.win_loss_ratio:.2f}'),
            ]

            # Draw stat boxes
            box_width = 0.23
            box_height = 0.38
            spacing = 0.01
            start_x = 0.02
            row1_y = 0.55
            row2_y = 0.08

            for row_idx, (stats_row, y_pos) in enumerate([(row1_stats, row1_y), (row2_stats, row2_y)]):
                for i, (label, value) in enumerate(stats_row):
                    x_pos = start_x + i * (box_width + spacing)

                    # Draw box
                    box = FancyBboxPatch(
                        (x_pos, y_pos), box_width, box_height,
                        boxstyle="round,pad=0.02,rounding_size=0.02",
                        facecolor=box_color,
                        edgecolor=border_color,
                        linewidth=1.5,
                        transform=ax_footer.transAxes
                    )
                    ax_footer.add_patch(box)

                    # Add label (smaller, gray)
                    ax_footer.text(
                        x_pos + box_width / 2, y_pos + box_height * 0.75,
                        label,
                        transform=ax_footer.transAxes,
                        fontsize=9,
                        color='#888888',
                        ha='center', va='center'
                    )

                    # Add value (larger, white, bold)
                    ax_footer.text(
                        x_pos + box_width / 2, y_pos + box_height * 0.32,
                        value,
                        transform=ax_footer.transAxes,
                        fontsize=14,
                        color='white',
                        fontweight='bold',
                        ha='center', va='center'
                    )

        # Tight layout
        plt.tight_layout()

        # Save to BytesIO buffer
        buf = io.BytesIO()
        fig.savefig(buf, format='png', facecolor=fig.get_facecolor(),
                    edgecolor='none', bbox_inches='tight', pad_inches=0.2)
        buf.seek(0)

        # Close figure to free memory
        plt.close(fig)

        return buf

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

        signals_channel_id = await self.get_signals_channel_id()
        if not signals_channel_id:
            return False

        try:
            await self.bot.send_message(
                chat_id=signals_channel_id,
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

    async def send_photo_to_channel(self, photo: io.BytesIO, caption: str | None = None) -> bool:
        """
        Send a photo to the configured Telegram channel.

        Args:
            photo: BytesIO buffer containing the image
            caption: Optional caption for the image

        Returns:
            True if sent successfully, False otherwise
        """
        if not self.is_enabled:
            return False

        try:
            await self.bot.send_photo(
                chat_id=settings.telegram_channel_id,
                photo=photo,
                caption=caption,
            )
            return True
        except TelegramError as e:
            logger.error(f"Failed to send photo: {e}")
            return False

    async def send_photo_to_signals_channel(self, photo: io.BytesIO, caption: str | None = None) -> bool:
        """
        Send a photo to the signals-only channel.

        Args:
            photo: BytesIO buffer containing the image
            caption: Optional caption for the image

        Returns:
            True if sent successfully, False otherwise
        """
        if not self.signals_channel_enabled:
            return False

        signals_channel_id = await self.get_signals_channel_id()
        if not signals_channel_id:
            return False

        try:
            await self.bot.send_photo(
                chat_id=signals_channel_id,
                photo=photo,
                caption=caption,
            )
            return True
        except TelegramError as e:
            logger.error(f"Failed to send photo to signals channel: {e}")
            return False

    async def send_daily_report(self, data: DailyReportData) -> bool:
        """
        Send daily report notification to both channels.
        Includes equity curve chart if enabled and data is available.

        Args:
            data: Daily report data

        Returns:
            True if sent successfully
        """
        message = self.format_daily_report_message(data)

        # Generate and send equity curve if enabled and has data
        chart_sent = False
        if settings.equity_curve_enabled and data.equity_points:
            chart_image = self.generate_equity_curve_image(
                data.equity_points, data.date, data.chart_stats
            )
            if chart_image:
                # Send chart to main channel
                if self.is_enabled:
                    await self.send_photo_to_channel(chart_image)
                    chart_image.seek(0)  # Reset buffer position for reuse

                # Send chart to signals channel
                await self.send_photo_to_signals_channel(chart_image)
                chart_sent = True
                logger.info("Equity curve chart sent successfully")

        # Send the text report
        return await self.send_signal_message(message)


# Singleton instance
telegram_service = TelegramService()
