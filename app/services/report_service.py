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
        total_capital = 0.0
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
            (total_pnl_usdt / total_capital) * 100 if total_capital > 0 else 0
        )

        # Sort trade history by PnL (best first)
        trade_history.sort(key=lambda x: x.pnl_usdt, reverse=True)

        # Build equity curve data points
        equity_points: list[EquityPoint] = []
        if settings.equity_curve_enabled:
            equity_data = await db.get_equity_curve_data(date)
            cumulative_pnl = 0.0
            for row in equity_data:
                cumulative_pnl += row.get("total_pnl_usdt", 0) or 0
                closed_at = row.get("closed_at")
                if closed_at:
                    try:
                        if isinstance(closed_at, str):
                            timestamp = datetime.fromisoformat(closed_at)
                        else:
                            timestamp = closed_at
                        equity_points.append(EquityPoint(
                            timestamp=timestamp,
                            cumulative_pnl=cumulative_pnl
                        ))
                    except (ValueError, TypeError):
                        pass

        # Calculate chart statistics for footer
        chart_stats = None
        if settings.equity_curve_enabled and trade_history:
            # Count wins and losses
            wins = [t for t in trade_history if t.pnl_usdt > 0]
            losses = [t for t in trade_history if t.pnl_usdt < 0]
            num_wins = len(wins)
            num_losses = len(losses)

            # Win rate
            win_rate = (num_wins / total_trades_count * 100) if total_trades_count > 0 else 0

            # Profit factor (total wins / total losses)
            total_wins = sum(t.pnl_usdt for t in wins) if wins else 0
            total_losses = abs(sum(t.pnl_usdt for t in losses)) if losses else 0
            profit_factor = (total_wins / total_losses) if total_losses > 0 else total_wins

            # Win/Loss ratio (avg win / avg loss)
            avg_win = (total_wins / num_wins) if num_wins > 0 else 0
            avg_loss = (total_losses / num_losses) if num_losses > 0 else 0
            win_loss_ratio = (avg_win / avg_loss) if avg_loss > 0 else avg_win

            # Max drawdown from equity curve
            # Drawdown = drop from peak to trough
            # Drawdown % = relative to total capital deployed (not peak PnL)
            max_drawdown_usdt = 0.0
            peak = 0.0
            for point in equity_points:
                if point.cumulative_pnl > peak:
                    peak = point.cumulative_pnl
                drawdown = peak - point.cumulative_pnl
                if drawdown > max_drawdown_usdt:
                    max_drawdown_usdt = drawdown

            # Calculate drawdown % relative to total capital deployed
            max_drawdown_percent = (max_drawdown_usdt / total_capital * 100) if total_capital > 0 else 0

            chart_stats = ChartStats(
                total_net_pnl=total_pnl_usdt,
                max_drawdown_percent=max_drawdown_percent,
                max_drawdown_usdt=max_drawdown_usdt,
                num_trades=total_trades_count,
                win_rate=win_rate,
                total_used_equity=total_capital,
                profit_factor=profit_factor,
                win_loss_ratio=win_loss_ratio,
            )

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
