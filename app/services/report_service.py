"""
Report Service

Handles generation and scheduling of daily performance reports.
"""

import json
import logging
from collections import defaultdict
from datetime import datetime, timedelta

import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from ..config import settings
from ..database import db
from ..models import DailyReportData, TradeHistoryItem, EquityPoint, ChartStats
from .telegram_service import telegram_service

logger = logging.getLogger(__name__)


class ReportService:
    """Service for generating and scheduling reports."""

    def __init__(self):
        self._scheduler: AsyncIOScheduler | None = None

    @property
    def scheduler(self) -> AsyncIOScheduler:
        """Get or create scheduler instance."""
        if not self._scheduler:
            self._scheduler = AsyncIOScheduler()
        return self._scheduler

    def start_scheduler(self) -> None:
        """Start the report scheduler."""
        if self._scheduler and self._scheduler.running:
            return

        # Parse report time
        try:
            hour, minute = map(int, settings.daily_report_time.split(":"))
        except ValueError:
            hour, minute = 12, 0
            logger.warning(
                f"Invalid daily_report_time '{settings.daily_report_time}', using 12:00"
            )

        # Create cron trigger with configured timezone
        tz = pytz.timezone(settings.timezone)
        trigger = CronTrigger(hour=hour, minute=minute, timezone=tz)

        # Schedule daily report
        self.scheduler.add_job(
            self.generate_and_send_daily_report,
            trigger=trigger,
            id="daily_report",
            replace_existing=True,
        )

        self.scheduler.start()
        logger.info(
            f"Report scheduler started. Daily report at {hour:02d}:{minute:02d} {settings.timezone}"
        )

    def stop_scheduler(self) -> None:
        """Stop the report scheduler."""
        if self._scheduler and self._scheduler.running:
            self._scheduler.shutdown()
            logger.info("Report scheduler stopped")

    async def generate_daily_report(self, date: str | None = None) -> DailyReportData:
        """
        Generate daily report for a specific date.

        Uses the same period-based database functions as other commands
        (/pnl, /stats, /best, etc.) to ensure consistent results.

        Args:
            date: Date string (YYYY-MM-DD). Defaults to yesterday.

        Returns:
            DailyReportData with report statistics
        """
        if date is None:
            # Get yesterday's date in configured timezone
            tz = pytz.timezone(settings.timezone)
            yesterday = datetime.now(tz) - timedelta(days=1)
            date = yesterday.strftime("%Y-%m-%d")

        logger.info(f"Generating daily report for {date}")

        # ====== USE SHARED PERIOD-BASED FUNCTIONS FOR CONSISTENCY ======

        # Get statistics using the SAME function as /stats command
        stats = await db.get_statistics_for_period(date, date)

        if stats["total_trades"] == 0:
            logger.info(f"No trades found for {date}")
            return DailyReportData(
                date=date,
                total_trades=0,
                total_pyramids=0,
                total_pnl_usdt=0.0,
                total_pnl_percent=0.0,
                trades=[],
                by_exchange={},
                by_timeframe={},
                by_pair={},
            )

        # Get PnL using the SAME function as /pnl command
        total_pnl_usdt, total_trades_count = await db.get_realized_pnl_for_period(date, date)

        # Get drawdown using the SAME function as /drawdown command
        drawdown_data = await db.get_drawdown_for_period(date, date)

        # Get exchange breakdown using the SAME function as /exchange command
        exchange_stats = await db.get_exchange_stats_for_period(date, date)
        by_exchange = {
            row["exchange"]: {"pnl": row["pnl"], "trades": row["trades"]}
            for row in exchange_stats
        }

        # Get trades using the SAME function as /trades command
        trades = await db.get_trades_for_period(date, date, limit=1000)

        # Build trade history and calculate pyramids/capital (report-specific)
        total_capital = 0.0
        total_pyramids = 0
        trade_history: list[TradeHistoryItem] = []
        by_timeframe: dict = defaultdict(lambda: {"pnl": 0.0, "trades": 0})
        by_pair: dict = defaultdict(float)

        for trade in trades:
            trade_id = trade["id"]
            exchange = trade["exchange"]
            base = trade["base"]
            quote = trade["quote"]
            pair = f"{base}/{quote}"
            timeframe = trade.get("timeframe") or "N/A"
            group_id = trade.get("group_id") or trade_id[:8]

            pnl = trade.get("total_pnl_usdt", 0) or 0
            pnl_percent = trade.get("total_pnl_percent", 0) or 0

            # Get pyramids for this trade (report-specific detail)
            pyramids = await db.get_pyramids_for_trade(trade_id)
            pyramids_count = len(pyramids)
            total_pyramids += pyramids_count

            for pyramid in pyramids:
                total_capital += pyramid.get("capital_usdt", 0) or 0

            # Add to trade history
            trade_history.append(TradeHistoryItem(
                group_id=group_id,
                exchange=exchange,
                pair=pair,
                timeframe=timeframe,
                pyramids_count=pyramids_count,
                pnl_usdt=pnl,
                pnl_percent=pnl_percent,
            ))

            # Aggregate by timeframe (report-specific)
            by_timeframe[timeframe]["pnl"] += pnl
            by_timeframe[timeframe]["trades"] += 1

            # Aggregate by pair (report-specific)
            by_pair[pair] += pnl

        # Calculate overall percentage
        total_pnl_percent = (
            (total_pnl_usdt / total_capital) * 100 if total_capital > 0 else 0
        )

        # Sort trade history by PnL (best first)
        trade_history.sort(key=lambda x: x.pnl_usdt, reverse=True)

        # Build equity curve data points (chart-specific)
        equity_points: list[EquityPoint] = []
        all_time_cumulative_pnl = 0.0
        if settings.equity_curve_enabled:
            # Get cumulative realized PnL from all trades BEFORE this date (for context)
            all_time_cumulative_pnl = await db.get_cumulative_pnl_before_date(date)

            equity_data = await db.get_equity_curve_data(date)
            today_running_pnl = 0.0  # Start from $0 for today
            for row in equity_data:
                today_running_pnl += row.get("total_pnl_usdt", 0) or 0
                closed_at = row.get("closed_at")
                if closed_at:
                    try:
                        if isinstance(closed_at, str):
                            timestamp = datetime.fromisoformat(closed_at)
                        else:
                            timestamp = closed_at
                        equity_points.append(EquityPoint(
                            timestamp=timestamp,
                            cumulative_pnl=today_running_pnl  # Today's running total only
                        ))
                    except (ValueError, TypeError):
                        pass

        # Calculate chart statistics using values from shared functions
        chart_stats = None
        if settings.equity_curve_enabled and trade_history:
            # Use stats from get_statistics_for_period() - SAME as /stats command
            win_rate = stats["win_rate"]
            profit_factor = stats["profit_factor"]

            # Win/Loss ratio from shared stats
            avg_win = stats["avg_win"]
            avg_loss = abs(stats["avg_loss"]) if stats["avg_loss"] else 0
            win_loss_ratio = (avg_win / avg_loss) if avg_loss > 0 else avg_win

            # Use drawdown from get_drawdown_for_period() - SAME as /drawdown command
            max_drawdown_usdt = drawdown_data["max_drawdown"]
            max_drawdown_percent = drawdown_data["max_drawdown_percent"]

            # All-time cumulative PnL (for context at bottom of chart)
            final_all_time_pnl = all_time_cumulative_pnl + total_pnl_usdt

            # Get trade counts breakdown (report-specific)
            trade_counts = await db.get_trade_counts_for_date(date)

            chart_stats = ChartStats(
                total_net_pnl=total_pnl_usdt,  # TODAY's PnL only
                max_drawdown_percent=max_drawdown_percent,
                max_drawdown_usdt=max_drawdown_usdt,
                trades_opened_today=trade_counts["opened_today"],
                trades_closed_today=trade_counts["closed_today"],
                trades_still_open=trade_counts["still_open"],
                win_rate=win_rate,
                total_used_equity=total_capital,
                profit_factor=profit_factor,
                win_loss_ratio=win_loss_ratio,
                cumulative_pnl=final_all_time_pnl,  # All-time for context
            )

        report_data = DailyReportData(
            date=date,
            total_trades=total_trades_count,
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

        # Save report to database (exclude equity_points for JSON serialization)
        # Use mode='json' to properly serialize datetime objects
        await db.save_daily_report(
            date=date,
            total_trades=total_trades_count,
            total_pyramids=total_pyramids,
            total_pnl_usdt=total_pnl_usdt,
            report_json=json.dumps(report_data.model_dump(mode='json')),
        )

        logger.info(
            f"Daily report generated: {total_trades_count} trades, "
            f"{total_pyramids} pyramids, ${total_pnl_usdt:.2f} PnL"
        )

        return report_data

    async def generate_and_send_daily_report(self, date: str | None = None) -> bool:
        """
        Generate daily report and send to Telegram.

        Args:
            date: Date string (YYYY-MM-DD). Defaults to yesterday.

        Returns:
            True if report was sent successfully
        """
        try:
            report_data = await self.generate_daily_report(date)

            # Only send if there were trades
            if report_data.total_trades > 0:
                success = await telegram_service.send_daily_report(report_data)
                return success
            else:
                logger.info(f"No trades for {report_data.date}, skipping Telegram notification")
                return True

        except Exception as e:
            logger.error(f"Failed to generate/send daily report: {e}")
            return False


# Singleton instance
report_service = ReportService()
