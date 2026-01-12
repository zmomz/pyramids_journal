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
from ..models import DailyReportData, TradeHistoryItem
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

        # Get all closed trades for the date
        trades = await db.get_trades_for_date(date)

        if not trades:
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

        # Aggregate statistics
        total_trades_count = len(trades)
        total_pnl_usdt = 0.0
        total_notional = 0.0
        total_pyramids = 0

        trade_history: list[TradeHistoryItem] = []
        by_exchange: dict = defaultdict(lambda: {"pnl": 0.0, "trades": 0})
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
            total_pnl_usdt += pnl

            # Get pyramids for this trade
            pyramids = await db.get_pyramids_for_trade(trade_id)
            pyramids_count = len(pyramids)
            total_pyramids += pyramids_count

            for pyramid in pyramids:
                total_notional += pyramid.get("notional_usdt", 0) or 0

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

            # Aggregate by exchange
            by_exchange[exchange]["pnl"] += pnl
            by_exchange[exchange]["trades"] += 1

            # Aggregate by timeframe
            by_timeframe[timeframe]["pnl"] += pnl
            by_timeframe[timeframe]["trades"] += 1

            # Aggregate by pair
            by_pair[pair] += pnl

        # Calculate overall percentage
        total_pnl_percent = (
            (total_pnl_usdt / total_notional) * 100 if total_notional > 0 else 0
        )

        # Sort trade history by PnL (best first)
        trade_history.sort(key=lambda x: x.pnl_usdt, reverse=True)

        report_data = DailyReportData(
            date=date,
            total_trades=total_trades_count,
            total_pyramids=total_pyramids,
            total_pnl_usdt=total_pnl_usdt,
            total_pnl_percent=total_pnl_percent,
            trades=trade_history,
            by_exchange=dict(by_exchange),
            by_timeframe=dict(by_timeframe),
            by_pair=dict(by_pair),
        )

        # Save report to database
        await db.save_daily_report(
            date=date,
            total_trades=total_trades_count,
            total_pyramids=total_pyramids,
            total_pnl_usdt=total_pnl_usdt,
            report_json=json.dumps(report_data.model_dump()),
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
