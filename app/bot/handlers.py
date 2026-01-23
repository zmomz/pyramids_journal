"""
Telegram Bot Command Handlers

All bot command handlers for monitoring, reporting, configuration, and control.
"""

import asyncio
import csv
import io
import logging
from datetime import datetime, timedelta, UTC
from typing import Tuple

import pytz
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from ..config import settings, exchange_config
from ..database import db
from ..services.exchange_service import exchange_service
from . import formatters

logger = logging.getLogger(__name__)


def parse_date_filter(args: list[str]) -> Tuple[str | None, str | None, str]:
    """
    Parse date filter from command arguments.

    Args:
        args: List of command arguments

    Returns:
        Tuple of (start_date, end_date, period_label)
        - start_date: YYYY-MM-DD or None for all-time
        - end_date: YYYY-MM-DD or None for all-time
        - period_label: Human readable label for the period

    Examples:
        [] -> (None, None, "All-Time")
        ["today"] -> ("2026-01-20", "2026-01-20", "Today (2026-01-20)")
        ["yesterday"] -> ("2026-01-19", "2026-01-19", "Yesterday (2026-01-19)")
        ["week"] -> ("2026-01-13", "2026-01-20", "Last 7 Days")
        ["month"] -> ("2025-12-21", "2026-01-20", "Last 30 Days")
        ["2026-01-15"] -> ("2026-01-15", "2026-01-15", "2026-01-15")
    """
    tz = pytz.timezone(settings.timezone)
    now = datetime.now(tz)
    today = now.strftime("%Y-%m-%d")

    if not args:
        return None, None, "All-Time"

    period = args[0].lower()

    if period == "today":
        return today, today, f"Today ({today})"

    elif period == "yesterday":
        yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d")
        return yesterday, yesterday, f"Yesterday ({yesterday})"

    elif period == "week":
        start = (now - timedelta(days=6)).strftime("%Y-%m-%d")
        return start, today, "Last 7 Days"

    elif period == "month":
        start = (now - timedelta(days=29)).strftime("%Y-%m-%d")
        return start, today, "Last 30 Days"

    elif "-" in period and len(period) == 10:
        # Specific date YYYY-MM-DD
        try:
            datetime.strptime(period, "%Y-%m-%d")  # Validate format
            return period, period, period
        except ValueError:
            return None, None, "All-Time"

    else:
        return None, None, "All-Time"

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
            # Skip orphan trades (no pyramids due to validation failure)
            if not pyramids:
                continue
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

        # Telegram has 4096 character limit per message
        if len(message) <= 4096:
            await update.message.reply_text(message)
        else:
            # Split message into chunks, keeping multi-line entries together
            chunks = []
            current_chunk = ""
            lines = message.split('\n')
            i = 0
            while i < len(lines):
                line = lines[i]
                # Group detail lines (start with │ or spaces) with their parent
                block = line
                if i + 1 < len(lines) and (lines[i + 1].startswith('│') or lines[i + 1].startswith('   ')):
                    block = line + '\n' + lines[i + 1]
                    i += 1

                if len(current_chunk) + len(block) + 1 > 4096:
                    chunks.append(current_chunk)
                    current_chunk = block
                else:
                    current_chunk = current_chunk + '\n' + block if current_chunk else block
                i += 1

            if current_chunk:
                chunks.append(current_chunk)

            for i, chunk in enumerate(chunks):
                try:
                    await update.message.reply_text(chunk)
                    # Add delay between chunks to avoid Telegram rate limiting
                    if i < len(chunks) - 1:
                        await asyncio.sleep(0.5)
                except Exception as e:
                    logger.error(f"Failed to send chunk {i+1}/{len(chunks)}: {e}")

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
    """Generate performance report with equity curve chart.

    Usage:
        /report - All-time report
        /report today - Today's report (trades so far)
        /report yesterday - Yesterday's daily report
        /report YYYY-MM-DD - Report for specific date
        /report week - Last 7 days
        /report month - Last 30 days
    """
    from ..services.report_service import report_service
    from ..services.telegram_service import telegram_service

    # Handle both direct messages and callback queries (menu buttons)
    message = update.message or (update.callback_query.message if update.callback_query else None)
    if not message:
        logger.error("No message context available for /report")
        return

    period = context.args[0] if context.args else "all"

    try:
        date = None
        report = None

        if period == "yesterday":
            # Yesterday's report
            report = await report_service.generate_daily_report()
            date = report.date
        elif period == "today":
            # Today's report
            import pytz
            tz = pytz.timezone(settings.timezone)
            today = datetime.now(tz).strftime("%Y-%m-%d")
            report = await report_service.generate_daily_report(today)
            date = today
        elif "-" in period and len(period) == 10:
            # Specific date (YYYY-MM-DD format)
            date = period
            report = await report_service.generate_daily_report(date)
        elif period == "week":
            # Last 7 days
            report = await generate_period_report(7)
        elif period == "month":
            # Last 30 days
            report = await generate_period_report(30)
        elif period == "all":
            # All-time report
            report = await generate_period_report(None)
        else:
            await message.reply_text(
                "Usage:\n"
                "/report - All-time report\n"
                "/report today - Today's trades\n"
                "/report yesterday - Yesterday's report\n"
                "/report 2026-01-20 - Specific date\n"
                "/report week - Last 7 days\n"
                "/report month - Last 30 days"
            )
            return

        # Send equity curve chart if available
        if settings.equity_curve_enabled and report.equity_points and len(report.equity_points) >= 2:
            chart_image = telegram_service.generate_equity_curve_image(
                report.equity_points, report.date, report.chart_stats
            )
            if chart_image:
                await message.reply_photo(photo=chart_image)
                logger.info("Equity curve chart sent via /report command")

        # Send the text report (handle long messages)
        report_text = telegram_service.format_daily_report_message(report)

        if len(report_text) <= 4096:
            await message.reply_text(report_text)
        else:
            # Split message into chunks, keeping 2-line trade entries together
            chunks = []
            current_chunk = ""
            lines = report_text.split('\n')
            i = 0
            while i < len(lines):
                line = lines[i]
                # Check if next line is a detail line (starts with │ or spaces for trade details)
                # Group them together to avoid splitting trade entries
                block = line
                if i + 1 < len(lines) and (lines[i + 1].startswith('│') or lines[i + 1].startswith('   ')):
                    block = line + '\n' + lines[i + 1]
                    i += 1

                if len(current_chunk) + len(block) + 1 > 4096:
                    chunks.append(current_chunk)
                    current_chunk = block
                else:
                    current_chunk = current_chunk + '\n' + block if current_chunk else block
                i += 1

            if current_chunk:
                chunks.append(current_chunk)

            for i, chunk in enumerate(chunks):
                try:
                    await message.reply_text(chunk)
                    # Add delay between chunks to avoid Telegram rate limiting
                    if i < len(chunks) - 1:
                        await asyncio.sleep(0.5)
                except Exception as e:
                    logger.error(f"Failed to send chunk {i+1}/{len(chunks)}: {e}")

    except Exception as e:
        logger.error(f"Error in /report: {e}")
        await message.reply_text(f"❌ Error generating report: {e}")


