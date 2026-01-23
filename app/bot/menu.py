"""
Interactive Menu System for Telegram Bot

Provides inline keyboard menus for better navigation and UX.
"""

import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import RetryAfter
from telegram.ext import CallbackQueryHandler, ContextTypes

logger = logging.getLogger(__name__)


# ============== Keyboard Definitions ==============

def get_main_menu() -> InlineKeyboardMarkup:
    """Create main menu keyboard."""
    keyboard = [
        [
            InlineKeyboardButton("📈 Performance", callback_data="menu_performance"),
            InlineKeyboardButton("💰 PnL", callback_data="menu_pnl"),
        ],
        [
            InlineKeyboardButton("📋 Trades", callback_data="menu_trades"),
            InlineKeyboardButton("⚙️ Settings", callback_data="menu_settings"),
        ],
        [
            InlineKeyboardButton("📤 Export", callback_data="cmd_export"),
            InlineKeyboardButton("❓ Help", callback_data="cmd_help"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_performance_menu(selected_period: str = "all") -> InlineKeyboardMarkup:
    """Create performance submenu with period selection."""
    # Period buttons with checkmark for selected
    periods = [
        ("Today", "today"),
        ("Week", "week"),
        ("Month", "month"),
        ("All", "all"),
    ]
    period_row = [
        InlineKeyboardButton(
            f"{'✓ ' if p[1] == selected_period else ''}{p[0]}",
            callback_data=f"period_{p[1]}"
        )
        for p in periods
    ]

    keyboard = [
        period_row,
        [
            InlineKeyboardButton("📊 Report", callback_data="perf_report"),
            InlineKeyboardButton("📈 Stats", callback_data="perf_stats"),
        ],
        [
            InlineKeyboardButton("🏆 Best", callback_data="perf_best"),
            InlineKeyboardButton("📉 Worst", callback_data="perf_worst"),
        ],
        [
            InlineKeyboardButton("📊 Drawdown", callback_data="perf_drawdown"),
            InlineKeyboardButton("🔥 Streak", callback_data="perf_streak"),
        ],
        [InlineKeyboardButton("← Back", callback_data="menu_main")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_pnl_menu(selected_period: str = "all") -> InlineKeyboardMarkup:
    """Create PnL submenu with period selection."""
    periods = [
        ("Today", "today"),
        ("Week", "week"),
        ("Month", "month"),
        ("All", "all"),
    ]
    period_row = [
        InlineKeyboardButton(
            f"{'✓ ' if p[1] == selected_period else ''}{p[0]}",
            callback_data=f"pnl_period_{p[1]}"
        )
        for p in periods
    ]

    keyboard = [
        period_row,
        [InlineKeyboardButton("💰 Show PnL Summary", callback_data="pnl_show")],
        [InlineKeyboardButton("← Back", callback_data="menu_main")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_trades_menu() -> InlineKeyboardMarkup:
    """Create trades submenu."""
    keyboard = [
        [
            InlineKeyboardButton("📊 Open Positions", callback_data="trades_status"),
            InlineKeyboardButton("🔴 Live Prices", callback_data="trades_live"),
        ],
        [
            InlineKeyboardButton("📜 Recent Trades", callback_data="trades_recent"),
        ],
        [
            InlineKeyboardButton("Today", callback_data="trades_today"),
            InlineKeyboardButton("This Week", callback_data="trades_week"),
        ],
        [InlineKeyboardButton("← Back", callback_data="menu_main")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_settings_menu() -> InlineKeyboardMarkup:
    """Create settings submenu."""
    keyboard = [
        [
            InlineKeyboardButton("🕐 Timezone", callback_data="settings_timezone"),
            InlineKeyboardButton("📅 Report Time", callback_data="settings_reporttime"),
        ],
        [
            InlineKeyboardButton("💵 View Fees", callback_data="settings_fees"),
            InlineKeyboardButton("💰 Capital", callback_data="settings_capital"),
        ],
        [
            InlineKeyboardButton("⏸️ Pause Bot", callback_data="settings_pause"),
            InlineKeyboardButton("▶️ Resume Bot", callback_data="settings_resume"),
        ],
        [InlineKeyboardButton("← Back", callback_data="menu_main")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_reporttime_menu(current_time: str) -> InlineKeyboardMarkup:
    """Create report time selection menu."""
    common_times = [
        ("🌅 08:00", "08:00"),
        ("☀️ 12:00", "12:00"),
        ("🌆 18:00", "18:00"),
        ("🌙 00:00", "00:00"),
    ]

    keyboard = []
    row = []
    for label, time_val in common_times:
        # Mark current time with checkmark
        display = f"✓ {label}" if time_val == current_time else label
        row.append(InlineKeyboardButton(display, callback_data=f"reporttime_{time_val}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    keyboard.append([InlineKeyboardButton("← Back", callback_data="menu_settings")])
    return InlineKeyboardMarkup(keyboard)


def get_timezone_menu(current_tz: str) -> InlineKeyboardMarkup:
    """Create timezone selection menu."""
    common_timezones = [
        ("🇺🇸 New York", "America/New_York"),
        ("🇬🇧 London", "Europe/London"),
        ("🇸🇦 Riyadh", "Asia/Riyadh"),
        ("🇦🇪 Dubai", "Asia/Dubai"),
        ("🇮🇳 Mumbai", "Asia/Kolkata"),
        ("🇸🇬 Singapore", "Asia/Singapore"),
        ("🇯🇵 Tokyo", "Asia/Tokyo"),
        ("🇦🇺 Sydney", "Australia/Sydney"),
    ]

    keyboard = []
    row = []
    for label, tz_val in common_timezones:
        # Mark current timezone with checkmark
        display = f"✓ {label}" if tz_val == current_tz else label
        row.append(InlineKeyboardButton(display, callback_data=f"timezone_{tz_val}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    keyboard.append([InlineKeyboardButton("← Back", callback_data="menu_settings")])
    return InlineKeyboardMarkup(keyboard)


# ============== Menu State ==============

# Store selected periods per user (chat_id -> {'performance': 'all', 'pnl': 'all'})
_user_periods: dict[int, dict[str, str]] = {}


def get_user_period(chat_id: int, menu: str) -> str:
    """Get selected period for a user's menu."""
    if chat_id not in _user_periods:
        _user_periods[chat_id] = {}
    return _user_periods[chat_id].get(menu, "all")


def set_user_period(chat_id: int, menu: str, period: str) -> None:
    """Set selected period for a user's menu."""
    if chat_id not in _user_periods:
        _user_periods[chat_id] = {}
    _user_periods[chat_id][menu] = period


def period_to_args(period: str) -> list[str]:
    """Convert period selection to command args."""
    if period == "all":
        return []
    return [period]


class CallbackMessageAdapter:
    """Adapter to make callback query messages work with command handlers."""

    def __init__(self, callback_query):
        self._query = callback_query
        self._message = callback_query.message

    async def reply_text(self, text, **kwargs):
        """Send a new message as reply."""
        return await self._message.reply_text(text, **kwargs)

    async def reply_photo(self, **kwargs):
        """Send a photo as reply."""
        return await self._message.reply_photo(**kwargs)

    async def reply_document(self, **kwargs):
        """Send a document as reply."""
        return await self._message.reply_document(**kwargs)

    @property
    def chat_id(self):
        return self._message.chat_id


class CallbackUpdateAdapter:
    """Adapter to make callback updates work with command handlers."""

    def __init__(self, callback_query):
        self.callback_query = callback_query
        self.message = CallbackMessageAdapter(callback_query)
        self.effective_chat = callback_query.message.chat


async def _execute_command_from_callback(query, context, command_func):
    """Execute a command handler from a callback query."""
    # Create an adapter that makes callback query look like a regular update
    adapted_update = CallbackUpdateAdapter(query)
    # Call the command function - the adapter has effective_chat for validation
    await command_func(adapted_update, context)


# ============== Callback Handlers ==============

# Reference to bot for channel validation
_bot = None


async def menu_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle all menu callback queries."""
    query = update.callback_query

    # Validate this is from the configured channel
    if _bot and not _bot.is_valid_chat(update):
        return

    await query.answer()  # Acknowledge the callback

    chat_id = query.message.chat_id
    data = query.data

    # Import handlers here to avoid circular imports
    from . import handlers

    try:
        # Main menu navigation
        if data == "menu_main":
            await query.edit_message_text(
                "📊 Trading Bot Menu\n━━━━━━━━━━━━━━━━━━━━━━━\n\nSelect a category:",
                reply_markup=get_main_menu()
            )

        elif data == "menu_performance":
            period = get_user_period(chat_id, "performance")
            await query.edit_message_text(
                "📈 Performance Analytics\n━━━━━━━━━━━━━━━━━━━━━━━\n\n📅 Select period, then tap a report:",
                reply_markup=get_performance_menu(period)
            )

        elif data == "menu_pnl":
            period = get_user_period(chat_id, "pnl")
            await query.edit_message_text(
                "💰 Profit & Loss\n━━━━━━━━━━━━━━━━━━━━━━━\n\n📅 Select period:",
                reply_markup=get_pnl_menu(period)
            )

        elif data == "menu_trades":
            await query.edit_message_text(
                "📋 Trade Management\n━━━━━━━━━━━━━━━━━━━━━━━\n\nSelect an option:",
                reply_markup=get_trades_menu()
            )

        elif data == "menu_settings":
            await query.edit_message_text(
                "⚙️ Bot Settings\n━━━━━━━━━━━━━━━━━━━━━━━\n\nSelect an option:",
                reply_markup=get_settings_menu()
            )

        # Period selection for performance menu
        elif data.startswith("period_"):
            period = data.replace("period_", "")
            set_user_period(chat_id, "performance", period)
            await query.edit_message_text(
                "📈 Performance Analytics\n━━━━━━━━━━━━━━━━━━━━━━━\n\n📅 Select period, then tap a report:",
                reply_markup=get_performance_menu(period)
            )

        # Period selection for PnL menu
        elif data.startswith("pnl_period_"):
            period = data.replace("pnl_period_", "")
            set_user_period(chat_id, "pnl", period)
            await query.edit_message_text(
                "💰 Profit & Loss\n━━━━━━━━━━━━━━━━━━━━━━━\n\n📅 Select period:",
                reply_markup=get_pnl_menu(period)
            )

        # Performance commands - execute and send result as new message
        elif data == "perf_report":
            period = get_user_period(chat_id, "performance")
            # Map menu periods to report command args
            period_map = {
                "today": ["today"],
                "week": ["week"],
                "month": ["month"],
                "all": ["all"],
            }
            context.args = period_map.get(period, ["all"])
            await _execute_command_from_callback(query, context, handlers.cmd_report)

        elif data == "perf_stats":
            period = get_user_period(chat_id, "performance")
            context.args = period_to_args(period)
            await _execute_command_from_callback(query, context, handlers.cmd_stats)

        elif data == "perf_best":
            period = get_user_period(chat_id, "performance")
            context.args = period_to_args(period)
            await _execute_command_from_callback(query, context, handlers.cmd_best)

        elif data == "perf_worst":
            period = get_user_period(chat_id, "performance")
            context.args = period_to_args(period)
            await _execute_command_from_callback(query, context, handlers.cmd_worst)

        elif data == "perf_drawdown":
            period = get_user_period(chat_id, "performance")
            context.args = period_to_args(period)
            await _execute_command_from_callback(query, context, handlers.cmd_drawdown)

        elif data == "perf_streak":
            period = get_user_period(chat_id, "performance")
            context.args = period_to_args(period)
            await _execute_command_from_callback(query, context, handlers.cmd_streak)

        # PnL command
        elif data == "pnl_show":
            period = get_user_period(chat_id, "pnl")
            context.args = period_to_args(period)
            await _execute_command_from_callback(query, context, handlers.cmd_pnl)

        # Trades commands
        elif data == "trades_status":
            context.args = []
            await _execute_command_from_callback(query, context, handlers.cmd_status)

        elif data == "trades_live":
            context.args = []
            await _execute_command_from_callback(query, context, handlers.cmd_live)

        elif data == "trades_recent":
            context.args = []
            await _execute_command_from_callback(query, context, handlers.cmd_trades)

        elif data == "trades_today":
            context.args = ["today"]
            await _execute_command_from_callback(query, context, handlers.cmd_trades)

        elif data == "trades_week":
            context.args = ["week"]
            await _execute_command_from_callback(query, context, handlers.cmd_trades)

        # Settings commands
        elif data == "settings_timezone":
            # Show timezone menu instead of just viewing
            from ..database import db
            from ..config import settings
            cursor = await db.connection.execute(
                "SELECT value FROM settings WHERE key = 'timezone'"
            )
            row = await cursor.fetchone()
            current_tz = row["value"] if row else settings.timezone

            await query.edit_message_text(
                f"🌍 Timezone\n━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"Current: {current_tz}\n\n"
                f"Select a timezone or use:\n`/timezone <tz>` for custom",
                reply_markup=get_timezone_menu(current_tz),
                parse_mode="Markdown"
            )

        elif data == "settings_reporttime":
            # Show report time menu instead of just viewing
            from ..database import db
            from ..config import settings
            cursor = await db.connection.execute(
                "SELECT value FROM settings WHERE key = 'daily_report_time'"
            )
            row = await cursor.fetchone()
            current_time = row["value"] if row else settings.daily_report_time

            await query.edit_message_text(
                f"📅 Daily Report Time\n━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"Current: {current_time}\n\n"
                f"Select a new time or use:\n`/reporttime HH:MM` for custom time",
                reply_markup=get_reporttime_menu(current_time),
                parse_mode="Markdown"
            )

        elif data.startswith("reporttime_"):
            # Handle report time selection
            from ..database import db
            from ..config import settings
            from ..services.report_service import report_service
            from datetime import datetime, UTC

            new_time = data.replace("reporttime_", "")

            # Save to database
            await db.connection.execute(
                "INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?, ?, ?)",
                ("daily_report_time", new_time, datetime.now(UTC).isoformat())
            )
            await db.connection.commit()

            # Apply immediately
            await report_service.reschedule_daily_report(new_time)

            # Update menu to show new selection
            await query.edit_message_text(
                f"✅ Report time updated to: {new_time}\n\n"
                f"Daily reports will now be sent at {new_time}",
                reply_markup=get_reporttime_menu(new_time)
            )

        elif data.startswith("timezone_"):
            # Handle timezone selection
            from ..database import db
            from ..config import settings
            from ..services.report_service import report_service
            from datetime import datetime, UTC

            new_tz = data.replace("timezone_", "")

            # Save to database
            await db.connection.execute(
                "INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?, ?, ?)",
                ("timezone", new_tz, datetime.now(UTC).isoformat())
            )
            await db.connection.commit()

            # Get current report time to reschedule with new timezone
            cursor = await db.connection.execute(
                "SELECT value FROM settings WHERE key = 'daily_report_time'"
            )
            row = await cursor.fetchone()
            current_time = row["value"] if row else settings.daily_report_time

            # Apply immediately
            await report_service.reschedule_daily_report(current_time, new_tz)

            # Update menu to show new selection
            await query.edit_message_text(
                f"✅ Timezone updated to: {new_tz}\n\n"
                f"Daily reports will use this timezone.",
                reply_markup=get_timezone_menu(new_tz)
            )

        elif data == "settings_fees":
            context.args = []
            await _execute_command_from_callback(query, context, handlers.cmd_fees)

        elif data == "settings_capital":
            context.args = []
            await _execute_command_from_callback(query, context, handlers.cmd_set_capital)

        elif data == "settings_pause":
            context.args = []
            await _execute_command_from_callback(query, context, handlers.cmd_pause)

        elif data == "settings_resume":
            context.args = []
            await _execute_command_from_callback(query, context, handlers.cmd_resume)

        # Direct commands
        elif data == "cmd_export":
            context.args = []
            await _execute_command_from_callback(query, context, handlers.cmd_export)

        elif data == "cmd_help":
            context.args = []
            await _execute_command_from_callback(query, context, handlers.cmd_help)

    except RetryAfter as e:
        logger.warning(f"Rate limited by Telegram, retry after {e.retry_after}s")
    except Exception as e:
        logger.error(f"Error in menu callback: {e}")
        try:
            await query.message.reply_text(f"❌ Error: {e}")
        except RetryAfter:
            pass


# ============== Menu Command ==============

async def cmd_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the main interactive menu."""
    # Validate channel
    if _bot and not _bot.is_valid_chat(update):
        return

    await update.message.reply_text(
        "📊 Trading Bot Menu\n━━━━━━━━━━━━━━━━━━━━━━━\n\nSelect a category:",
        reply_markup=get_main_menu()
    )


def setup_menu_handlers(app, bot) -> None:
    """Register menu command and callback handlers."""
    from telegram.ext import CommandHandler

    # Store bot reference for channel validation
    global _bot
    _bot = bot

    # Add /menu command
    app.add_handler(CommandHandler("menu", cmd_menu))

    # Add callback query handler for all menu interactions
    app.add_handler(CallbackQueryHandler(menu_callback_handler))

    logger.info("Registered menu handlers")
