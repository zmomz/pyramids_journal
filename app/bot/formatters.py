"""
Message Formatters for Telegram Bot

Formats data into readable Telegram messages.
"""

from datetime import datetime, UTC
from typing import Any

import pytz

from ..config import settings


def get_local_time(utc_time: datetime | None = None) -> datetime:
    """Convert UTC time to configured timezone."""
    tz = pytz.timezone(settings.timezone)
    if utc_time is None:
        utc_time = datetime.now(UTC)
    if utc_time.tzinfo is None:
        utc_time = pytz.utc.localize(utc_time)
    return utc_time.astimezone(tz)


def format_price(price: float) -> str:
    """Format price for display."""
    if price >= 1000:
        return f"${price:,.2f}"
    elif price >= 1:
        return f"${price:.4f}"
    else:
        return f"${price:.8f}"


def format_pnl(pnl: float) -> str:
    """Format PnL with + or - prefix."""
    sign = "+" if pnl >= 0 else ""
    return f"{sign}${pnl:.2f}"


def format_percent(percent: float) -> str:
    """Format percentage with + or - prefix."""
    sign = "+" if percent >= 0 else ""
    return f"{sign}{percent:.2f}%"


def format_status(open_trades: list[dict], prices: dict[str, float]) -> str:
    """Format open trades status message."""
    if not open_trades:
        return "📊 No open trades"

    lines = ["📊 Open Trades", ""]

    for trade in open_trades:
        pair = f"{trade['base']}/{trade['quote']}"
        exchange = trade['exchange'].capitalize()
        key = f"{trade['exchange']}:{trade['base']}{trade['quote']}"
        current_price = prices.get(key, 0)

        # Calculate unrealized PnL
        pyramids = trade.get('pyramids', [])
        total_size = sum(p['position_size'] for p in pyramids)
        avg_entry = sum(p['entry_price'] * p['position_size'] for p in pyramids) / total_size if total_size > 0 else 0
        unrealized_pnl = (current_price - avg_entry) * total_size if current_price > 0 else 0

        lines.append(f"{'─' * 25}")
        lines.append(f"📈 {pair} on {exchange}")
        lines.append(f"├─ Pyramids: {len(pyramids)}")
        lines.append(f"├─ Size: {total_size:.6f} {trade['base']}")
        lines.append(f"├─ Avg Entry: {format_price(avg_entry)}")
        lines.append(f"├─ Current: {format_price(current_price)}")
        lines.append(f"└─ Unrealized: {format_pnl(unrealized_pnl)}")

    return "\n".join(lines)


def format_live(prices: dict[str, dict]) -> str:
    """Format live prices message."""
    if not prices:
        return "📈 No open positions to track"

    lines = ["📈 Live Prices", ""]

    for key, data in prices.items():
        pair = data.get('pair', key)
        exchange = data.get('exchange', '').capitalize()
        price = data.get('price', 0)
        change = data.get('change', 0)

        emoji = "🟢" if change >= 0 else "🔴"
        lines.append(f"{emoji} {pair} ({exchange}): {format_price(price)} ({format_percent(change)})")

    return "\n".join(lines)


def format_stats(stats: dict[str, Any]) -> str:
    """Format statistics message with optional period label."""
    period_label = stats.get('period_label', 'All-Time')
    title = f"📊 Statistics - {period_label}"

    lines = [
        title,
        "━" * 30,
        f"Total Trades: {stats.get('total_trades', 0)}",
        f"Win Rate: {stats.get('win_rate', 0):.1f}%",
        f"Total PnL: {format_pnl(stats.get('total_pnl', 0))}",
        "",
        f"Avg Win: {format_pnl(stats.get('avg_win', 0))}",
        f"Avg Loss: {format_pnl(stats.get('avg_loss', 0))}",
        f"Best Trade: {format_pnl(stats.get('best_trade', 0))}",
        f"Worst Trade: {format_pnl(stats.get('worst_trade', 0))}",
        "",
        f"Profit Factor: {stats.get('profit_factor', 0):.2f}",
        f"Avg Trade: {format_pnl(stats.get('avg_trade', 0))}",
    ]
    return "\n".join(lines)


def format_pnl_summary(realized: float, unrealized: float) -> str:
    """Format PnL summary message."""
    total = realized + unrealized
    separator = "- - - - - - - - - - - - - - - - - - "

    # Use 🟢 for positive, 🔻 for negative net PnL
    pnl_emoji = "🟢" if total >= 0 else "🔻"

    lines = [
        "💰 PnL Summary",
        separator,
        f"Realized PnL: {format_pnl(realized)}",
        f"Unrealized PnL: {format_pnl(unrealized)}",
        separator,
        f"{pnl_emoji} Net PnL: {format_pnl(total)}",
    ]
    return "\n".join(lines)