async def generate_period_report(days: int | None):
    """Generate report for a period of days, or all-time if days is None.

    Returns the same level of detail as generate_daily_report() including:
    - trades[] list with TradeHistoryItem objects
    - equity_points[] for equity curve chart
    - chart_stats for chart footer statistics
    """
    from ..models import DailyReportData, TradeHistoryItem, EquityPoint, ChartStats
    from collections import defaultdict

    # Convert days to date range
    tz = pytz.timezone(settings.timezone)
    end_date = datetime.now(tz).strftime("%Y-%m-%d")

    if days is not None:
        start_dt = datetime.now(tz) - timedelta(days=days - 1)
        start_date = start_dt.strftime("%Y-%m-%d")
        period_label = f"Last {days} Days"
    else:
        start_date = None
        end_date = None
        period_label = "All-Time"

    # Use shared database functions (same as other commands)
    stats = await db.get_statistics_for_period(start_date, end_date)

    if stats["total_trades"] == 0:
        return DailyReportData(
            date=period_label,
            total_trades=0,
            total_pyramids=0,
            total_pnl_usdt=0.0,
            total_pnl_percent=0.0,
            trades=[],
            by_exchange={},
            by_timeframe={},
            by_pair={},
        )

    # Get trades and build trade history
    trades = await db.get_trades_for_period(start_date, end_date, limit=1000)

    total_capital = 0.0
    total_pyramids = 0
    trade_history: list[TradeHistoryItem] = []
    by_timeframe: dict = defaultdict(lambda: {"pnl": 0.0, "trades": 0})
    by_pair: dict = defaultdict(float)

    for trade in trades:
        pyramids = await db.get_pyramids_for_trade(trade['id'])
        pyramids_count = len(pyramids)
        total_pyramids += pyramids_count

        for p in pyramids:
            total_capital += p.get('capital_usdt', 0) or 0

        pnl = trade.get('total_pnl_usdt', 0) or 0
        pnl_percent = trade.get('total_pnl_percent', 0) or 0
        pair = f"{trade['base']}/{trade['quote']}"
        timeframe = trade.get('timeframe') or 'N/A'

        trade_history.append(TradeHistoryItem(
            group_id=trade.get('group_id') or trade['id'][:8],
            exchange=trade['exchange'],
            pair=pair,
            timeframe=timeframe,
            pyramids_count=pyramids_count,
            pnl_usdt=pnl,
            pnl_percent=pnl_percent,
        ))

        by_timeframe[timeframe]['pnl'] += pnl
        by_timeframe[timeframe]['trades'] += 1
        by_pair[pair] += pnl

    # Sort by PnL (best first)
    trade_history.sort(key=lambda x: x.pnl_usdt, reverse=True)

    # Get exchange breakdown
    exchange_stats = await db.get_exchange_stats_for_period(start_date, end_date)
    by_exchange = {
        row["exchange"]: {"pnl": row["pnl"], "trades": row["trades"]}
        for row in exchange_stats
    }

    # Calculate total PnL and percent
    total_pnl_usdt = stats["total_pnl"]
    total_pnl_percent = (total_pnl_usdt / total_capital * 100) if total_capital > 0 else 0

    # Build equity curve
    equity_points: list[EquityPoint] = []
    if settings.equity_curve_enabled:
        equity_data = await db.get_equity_curve_data_for_period(start_date, end_date)
        # Start from 0 - period reports show only this period's performance
        running_pnl = 0.0
        for row in equity_data:
            running_pnl += row.get("total_pnl_usdt", 0) or 0
            closed_at = row.get("closed_at")
            if closed_at:
                try:
                    timestamp = datetime.fromisoformat(closed_at) if isinstance(closed_at, str) else closed_at
                    equity_points.append(EquityPoint(
                        timestamp=timestamp,
                        cumulative_pnl=running_pnl
                    ))
                except (ValueError, TypeError):
                    pass

    # Build chart stats
    chart_stats = None
    if settings.equity_curve_enabled and trade_history:
        drawdown_data = await db.get_drawdown_for_period(start_date, end_date)

        avg_win = stats["avg_win"]
        avg_loss = abs(stats["avg_loss"]) if stats["avg_loss"] else 0
        win_loss_ratio = (avg_win / avg_loss) if avg_loss > 0 else avg_win

        # Get trade counts for the period
        trade_counts = await db.get_trade_counts_for_period(start_date, end_date)

        chart_stats = ChartStats(
            total_net_pnl=total_pnl_usdt,
            max_drawdown_percent=drawdown_data["max_drawdown_percent"],
            max_drawdown_usdt=drawdown_data["max_drawdown"],
            trades_opened_today=trade_counts["opened_in_period"],
            trades_closed_today=trade_counts["closed_in_period"],
            win_rate=stats["win_rate"],
            total_used_equity=total_capital,
            profit_factor=stats["profit_factor"],
            win_loss_ratio=win_loss_ratio,
            cumulative_pnl=total_pnl_usdt,
        )

    return DailyReportData(
        date=period_label,
        total_trades=stats["total_trades"],
        total_pyramids=total_pyramids,
        total_pnl_usdt=total_pnl_usdt,
        total_pnl_percent=total_pnl_percent,
        trades=trade_history,
        by_exchange=by_exchange,
        by_timeframe=dict(by_timeframe),
        by_pair=dict(by_pair),
        equity_points=equity_points,
        chart_stats=chart_stats,
    )


