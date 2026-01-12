"""
Telegram Bot Command Handlers

All bot command handlers for monitoring, reporting, configuration, and control.
"""

import csv
import io
import logging
from datetime import datetime, timedelta

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from ..config import settings, exchange_config
from ..database import db
from ..services.exchange_service import exchange_service
from . import formatters

logger = logging.getLogger(__name__)

# Global reference to bot instance (set in setup_handlers)
_bot = None


def channel_only(func):
    """Decorator to restrict commands to configured channel only."""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not _bot or not _bot.is_valid_chat(update):
            return  # Silently ignore messages from other chats
        return await func(update, context)
    return wrapper


# ============== Monitoring Commands ==============

@channel_only
async def cmd_ping(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Health check command."""
    await update.message.reply_text("🏓 Pong! Bot is running.")


@channel_only
async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show open trades with unrealized PnL."""
    try:
        # Get open trades
        cursor = await db.connection.execute(
            "SELECT * FROM trades WHERE status = 'open'"
        )
        rows = await cursor.fetchall()
        open_trades = []

        for row in rows:
            trade = dict(row)
            # Get pyramids for this trade
            pyramids = await db.get_pyramids_for_trade(trade['id'])
            trade['pyramids'] = pyramids
            open_trades.append(trade)

        # Fetch current prices
        prices = {}
        for trade in open_trades:
            try:
                price_data = await exchange_service.get_price(
                    trade['exchange'], trade['base'], trade['quote']
                )
                key = f"{trade['exchange']}:{trade['base']}{trade['quote']}"
                prices[key] = price_data.price
            except Exception as e:
                logger.error(f"Failed to fetch price: {e}")

        message = formatters.format_status(open_trades, prices)
        await update.message.reply_text(message)

    except Exception as e:
        logger.error(f"Error in /status: {e}")
        await update.message.reply_text(f"❌ Error: {e}")


@channel_only
async def cmd_live(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show live prices for open positions."""
    try:
        cursor = await db.connection.execute(
            "SELECT DISTINCT exchange, base, quote FROM trades WHERE status = 'open'"
        )
        rows = await cursor.fetchall()

        if not rows:
            await update.message.reply_text("📈 No open positions")
            return

        prices = {}
        for row in rows:
            try:
                price_data = await exchange_service.get_price(
                    row['exchange'], row['base'], row['quote']
                )
                key = f"{row['exchange']}:{row['base']}/{row['quote']}"
                prices[key] = {
                    'pair': f"{row['base']}/{row['quote']}",
                    'exchange': row['exchange'],
                    'price': price_data.price,
                    'change': 0  # Would need historical data for change
                }
            except Exception as e:
                logger.error(f"Failed to fetch price: {e}")

        message = formatters.format_live(prices)
        await update.message.reply_text(message)

    except Exception as e:
        logger.error(f"Error in /live: {e}")
        await update.message.reply_text(f"❌ Error: {e}")


# ============== Reporting Commands ==============

@channel_only
async def cmd_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Generate performance report."""
    from ..services.report_service import report_service

    period = context.args[0] if context.args else "daily"

    try:
        if period == "daily":
            # Yesterday's report
            report = await report_service.generate_daily_report()
        elif period == "weekly":
            # Last 7 days
            report = await generate_period_report(7)
        elif period == "monthly":
            # Last 30 days
            report = await generate_period_report(30)
        else:
            await update.message.reply_text("Usage: /report [daily|weekly|monthly]")
            return

        message = formatters.format_report(report) if hasattr(formatters, 'format_report') else str(report)

        # Use telegram service format if available
        from ..services.telegram_service import telegram_service
        message = telegram_service.format_daily_report_message(report)

        await update.message.reply_text(message)

    except Exception as e:
        logger.error(f"Error in /report: {e}")
        await update.message.reply_text(f"❌ Error generating report: {e}")


async def generate_period_report(days: int):
    """Generate report for a period of days."""
    from ..models import DailyReportData
    from collections import defaultdict

    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)

    cursor = await db.connection.execute(
        """
        SELECT * FROM trades
        WHERE status = 'closed' AND closed_at >= ?
        """,
        (start_date.isoformat(),)
    )
    trades = await cursor.fetchall()

    total_pnl = sum(t['total_pnl_usdt'] or 0 for t in trades)
    total_notional = 0
    by_exchange = defaultdict(lambda: {"pnl": 0, "trades": 0})
    by_pair = defaultdict(float)

    for trade in trades:
        pyramids = await db.get_pyramids_for_trade(trade['id'])
        for p in pyramids:
            total_notional += p.get('notional_usdt', 0) or 0

        by_exchange[trade['exchange']]['pnl'] += trade['total_pnl_usdt'] or 0
        by_exchange[trade['exchange']]['trades'] += 1

        pair = f"{trade['base']}/{trade['quote']}"
        by_pair[pair] += trade['total_pnl_usdt'] or 0

    return DailyReportData(
        date=f"Last {days} days",
        total_trades=len(trades),
        total_pyramids=sum(len(await db.get_pyramids_for_trade(t['id'])) for t in trades),
        total_pnl_usdt=total_pnl,
        total_pnl_percent=(total_pnl / total_notional * 100) if total_notional > 0 else 0,
        by_exchange=dict(by_exchange),
        by_pair=dict(by_pair),
    )


@channel_only
async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show overall statistics."""
    try:
        stats = await get_statistics()
        message = formatters.format_stats(stats)
        await update.message.reply_text(message)
    except Exception as e:
        logger.error(f"Error in /stats: {e}")
        await update.message.reply_text(f"❌ Error: {e}")


async def get_statistics() -> dict:
    """Calculate overall trading statistics."""
    cursor = await db.connection.execute(
        "SELECT * FROM trades WHERE status = 'closed'"
    )
    trades = [dict(r) for r in await cursor.fetchall()]

    if not trades:
        return {
            'total_trades': 0, 'win_rate': 0, 'total_pnl': 0,
            'avg_win': 0, 'avg_loss': 0, 'best_trade': 0,
            'worst_trade': 0, 'profit_factor': 0, 'avg_trade': 0
        }

    pnls = [t['total_pnl_usdt'] or 0 for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]

    total_wins = sum(wins) if wins else 0
    total_losses = abs(sum(losses)) if losses else 0

    return {
        'total_trades': len(trades),
        'win_rate': (len(wins) / len(trades) * 100) if trades else 0,
        'total_pnl': sum(pnls),
        'avg_win': (total_wins / len(wins)) if wins else 0,
        'avg_loss': (sum(losses) / len(losses)) if losses else 0,
        'best_trade': max(pnls) if pnls else 0,
        'worst_trade': min(pnls) if pnls else 0,
        'profit_factor': (total_wins / total_losses) if total_losses > 0 else float('inf'),
        'avg_trade': (sum(pnls) / len(pnls)) if pnls else 0,
    }


@channel_only
async def cmd_pnl(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show total PnL summary."""
    try:
        # Realized PnL
        cursor = await db.connection.execute(
            "SELECT COALESCE(SUM(total_pnl_usdt), 0) as realized FROM trades WHERE status = 'closed'"
        )
        row = await cursor.fetchone()
        realized = row['realized'] if row else 0

        # Unrealized PnL
        cursor = await db.connection.execute(
            "SELECT * FROM trades WHERE status = 'open'"
        )
        open_trades = [dict(r) for r in await cursor.fetchall()]

        unrealized = 0
        for trade in open_trades:
            try:
                price_data = await exchange_service.get_price(
                    trade['exchange'], trade['base'], trade['quote']
                )
                pyramids = await db.get_pyramids_for_trade(trade['id'])
                for p in pyramids:
                    unrealized += (price_data.price - p['entry_price']) * p['position_size']
            except Exception:
                pass

        message = formatters.format_pnl_summary(realized, unrealized)
        await update.message.reply_text(message)

    except Exception as e:
        logger.error(f"Error in /pnl: {e}")
        await update.message.reply_text(f"❌ Error: {e}")


@channel_only
async def cmd_best(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show top 5 profitable pairs."""
    try:
        cursor = await db.connection.execute(
            """
            SELECT base || '/' || quote as pair,
                   SUM(total_pnl_usdt) as pnl,
                   COUNT(*) as trades
            FROM trades
            WHERE status = 'closed'
            GROUP BY base, quote
            ORDER BY pnl DESC
            LIMIT 5
            """
        )
        rows = await cursor.fetchall()
        pairs = [dict(r) for r in rows]
        message = formatters.format_best_worst(pairs, is_best=True)
        await update.message.reply_text(message)
    except Exception as e:
        logger.error(f"Error in /best: {e}")
        await update.message.reply_text(f"❌ Error: {e}")


@channel_only
async def cmd_worst(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show top 5 losing pairs."""
    try:
        cursor = await db.connection.execute(
            """
            SELECT base || '/' || quote as pair,
                   SUM(total_pnl_usdt) as pnl,
                   COUNT(*) as trades
            FROM trades
            WHERE status = 'closed'
            GROUP BY base, quote
            ORDER BY pnl ASC
            LIMIT 5
            """
        )
        rows = await cursor.fetchall()
        pairs = [dict(r) for r in rows]
        message = formatters.format_best_worst(pairs, is_best=False)
        await update.message.reply_text(message)
    except Exception as e:
        logger.error(f"Error in /worst: {e}")
        await update.message.reply_text(f"❌ Error: {e}")


@channel_only
async def cmd_streak(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show win/loss streak information."""
    try:
        cursor = await db.connection.execute(
            """
            SELECT total_pnl_usdt FROM trades
            WHERE status = 'closed'
            ORDER BY closed_at DESC
            """
        )
        rows = await cursor.fetchall()
        pnls = [r['total_pnl_usdt'] or 0 for r in rows]

        # Calculate current streak
        current = 0
        if pnls:
            is_win = pnls[0] > 0
            for pnl in pnls:
                if (pnl > 0) == is_win:
                    current += 1 if is_win else -1
                else:
                    break

        # Calculate longest streaks
        longest_win = longest_loss = 0
        streak = 0
        prev_win = None

        for pnl in reversed(pnls):
            is_win = pnl > 0
            if prev_win is None or is_win == prev_win:
                streak += 1
            else:
                if prev_win:
                    longest_win = max(longest_win, streak)
                else:
                    longest_loss = max(longest_loss, streak)
                streak = 1
            prev_win = is_win

        if prev_win is not None:
            if prev_win:
                longest_win = max(longest_win, streak)
            else:
                longest_loss = max(longest_loss, streak)

        message = formatters.format_streak(current, longest_win, longest_loss)
        await update.message.reply_text(message)

    except Exception as e:
        logger.error(f"Error in /streak: {e}")
        await update.message.reply_text(f"❌ Error: {e}")


@channel_only
async def cmd_drawdown(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show drawdown information."""
    try:
        cursor = await db.connection.execute(
            """
            SELECT total_pnl_usdt, closed_at FROM trades
            WHERE status = 'closed'
            ORDER BY closed_at ASC
            """
        )
        rows = await cursor.fetchall()

        if not rows:
            await update.message.reply_text("📉 No closed trades yet")
            return

        # Calculate equity curve and drawdown
        equity = 0
        peak = 0
        max_dd = 0

        for row in rows:
            equity += row['total_pnl_usdt'] or 0
            if equity > peak:
                peak = equity
            dd = peak - equity
            if dd > max_dd:
                max_dd = dd

        current_dd = peak - equity
        max_dd_percent = (max_dd / peak * 100) if peak > 0 else 0

        message = formatters.format_drawdown(max_dd, max_dd_percent, current_dd)
        await update.message.reply_text(message)

    except Exception as e:
        logger.error(f"Error in /drawdown: {e}")
        await update.message.reply_text(f"❌ Error: {e}")


# ============== History Commands ==============

@channel_only
async def cmd_trades(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show recent trades."""
    try:
        limit = int(context.args[0]) if context.args else 10
        limit = min(limit, 50)  # Cap at 50

        trades = await db.get_recent_trades(limit)
        message = formatters.format_trades_list(trades)
        await update.message.reply_text(message)

    except Exception as e:
        logger.error(f"Error in /trades: {e}")
        await update.message.reply_text(f"❌ Error: {e}")


@channel_only
async def cmd_history(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show history for specific pair."""
    if not context.args:
        await update.message.reply_text("Usage: /history <pair> (e.g., /history BTC/USDT)")
        return

    try:
        from ..services.symbol_normalizer import parse_symbol
        parsed = parse_symbol(context.args[0])

        cursor = await db.connection.execute(
            """
            SELECT * FROM trades
            WHERE base = ? AND quote = ? AND status = 'closed'
            ORDER BY closed_at DESC
            LIMIT 20
            """,
            (parsed.base, parsed.quote)
        )
        trades = [dict(r) for r in await cursor.fetchall()]

        if not trades:
            await update.message.reply_text(f"📋 No trades found for {parsed.base}/{parsed.quote}")
            return

        message = formatters.format_trades_list(trades)
        await update.message.reply_text(message)

    except Exception as e:
        logger.error(f"Error in /history: {e}")
        await update.message.reply_text(f"❌ Error: {e}")


@channel_only
async def cmd_exchange(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show stats for specific exchange."""
    if not context.args:
        await update.message.reply_text("Usage: /exchange <name> (e.g., /exchange binance)")
        return

    try:
        from ..services.symbol_normalizer import normalize_exchange
        exchange = normalize_exchange(context.args[0])

        if not exchange:
            await update.message.reply_text(f"❌ Unknown exchange: {context.args[0]}")
            return

        cursor = await db.connection.execute(
            """
            SELECT COUNT(*) as trades,
                   COALESCE(SUM(total_pnl_usdt), 0) as pnl
            FROM trades
            WHERE exchange = ? AND status = 'closed'
            """,
            (exchange,)
        )
        row = await cursor.fetchone()

        message = f"📊 {exchange.capitalize()} Stats\n\nTrades: {row['trades']}\nPnL: {formatters.format_pnl(row['pnl'])}"
        await update.message.reply_text(message)

    except Exception as e:
        logger.error(f"Error in /exchange: {e}")
        await update.message.reply_text(f"❌ Error: {e}")


# ============== Configuration Commands ==============

@channel_only
async def cmd_fees(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show exchange fees."""
    fees = {}
    for exchange_name, fee_obj in exchange_config.exchanges.items():
        fees[exchange_name] = {
            'maker_fee': fee_obj.maker_fee * 100,
            'taker_fee': fee_obj.taker_fee * 100,
        }

    message = formatters.format_fees(fees)
    await update.message.reply_text(message)


@channel_only
async def cmd_setfee(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Update exchange fee."""
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /setfee <exchange> <taker_rate>\nExample: /setfee binance 0.1")
        return

    try:
        from ..services.symbol_normalizer import normalize_exchange
        exchange = normalize_exchange(context.args[0])
        rate = float(context.args[1])

        if not exchange:
            await update.message.reply_text(f"❌ Unknown exchange: {context.args[0]}")
            return

        # Save to settings table
        await db.connection.execute(
            "INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?, ?, ?)",
            (f"fee_{exchange}_taker", str(rate), datetime.utcnow().isoformat())
        )
        await db.connection.commit()

        await update.message.reply_text(f"✅ Updated {exchange} taker fee to {rate}%")

    except ValueError:
        await update.message.reply_text("❌ Invalid rate. Use a number like 0.1")
    except Exception as e:
        logger.error(f"Error in /setfee: {e}")
        await update.message.reply_text(f"❌ Error: {e}")


@channel_only
async def cmd_timezone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """View or set timezone."""
    if not context.args:
        await update.message.reply_text(f"🕐 Current timezone: {settings.timezone}")
        return

    try:
        import pytz
        tz = context.args[0]
        pytz.timezone(tz)  # Validate timezone

        await db.connection.execute(
            "INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?, ?, ?)",
            ("timezone", tz, datetime.utcnow().isoformat())
        )
        await db.connection.commit()

        await update.message.reply_text(f"✅ Timezone set to: {tz}")

    except Exception as e:
        await update.message.reply_text(f"❌ Invalid timezone. Example: Asia/Riyadh")


@channel_only
async def cmd_reporttime(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """View or set daily report time."""
    if not context.args:
        await update.message.reply_text(f"🕐 Daily report time: {settings.daily_report_time}")
        return

    try:
        time_str = context.args[0]
        # Validate format
        datetime.strptime(time_str, "%H:%M")

        await db.connection.execute(
            "INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?, ?, ?)",
            ("daily_report_time", time_str, datetime.utcnow().isoformat())
        )
        await db.connection.commit()

        await update.message.reply_text(f"✅ Report time set to: {time_str}")

    except ValueError:
        await update.message.reply_text("❌ Invalid format. Use HH:MM (e.g., 12:00)")
    except Exception as e:
        logger.error(f"Error in /reporttime: {e}")
        await update.message.reply_text(f"❌ Error: {e}")


@channel_only
async def cmd_set_capital(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Set or clear capital amount per pyramid.

    Usage:
    /set_capital - Show all settings
    /set_capital clear - Clear all settings
    /set_capital <exchange> <pair> <timeframe> <index> <amount> - Set capital
    """
    from ..services.symbol_normalizer import parse_symbol, normalize_exchange

    if not context.args:
        # Show all pyramid capital settings
        capitals = await db.get_all_pyramid_capitals()
        if capitals:
            lines = ["💰 Pyramid Capital Settings:", ""]
            for key in sorted(capitals.keys()):
                lines.append(f"├─ {key}: ${capitals[key]:,.2f}")
            lines[-1] = lines[-1].replace("├─", "└─")  # Fix last item
            lines.append("")
            lines.append("Default: $1,000 USDT (when not set)")
            await update.message.reply_text("\n".join(lines))
        else:
            await update.message.reply_text(
                "💰 No custom capital set.\n"
                "Default: $1,000 USDT per pyramid\n\n"
                "Usage:\n"
                "/set_capital <exchange> <pair> <tf> <index> <amount>\n\n"
                "Examples:\n"
                "/set_capital kucoin ETH/USDT 1h 0 500\n"
                "/set_capital binance BTC/USDT 4h 1 2000\n\n"
                "/set_capital clear - Clear all"
            )
        return

    try:
        arg = context.args[0].lower()

        # Clear all capitals
        if arg in ("clear", "reset", "off", "none") and len(context.args) == 1:
            await db.clear_all_pyramid_capitals()
            await update.message.reply_text(
                "✅ All capital settings cleared.\n"
                "Default $1,000 USDT will be used."
            )
            return

        args = context.args

        # Require all 5 args: <exchange> <pair> <timeframe> <index> <amount>
        if len(args) < 5:
            await update.message.reply_text(
                "❌ Missing arguments.\n\n"
                "Usage: /set_capital <exchange> <pair> <tf> <index> <amount>\n"
                "Example: /set_capital kucoin ETH/USDT 1h 0 500"
            )
            return

        exchange = normalize_exchange(args[0])
        if not exchange:
            await update.message.reply_text(f"❌ Unknown exchange: {args[0]}")
            return

        parsed = parse_symbol(args[1])
        base, quote = parsed.base, parsed.quote
        timeframe = args[2].lower()
        pyramid_index = int(args[3])
        capital = args[4]

        if pyramid_index < 0:
            await update.message.reply_text("❌ Pyramid index must be 0 or greater")
            return

        # Handle clear for specific key
        if capital.lower() in ("clear", "reset", "off", "none"):
            key = await db.set_pyramid_capital(
                pyramid_index, None,
                exchange=exchange, base=base, quote=quote, timeframe=timeframe
            )
            await update.message.reply_text(
                f"✅ Capital cleared for: {key}\n"
                "Default $1,000 USDT will be used."
            )
            return

        capital_value = float(capital)
        if capital_value <= 0:
            await update.message.reply_text("❌ Capital must be positive")
            return

        key = await db.set_pyramid_capital(
            pyramid_index, capital_value,
            exchange=exchange, base=base, quote=quote, timeframe=timeframe
        )
        await update.message.reply_text(
            f"✅ Capital set: {key} = ${capital_value:,.2f}\n"
            f"Position size = ${capital_value:,.2f} / entry_price"
        )

    except ValueError as e:
        await update.message.reply_text(
            f"❌ Invalid input: {e}\n"
            "Use /set_capital for usage help."
        )
    except Exception as e:
        logger.error(f"Error in /set_capital: {e}")
        await update.message.reply_text(f"❌ Error: {e}")


# ============== Control Commands ==============

@channel_only
async def cmd_pause(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Pause signal processing."""
    try:
        await db.connection.execute(
            "INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?, ?, ?)",
            ("paused", "true", datetime.utcnow().isoformat())
        )
        await db.connection.commit()
        await update.message.reply_text("⏸️ Signal processing paused")
    except Exception as e:
        logger.error(f"Error in /pause: {e}")
        await update.message.reply_text(f"❌ Error: {e}")


@channel_only
async def cmd_resume(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Resume signal processing."""
    try:
        await db.connection.execute(
            "INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?, ?, ?)",
            ("paused", "false", datetime.utcnow().isoformat())
        )
        await db.connection.commit()
        await update.message.reply_text("▶️ Signal processing resumed")
    except Exception as e:
        logger.error(f"Error in /resume: {e}")
        await update.message.reply_text(f"❌ Error: {e}")


@channel_only
async def cmd_ignore(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Ignore signals for a pair."""
    if not context.args:
        await update.message.reply_text("Usage: /ignore <pair> (e.g., /ignore BTC/USDT)")
        return

    try:
        from ..services.symbol_normalizer import parse_symbol
        parsed = parse_symbol(context.args[0])
        pair = f"{parsed.base}/{parsed.quote}"

        # Get current ignored list
        cursor = await db.connection.execute(
            "SELECT value FROM settings WHERE key = 'ignored_pairs'"
        )
        row = await cursor.fetchone()
        ignored = row['value'].split(',') if row and row['value'] else []

        if pair not in ignored:
            ignored.append(pair)

        await db.connection.execute(
            "INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?, ?, ?)",
            ("ignored_pairs", ",".join(ignored), datetime.utcnow().isoformat())
        )
        await db.connection.commit()

        await update.message.reply_text(f"🔇 Now ignoring signals for {pair}")

    except Exception as e:
        logger.error(f"Error in /ignore: {e}")
        await update.message.reply_text(f"❌ Error: {e}")


@channel_only
async def cmd_unignore(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Resume signals for a pair."""
    if not context.args:
        await update.message.reply_text("Usage: /unignore <pair> (e.g., /unignore BTC/USDT)")
        return

    try:
        from ..services.symbol_normalizer import parse_symbol
        parsed = parse_symbol(context.args[0])
        pair = f"{parsed.base}/{parsed.quote}"

        cursor = await db.connection.execute(
            "SELECT value FROM settings WHERE key = 'ignored_pairs'"
        )
        row = await cursor.fetchone()
        ignored = row['value'].split(',') if row and row['value'] else []

        if pair in ignored:
            ignored.remove(pair)

        await db.connection.execute(
            "INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?, ?, ?)",
            ("ignored_pairs", ",".join(ignored), datetime.utcnow().isoformat())
        )
        await db.connection.commit()

        await update.message.reply_text(f"🔊 Resumed signals for {pair}")

    except Exception as e:
        logger.error(f"Error in /unignore: {e}")
        await update.message.reply_text(f"❌ Error: {e}")


# ============== Export Commands ==============

@channel_only
async def cmd_export(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Export trades to CSV."""
    try:
        cursor = await db.connection.execute(
            """
            SELECT t.*,
                   (SELECT COUNT(*) FROM pyramids WHERE trade_id = t.id) as pyramid_count
            FROM trades t
            WHERE status = 'closed'
            ORDER BY closed_at DESC
            """
        )
        trades = [dict(r) for r in await cursor.fetchall()]

        if not trades:
            await update.message.reply_text("📋 No trades to export")
            return

        # Create CSV in memory
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=[
            'id', 'exchange', 'base', 'quote', 'status',
            'created_at', 'closed_at', 'total_pnl_usdt', 'total_pnl_percent', 'pyramid_count'
        ])
        writer.writeheader()
        writer.writerows(trades)

        # Send as file
        output.seek(0)
        await update.message.reply_document(
            document=io.BytesIO(output.getvalue().encode()),
            filename=f"trades_export_{datetime.utcnow().strftime('%Y%m%d')}.csv",
            caption="📤 Trade export"
        )

    except Exception as e:
        logger.error(f"Error in /export: {e}")
        await update.message.reply_text(f"❌ Error: {e}")


@channel_only
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show help message."""
    message = formatters.format_help()
    await update.message.reply_text(message)


def setup_handlers(app: Application, bot) -> None:
    """Register all command handlers."""
    global _bot
    _bot = bot

    # Monitoring
    app.add_handler(CommandHandler("ping", cmd_ping))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("live", cmd_live))

    # Reporting
    app.add_handler(CommandHandler("report", cmd_report))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("pnl", cmd_pnl))
    app.add_handler(CommandHandler("best", cmd_best))
    app.add_handler(CommandHandler("worst", cmd_worst))
    app.add_handler(CommandHandler("streak", cmd_streak))
    app.add_handler(CommandHandler("drawdown", cmd_drawdown))

    # History
    app.add_handler(CommandHandler("trades", cmd_trades))
    app.add_handler(CommandHandler("history", cmd_history))
    app.add_handler(CommandHandler("exchange", cmd_exchange))

    # Configuration
    app.add_handler(CommandHandler("fees", cmd_fees))
    app.add_handler(CommandHandler("setfee", cmd_setfee))
    app.add_handler(CommandHandler("timezone", cmd_timezone))
    app.add_handler(CommandHandler("reporttime", cmd_reporttime))
    app.add_handler(CommandHandler("set_capital", cmd_set_capital))

    # Control
    app.add_handler(CommandHandler("pause", cmd_pause))
    app.add_handler(CommandHandler("resume", cmd_resume))
    app.add_handler(CommandHandler("ignore", cmd_ignore))
    app.add_handler(CommandHandler("unignore", cmd_unignore))

    # Export
    app.add_handler(CommandHandler("export", cmd_export))
    app.add_handler(CommandHandler("help", cmd_help))

    logger.info("Registered 22 bot command handlers")