def format_best_worst(pairs: list[dict], is_best: bool, period_label: str = "All-Time") -> str:
    """Format best/worst pairs message with optional period label."""
    emoji = "🏆" if is_best else "📉"
    title = "Best Pairs" if is_best else "Worst Pairs"

    if not pairs:
        return f"{emoji} No data available"

    lines = [f"{emoji} {title} - {period_label}", "━" * 30]

    for i, pair in enumerate(pairs[:5], 1):
        medal = ["🥇", "🥈", "🥉", "4.", "5."][i - 1]
        lines.append(f"{medal} {pair['pair']}: {format_pnl(pair['pnl'])} ({pair['trades']} trades)")

    return "\n".join(lines)


def format_streak(current: int, longest_win: int, longest_loss: int, period_label: str = "All-Time") -> str:
    """Format streak information with optional period label."""
    if current > 0:
        streak_text = f"🔥 {current} wins"
    elif current < 0:
        streak_text = f"❄️ {abs(current)} losses"
    else:
        streak_text = "➖ No active streak"

    lines = [
        f"📊 Streak Info - {period_label}",
        "━" * 30,
        f"Current: {streak_text}",
        f"Longest Win Streak: {longest_win}",
        f"Longest Loss Streak: {longest_loss}",
    ]
    return "\n".join(lines)


def format_drawdown(max_dd: float, max_dd_percent: float, current_dd: float, period_label: str = "All-Time") -> str:
    """Format drawdown information with optional period label."""
    lines = [
        f"📉 Drawdown Info - {period_label}",
        "━" * 30,
        f"Max Drawdown: {format_pnl(-max_dd)} ({format_percent(-max_dd_percent)})",
        f"Current Drawdown: {format_pnl(-current_dd)}",
    ]
    return "\n".join(lines)


def format_trades_list(trades: list[dict], page: int = 1, per_page: int = 10) -> str:
    """Format trades list message."""
    if not trades:
        return "📋 No trades found"

    lines = [f"📋 Recent Trades (Page {page})", ""]

    for trade in trades:
        pair = f"{trade['base']}/{trade['quote']}"
        exchange = trade['exchange'].capitalize()
        pnl = trade.get('total_pnl_usdt', 0) or 0
        emoji = "🟢" if pnl >= 0 else "🔴"
        date = trade.get('closed_at', '')[:10] if trade.get('closed_at') else 'Open'

        lines.append(f"{emoji} {pair} ({exchange}) | {format_pnl(pnl)} | {date}")

    return "\n".join(lines)


def format_fees(fees: dict[str, dict]) -> str:
    """Format exchange fees message."""
    lines = ["💸 Exchange Fees", ""]

    for exchange, fee_data in fees.items():
        maker = fee_data.get('maker_fee', 0)
        taker = fee_data.get('taker_fee', 0)
        lines.append(f"{exchange.capitalize()}: Maker {maker}% | Taker {taker}%")

    return "\n".join(lines)


def format_help() -> str:
    """Format help message with all commands."""
    return """📖 Available Commands

🎛️ Interactive Menu
/menu - Open interactive menu with buttons

📊 Monitoring
/status - Open trades with unrealized PnL
/live - Real-time prices
/ping - Health check

📈 Reporting (all support: today|week|month|YYYY-MM-DD)
/report [period] - Performance report with chart
/stats [period] - Overall statistics
/pnl [period] - PnL summary
/best [period] - Top 5 profitable pairs
/worst [period] - Top 5 losing pairs
/streak [period] - Win/loss streak
/drawdown [period] - Drawdown info

📋 History
/trades [n|period] - Recent trades
/history <pair> - History for pair
/exchange <name> [period] - Stats by exchange

⚙️ Configuration
/fees - Show exchange fees
/setfee <exchange> <rate> - Update fee
/timezone [zone] - View/set timezone
/reporttime [HH:MM] - Set report time
/signals_channel [id] - Set signals channel

🎛️ Control
/pause - Pause signal processing
/resume - Resume processing
/ignore <pair> - Ignore signals
/unignore <pair> - Resume signals

📤 Export
/export - Export trades to CSV

🗑️ Data Management
/reset - Reset/clear data options

/help - This message

📅 Period options: today, yesterday, week, month, or YYYY-MM-DD"""