@channel_only
async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show statistics with optional date filtering.

    Usage:
        /stats - All-time statistics
        /stats today - Today's statistics
        /stats yesterday - Yesterday's statistics
        /stats week - Last 7 days
        /stats month - Last 30 days
        /stats 2026-01-20 - Specific date
    """
    try:
        # Parse date filter
        start_date, end_date, period_label = parse_date_filter(context.args or [])

        # Get statistics for the period
        stats = await db.get_statistics_for_period(start_date, end_date)
        stats['period_label'] = period_label

        message = formatters.format_stats(stats)
        await update.message.reply_text(message)
    except Exception as e:
        logger.error(f"Error in /stats: {e}")
        await update.message.reply_text(f"❌ Error: {e}")


async def get_statistics() -> dict:
    """Calculate overall trading statistics (legacy function for backward compat)."""
    return await db.get_statistics_for_period(None, None)


@channel_only
async def cmd_pnl(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show PnL summary with optional date filtering.

    Usage:
        /pnl - All-time realized + unrealized
        /pnl today - Today's closed trades
        /pnl yesterday - Yesterday's closed trades
        /pnl week - Last 7 days
        /pnl month - Last 30 days
        /pnl 2026-01-20 - Specific date
    """
    try:
        # Parse date filter
        start_date, end_date, period_label = parse_date_filter(context.args or [])

        # Get realized PnL for the period
        realized, trade_count = await db.get_realized_pnl_for_period(start_date, end_date)

        # For all-time, also show unrealized
        unrealized = 0.0
        open_count = 0
        if start_date is None:
            # All-time view: include unrealized
            cursor = await db.connection.execute(
                "SELECT * FROM trades WHERE status = 'open'"
            )
            open_trades = [dict(r) for r in await cursor.fetchall()]
            open_count = len(open_trades)

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

        # Format message based on period
        if start_date is None:
            # All-time format (original)
            message = formatters.format_pnl_summary(realized, unrealized)
        else:
            # Period-specific format
            total = realized + unrealized
            pnl_emoji = "🟢" if total >= 0 else "🔻"

            lines = [
                f"💰 PnL Summary - {period_label}",
                "━" * 30,
                f"Closed Trades: {formatters.format_pnl(realized)} ({trade_count} trades)",
            ]

            if open_count > 0:
                lines.append(f"Open Trades: {formatters.format_pnl(unrealized)} ({open_count} trades)")
                lines.append("━" * 30)
                lines.append(f"{pnl_emoji} Period Net: {formatters.format_pnl(total)}")
            else:
                lines.append("━" * 30)
                lines.append(f"{pnl_emoji} Period Net: {formatters.format_pnl(realized)}")

            # Also show cumulative context
            all_time_realized, _ = await db.get_realized_pnl_for_period(None, None)
            lines.append("")
            lines.append(f"💼 Cumulative Realized: {formatters.format_pnl(all_time_realized)}")

            message = "\n".join(lines)

        await update.message.reply_text(message)

    except Exception as e:
        logger.error(f"Error in /pnl: {e}")
        await update.message.reply_text(f"❌ Error: {e}")


@channel_only
async def cmd_best(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show top 5 profitable pairs with optional date filtering.

    Usage:
        /best - All-time best pairs
        /best today - Today's best pairs
        /best yesterday - Yesterday's best pairs
        /best week - Last 7 days
        /best month - Last 30 days
        /best 2026-01-20 - Specific date
    """
    try:
        # Parse date filter
        start_date, end_date, period_label = parse_date_filter(context.args or [])

        # Get best pairs for the period
        pairs = await db.get_best_pairs_for_period(start_date, end_date, limit=5)
        message = formatters.format_best_worst(pairs, is_best=True, period_label=period_label)
        await update.message.reply_text(message)
    except Exception as e:
        logger.error(f"Error in /best: {e}")
        await update.message.reply_text(f"❌ Error: {e}")


@channel_only
async def cmd_worst(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show top 5 losing pairs with optional date filtering.

    Usage:
        /worst - All-time worst pairs
        /worst today - Today's worst pairs
        /worst yesterday - Yesterday's worst pairs
        /worst week - Last 7 days
        /worst month - Last 30 days
        /worst 2026-01-20 - Specific date
    """
    try:
        # Parse date filter
        start_date, end_date, period_label = parse_date_filter(context.args or [])

        # Get worst pairs for the period
        pairs = await db.get_worst_pairs_for_period(start_date, end_date, limit=5)
        message = formatters.format_best_worst(pairs, is_best=False, period_label=period_label)
        await update.message.reply_text(message)
    except Exception as e:
        logger.error(f"Error in /worst: {e}")
        await update.message.reply_text(f"❌ Error: {e}")


@channel_only
async def cmd_streak(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show win/loss streak information with optional date filtering.

    Usage:
        /streak - All-time streaks
        /streak today - Today's streaks
        /streak yesterday - Yesterday's streaks
        /streak week - Last 7 days
        /streak month - Last 30 days
        /streak 2026-01-20 - Specific date
    """
    try:
        # Parse date filter
        start_date, end_date, period_label = parse_date_filter(context.args or [])

        # Get streak info for the period
        streak_data = await db.get_streak_for_period(start_date, end_date)

        message = formatters.format_streak(
            streak_data['current'],
            streak_data['longest_win'],
            streak_data['longest_loss'],
            period_label=period_label
        )
        await update.message.reply_text(message)

    except Exception as e:
        logger.error(f"Error in /streak: {e}")
        await update.message.reply_text(f"❌ Error: {e}")


@channel_only
async def cmd_drawdown(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show drawdown information with optional date filtering.

    Usage:
        /drawdown - All-time drawdown
        /drawdown today - Today's drawdown
        /drawdown yesterday - Yesterday's drawdown
        /drawdown week - Last 7 days
        /drawdown month - Last 30 days
        /drawdown 2026-01-20 - Specific date
    """
    try:
        # Parse date filter
        start_date, end_date, period_label = parse_date_filter(context.args or [])

        # Get drawdown info for the period
        dd_data = await db.get_drawdown_for_period(start_date, end_date)

        if dd_data['trade_count'] == 0:
            await update.message.reply_text(f"📉 No closed trades for {period_label}")
            return

        message = formatters.format_drawdown(
            dd_data['max_drawdown'],
            dd_data['max_drawdown_percent'],
            dd_data['current_drawdown'],
            period_label=period_label
        )
        await update.message.reply_text(message)

    except Exception as e:
        logger.error(f"Error in /drawdown: {e}")
        await update.message.reply_text(f"❌ Error: {e}")


# ============== History Commands ==============

@channel_only
async def cmd_trades(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show recent trades with optional date filtering.

    Usage:
        /trades - Last 10 trades
        /trades 20 - Last 20 trades
        /trades today - Today's trades
        /trades yesterday - Yesterday's trades
        /trades week - Last 7 days
        /trades month - Last 30 days
        /trades 2026-01-20 - Specific date
    """
    try:
        args = context.args or []

        # Check if first arg is a number (limit)
        if args and args[0].isdigit():
            limit = min(int(args[0]), 50)
            trades = await db.get_recent_trades(limit)
            message = formatters.format_trades_list(trades)
        else:
            # Parse date filter
            start_date, end_date, period_label = parse_date_filter(args)

            if start_date is None:
                # All-time, use limit
                trades = await db.get_recent_trades(10)
                message = formatters.format_trades_list(trades)
            else:
                # Get trades for the period
                trades = await db.get_trades_for_period(start_date, end_date, limit=50)
                if not trades:
                    await update.message.reply_text(f"📋 No trades for {period_label}")
                    return
                message = f"📋 Trades - {period_label}\n\n"
                for trade in trades:
                    pair = f"{trade['base']}/{trade['quote']}"
                    exchange = trade['exchange'].capitalize()
                    pnl = trade.get('total_pnl_usdt', 0) or 0
                    emoji = "🟢" if pnl >= 0 else "🔴"
                    date = trade.get('closed_at', '')[:10] if trade.get('closed_at') else 'Open'
                    message += f"{emoji} {pair} ({exchange}) | {formatters.format_pnl(pnl)} | {date}\n"

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
    """Show stats for specific exchange with optional date filtering.

    Usage:
        /exchange binance - All-time stats for Binance
        /exchange binance today - Today's stats
        /exchange binance week - Last 7 days
        /exchange binance month - Last 30 days
        /exchange binance 2026-01-20 - Specific date
    """
    if not context.args:
        await update.message.reply_text(
            "Usage: /exchange <name> [period]\n"
            "Examples:\n"
            "/exchange binance\n"
            "/exchange binance today\n"
            "/exchange binance week"
        )
        return

    try:
        from ..services.symbol_normalizer import normalize_exchange
        exchange = normalize_exchange(context.args[0])

        if not exchange:
            await update.message.reply_text(f"❌ Unknown exchange: {context.args[0]}")
            return

        # Parse date filter from remaining args
        start_date, end_date, period_label = parse_date_filter(context.args[1:] if len(context.args) > 1 else [])

        # Build query based on date filter
        if start_date is None:
            # All-time
            cursor = await db.connection.execute(
                """
                SELECT COUNT(*) as trades,
                       COALESCE(SUM(total_pnl_usdt), 0) as pnl
                FROM trades
                WHERE exchange = ? AND status = 'closed'
                """,
                (exchange,)
            )
        else:
            # Date filtered
            cursor = await db.connection.execute(
                """
                SELECT COUNT(*) as trades,
                       COALESCE(SUM(total_pnl_usdt), 0) as pnl
                FROM trades
                WHERE exchange = ? AND status = 'closed'
                  AND DATE(closed_at) BETWEEN ? AND ?
                """,
                (exchange, start_date, end_date)
            )

        row = await cursor.fetchone()

        pnl_emoji = "🟢" if row['pnl'] >= 0 else "🔴"
        message = f"""📊 {exchange.capitalize()} Stats - {period_label}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Trades: {row['trades']}
{pnl_emoji} PnL: {formatters.format_pnl(row['pnl'])}"""
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
            (f"fee_{exchange}_taker", str(rate), datetime.now(UTC).isoformat())
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
    from ..services.report_service import report_service

    if not context.args:
        # Read from DB first, fallback to settings
        cursor = await db.connection.execute(
            "SELECT value FROM settings WHERE key = 'timezone'"
        )
        row = await cursor.fetchone()
        current_tz = row["value"] if row else settings.timezone
        await update.message.reply_text(f"🌍 Timezone: {current_tz}")
        return

    try:
        import pytz
        tz_str = context.args[0]
        pytz.timezone(tz_str)  # Validate timezone

        await db.connection.execute(
            "INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?, ?, ?)",
            ("timezone", tz_str, datetime.now(UTC).isoformat())
        )
        await db.connection.commit()

        # Get current report time from DB to reschedule with new timezone
        cursor = await db.connection.execute(
            "SELECT value FROM settings WHERE key = 'daily_report_time'"
        )
        row = await cursor.fetchone()
        current_time = row["value"] if row else settings.daily_report_time

        # Apply immediately by rescheduling with new timezone
        await report_service.reschedule_daily_report(current_time, tz_str)

        await update.message.reply_text(f"✅ Timezone set to: {tz_str}")

    except pytz.UnknownTimeZoneError:
        await update.message.reply_text("❌ Invalid timezone. Example: America/New_York, Asia/Tokyo")
    except Exception as e:
        logger.error(f"Error in /timezone: {e}")
        await update.message.reply_text(f"❌ Error: {e}")


@channel_only
async def cmd_reporttime(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """View or set daily report time."""
    from ..services.report_service import report_service

    if not context.args:
        # Read from DB first, fallback to settings
        cursor = await db.connection.execute(
            "SELECT value FROM settings WHERE key = 'daily_report_time'"
        )
        row = await cursor.fetchone()
        current_time = row["value"] if row else settings.daily_report_time
        await update.message.reply_text(f"🕐 Daily report time: {current_time}")
        return

    try:
        time_str = context.args[0]
        # Validate format
        datetime.strptime(time_str, "%H:%M")

        await db.connection.execute(
            "INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?, ?, ?)",
            ("daily_report_time", time_str, datetime.now(UTC).isoformat())
        )
        await db.connection.commit()

        # Apply immediately by rescheduling
        await report_service.reschedule_daily_report(time_str)

        await update.message.reply_text(f"✅ Report time set to: {time_str}")

    except ValueError:
        await update.message.reply_text("❌ Invalid format. Use HH:MM (e.g., 12:00)")
    except Exception as e:
        logger.error(f"Error in /reporttime: {e}")
        await update.message.reply_text(f"❌ Error: {e}")


@channel_only
async def cmd_signals_channel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """View or set the signals-only channel ID."""
    if not context.args:
        # Show current setting
        cursor = await db.connection.execute(
            "SELECT value FROM settings WHERE key = 'signals_channel_id'"
        )
        row = await cursor.fetchone()
        current = row['value'] if row else settings.telegram_signals_channel_id

        if current:
            await update.message.reply_text(f"📢 Signals channel ID: {current}")
        else:
            await update.message.reply_text(
                "📢 No signals channel configured.\n\n"
                "Usage: /signals_channel <channel_id>\n"
                "Example: /signals_channel -1001234567890\n\n"
                "To get channel ID:\n"
                "1. Add the bot to your channel as admin\n"
                "2. Forward a message from channel to @userinfobot\n\n"
                "Use /signals_channel off to disable"
            )
        return

    try:
        channel_id = context.args[0]

        # Handle disable
        if channel_id.lower() in ("off", "disable", "none", "clear"):
            await db.connection.execute(
                "DELETE FROM settings WHERE key = 'signals_channel_id'"
            )
            await db.connection.commit()
            await update.message.reply_text("✅ Signals channel disabled")
            return

        # Validate it looks like a channel ID (negative number)
        if not channel_id.startswith("-"):
            await update.message.reply_text(
                "❌ Invalid channel ID. Channel IDs start with - (e.g., -1001234567890)"
            )
            return

        # Test sending a message to verify the channel works
        from ..services.telegram_service import telegram_service
        try:
            await telegram_service.bot.send_message(
                chat_id=channel_id,
                text="✅ Signals channel connected successfully!"
            )
        except Exception as e:
            await update.message.reply_text(
                f"❌ Failed to send to channel: {e}\n\n"
                "Make sure the bot is an admin in that channel."
            )
            return

        # Save to database
        await db.connection.execute(
            "INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?, ?, ?)",
            ("signals_channel_id", channel_id, datetime.now(UTC).isoformat())
        )
        await db.connection.commit()

        await update.message.reply_text(f"✅ Signals channel set to: {channel_id}")

    except Exception as e:
        logger.error(f"Error in /signals_channel: {e}")
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
            ("paused", "true", datetime.now(UTC).isoformat())
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
            ("paused", "false", datetime.now(UTC).isoformat())
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
            ("ignored_pairs", ",".join(ignored), datetime.now(UTC).isoformat())
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
            ("ignored_pairs", ",".join(ignored), datetime.now(UTC).isoformat())
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
            'id', 'exchange', 'base', 'quote', 'position_side', 'timeframe', 'group_id',
            'status', 'created_at', 'closed_at', 'total_pnl_usdt', 'total_pnl_percent', 'pyramid_count'
        ])
        writer.writeheader()
        writer.writerows(trades)

        # Send as file
        output.seek(0)
        await update.message.reply_document(
            document=io.BytesIO(output.getvalue().encode()),
            filename=f"trades_export_{datetime.now(UTC).strftime('%Y%m%d')}.csv",
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


# ============== Data Management Commands ==============

@channel_only
async def cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reset/clear data from database.

    Usage:
        /reset - Show reset options
        /reset trades CONFIRM - Clear all trade data
        /reset settings CONFIRM - Clear all settings
        /reset cache CONFIRM - Clear cached data
        /reset all CONFIRM - Full database reset
    """
    args = context.args if context.args else []

    if not args:
        # Show help
        message = """🗑️ Data Reset Options

/reset trades CONFIRM
  Clear all trades, pyramids, exits, sequences

/reset settings CONFIRM
  Clear capital settings and other configs

/reset cache CONFIRM
  Clear symbol rules cache and daily reports

/reset all CONFIRM
  Full database reset (everything above)

⚠️ WARNING: These actions are irreversible!
You must add CONFIRM at the end to execute."""
        await update.message.reply_text(message)
        return

    reset_type = args[0].lower()
    confirmed = len(args) > 1 and args[1].upper() == "CONFIRM"

    if not confirmed:
        await update.message.reply_text(
            f"⚠️ To reset {reset_type}, use:\n/reset {reset_type} CONFIRM"
        )
        return

    try:
        if reset_type == "trades":
            counts = await db.reset_trades()
            message = f"""✅ Trade Data Cleared

Deleted:
├─ Trades: {counts.get('trades', 0)}
├─ Pyramids: {counts.get('pyramids', 0)}
└─ Exits: {counts.get('exits', 0)}

Sequences and processed alerts also reset."""

        elif reset_type == "settings":
            counts = await db.reset_settings()
            message = f"""✅ Settings Cleared

Deleted: {counts.get('settings', 0)} setting(s)

Capital configurations have been reset."""

        elif reset_type == "cache":
            counts = await db.reset_cache()
            message = f"""✅ Cache Cleared

Deleted:
├─ Symbol rules: {counts.get('symbol_rules', 0)}
└─ Daily reports: {counts.get('daily_reports', 0)}"""

        elif reset_type == "all":
            counts = await db.reset_all()
            message = f"""✅ Full Database Reset

Deleted:
├─ Trades: {counts.get('trades', 0)}
├─ Pyramids: {counts.get('pyramids', 0)}
├─ Exits: {counts.get('exits', 0)}
├─ Settings: {counts.get('settings', 0)}
├─ Symbol rules: {counts.get('symbol_rules', 0)}
└─ Daily reports: {counts.get('daily_reports', 0)}

Database is now clean."""

        else:
            await update.message.reply_text(
                f"❌ Unknown reset type: {reset_type}\n"
                "Valid options: trades, settings, cache, all"
            )
            return

        await update.message.reply_text(message)
        logger.info(f"Database reset ({reset_type}) executed")

    except Exception as e:
        logger.error(f"Error in /reset: {e}")
        await update.message.reply_text(f"❌ Error: {e}")


@channel_only
async def cmd_cleanup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Clean up orphan trades (trades with 0 pyramids).

    These orphan trades occur when validation fails after trade creation.

    Usage:
        /cleanup - Show how many orphan trades exist
        /cleanup CONFIRM - Delete orphan trades
    """
    try:
        args = context.args if context.args else []

        # Count orphan trades
        cursor = await db.connection.execute(
            """
            SELECT COUNT(*) FROM trades t
            LEFT JOIN pyramids p ON t.id = p.trade_id
            WHERE t.status = 'open'
            GROUP BY t.id
            HAVING COUNT(p.id) = 0
            """
        )
        rows = await cursor.fetchall()
        orphan_count = len(rows)

        if not args:
            if orphan_count == 0:
                await update.message.reply_text(
                    "✅ No orphan trades found.\n\n"
                    "All open trades have pyramids."
                )
            else:
                await update.message.reply_text(
                    f"🧹 Found {orphan_count} orphan trades\n\n"
                    "These are trades with 0 pyramids (validation failed).\n\n"
                    "To delete them, run:\n"
                    "`/cleanup CONFIRM`"
                )
            return

        if args[0].upper() != "CONFIRM":
            await update.message.reply_text(
                "❌ Please add CONFIRM to execute cleanup:\n"
                "`/cleanup CONFIRM`"
            )
            return

        # Execute cleanup
        deleted = await db.cleanup_orphan_trades()
        await update.message.reply_text(
            f"✅ Cleaned up {deleted} orphan trades\n\n"
            "These trades had no pyramids due to validation failures."
        )
        logger.info(f"Cleaned up {deleted} orphan trades")

    except Exception as e:
        logger.error(f"Error in /cleanup: {e}")
        await update.message.reply_text(f"❌ Error: {e}")


@channel_only
async def cmd_cleanup_pyramids(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List and optionally close trades exceeding pyramid limit.

    Usage:
        /cleanup_pyramids - List trades with more than max_pyramids
        /cleanup_pyramids <group_id> CONFIRM - Close the specified trade
    """
    try:
        args = context.args if context.args else []
        max_pyramids = settings.max_pyramids

        # Find trades exceeding the limit
        cursor = await db.connection.execute(
            """
            SELECT t.id, t.group_id, t.exchange, t.base, t.quote, t.status,
                   COUNT(p.id) as pyramid_count
            FROM trades t
            JOIN pyramids p ON t.id = p.trade_id
            WHERE t.status = 'open'
            GROUP BY t.id
            HAVING COUNT(p.id) > ?
            ORDER BY COUNT(p.id) DESC
            """,
            (max_pyramids,),
        )
        rows = await cursor.fetchall()

        if not args:
            # List over-limit trades
            if not rows:
                await update.message.reply_text(
                    f"✅ No trades exceed the {max_pyramids} pyramid limit.\n\n"
                    "All open trades are within limits."
                )
                return

            lines = [f"⚠️ Trades exceeding {max_pyramids} pyramid limit:\n"]
            for row in rows:
                lines.append(
                    f"📈 {row['group_id']}\n"
                    f"   {row['base']}/{row['quote']} on {row['exchange']}\n"
                    f"   Pyramids: {row['pyramid_count']} (limit: {max_pyramids})\n"
                )

            lines.append(f"\nTo force-close a trade:\n`/cleanup_pyramids <group_id> CONFIRM`")
            await update.message.reply_text("\n".join(lines))
            return

        # Handle confirmation to close a specific trade
        if len(args) >= 2 and args[-1].upper() == "CONFIRM":
            group_id = args[0]

            # Find the trade
            cursor = await db.connection.execute(
                "SELECT id, group_id FROM trades WHERE group_id = ? AND status = 'open'",
                (group_id,),
            )
            trade = await cursor.fetchone()

            if not trade:
                await update.message.reply_text(
                    f"❌ Trade not found: {group_id}\n\n"
                    "Use `/cleanup_pyramids` to see trades exceeding the limit."
                )
                return

            # Close the trade manually (mark as closed without exit price)
            await db.connection.execute(
                "UPDATE trades SET status = 'closed' WHERE id = ?",
                (trade["id"],),
            )
            await db.connection.commit()

            await update.message.reply_text(
                f"✅ Closed trade: {group_id}\n\n"
                "Note: This was a manual close. No exit was recorded."
            )
            logger.info(f"Manually closed over-limit trade: {group_id}")
            return

        # Invalid args
        await update.message.reply_text(
            f"Usage:\n"
            f"/cleanup_pyramids - List over-limit trades\n"
            f"/cleanup_pyramids <group_id> CONFIRM - Close specific trade"
        )

    except Exception as e:
        logger.error(f"Error in /cleanup_pyramids: {e}")
        await update.message.reply_text(f"❌ Error: {e}")


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
    app.add_handler(CommandHandler("signals_channel", cmd_signals_channel))
    app.add_handler(CommandHandler("set_capital", cmd_set_capital))

    # Control
    app.add_handler(CommandHandler("pause", cmd_pause))
    app.add_handler(CommandHandler("resume", cmd_resume))
    app.add_handler(CommandHandler("ignore", cmd_ignore))
    app.add_handler(CommandHandler("unignore", cmd_unignore))

    # Export & Data Management
    app.add_handler(CommandHandler("export", cmd_export))
    app.add_handler(CommandHandler("reset", cmd_reset))
    app.add_handler(CommandHandler("cleanup", cmd_cleanup))
    app.add_handler(CommandHandler("cleanup_pyramids", cmd_cleanup_pyramids))
    app.add_handler(CommandHandler("help", cmd_help))

    logger.info("Registered 26 bot command handlers")
