"""
Tests for report service in app/services/report_service.py

Ensures that report generation uses the same functions as other commands.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
import pytz


class TestReportServiceScheduler:
    """Tests for ReportService scheduler functionality."""

    def test_scheduler_property(self):
        """Test that scheduler property creates instance on demand."""
        from app.services.report_service import ReportService

        service = ReportService()
        assert service._scheduler is None

        scheduler = service.scheduler
        assert scheduler is not None
        assert service._scheduler is scheduler

    @patch("app.services.report_service.settings")
    def test_start_scheduler(self, mock_settings):
        """Test starting the scheduler."""
        from app.services.report_service import ReportService

        mock_settings.daily_report_time = "12:00"
        mock_settings.timezone = "UTC"

        service = ReportService()

        with patch.object(service.scheduler, "add_job") as mock_add_job:
            with patch.object(service.scheduler, "start") as mock_start:
                service.start_scheduler()

                mock_add_job.assert_called_once()
                mock_start.assert_called_once()

    @patch("app.services.report_service.settings")
    def test_start_scheduler_invalid_time(self, mock_settings):
        """Test starting scheduler with invalid time falls back to default."""
        from app.services.report_service import ReportService

        mock_settings.daily_report_time = "invalid"
        mock_settings.timezone = "UTC"

        service = ReportService()

        with patch.object(service.scheduler, "add_job") as mock_add_job:
            with patch.object(service.scheduler, "start") as mock_start:
                service.start_scheduler()

                # Should still work with default time
                mock_add_job.assert_called_once()

    def test_stop_scheduler(self):
        """Test stopping the scheduler."""
        from app.services.report_service import ReportService

        service = ReportService()
        service._scheduler = MagicMock()
        service._scheduler.running = True

        service.stop_scheduler()

        service._scheduler.shutdown.assert_called_once()

    def test_stop_scheduler_not_running(self):
        """Test stopping scheduler when not running."""
        from app.services.report_service import ReportService

        service = ReportService()
        # No scheduler initialized
        service.stop_scheduler()  # Should not raise


class TestGenerateDailyReport:
    """Tests for generate_daily_report method."""

    @pytest.mark.asyncio
    async def test_generate_report_no_trades(self, test_db):
        """Test generating report when no trades exist."""
        from app.services.report_service import ReportService

        service = ReportService()

        with patch("app.services.report_service.db", test_db):
            with patch("app.services.report_service.settings") as mock_settings:
                mock_settings.timezone = "UTC"
                mock_settings.equity_curve_enabled = False

                report = await service.generate_daily_report("2030-01-01")

                assert report.total_trades == 0
                assert report.total_pnl_usdt == 0.0
                assert report.trades == []

    @pytest.mark.asyncio
    async def test_generate_report_with_trades(self, populated_db):
        """Test generating report with existing trades."""
        from app.services.report_service import ReportService

        service = ReportService()
        today = datetime.now().strftime("%Y-%m-%d")

        with patch("app.services.report_service.db", populated_db):
            with patch("app.services.report_service.settings") as mock_settings:
                mock_settings.timezone = "UTC"
                mock_settings.equity_curve_enabled = True

                report = await service.generate_daily_report(today)

                # Should have 3 trades from today
                assert report.total_trades == 3
                assert len(report.trades) == 3
                # Total PnL: 100.50 - 30.25 + 50 = 120.25
                assert abs(report.total_pnl_usdt - 120.25) < 0.01

    @pytest.mark.asyncio
    async def test_report_uses_shared_statistics_function(self, populated_db):
        """Test that report uses get_statistics_for_period."""
        from app.services.report_service import ReportService

        service = ReportService()
        today = datetime.now().strftime("%Y-%m-%d")

        with patch("app.services.report_service.db", populated_db) as mock_db:
            with patch("app.services.report_service.settings") as mock_settings:
                mock_settings.timezone = "UTC"
                mock_settings.equity_curve_enabled = True

                # Spy on the function call
                original_get_stats = populated_db.get_statistics_for_period

                with patch.object(
                    populated_db,
                    "get_statistics_for_period",
                    wraps=original_get_stats
                ) as spy:
                    await service.generate_daily_report(today)

                    # Verify the shared function was called
                    spy.assert_called_once_with(today, today)

    @pytest.mark.asyncio
    async def test_report_uses_shared_pnl_function(self, populated_db):
        """Test that report uses get_realized_pnl_for_period."""
        from app.services.report_service import ReportService

        service = ReportService()
        today = datetime.now().strftime("%Y-%m-%d")

        with patch("app.services.report_service.db", populated_db):
            with patch("app.services.report_service.settings") as mock_settings:
                mock_settings.timezone = "UTC"
                mock_settings.equity_curve_enabled = True

                original_get_pnl = populated_db.get_realized_pnl_for_period

                with patch.object(
                    populated_db,
                    "get_realized_pnl_for_period",
                    wraps=original_get_pnl
                ) as spy:
                    await service.generate_daily_report(today)

                    spy.assert_called_once_with(today, today)

    @pytest.mark.asyncio
    async def test_report_uses_shared_drawdown_function(self, populated_db):
        """Test that report uses get_drawdown_for_period."""
        from app.services.report_service import ReportService

        service = ReportService()
        today = datetime.now().strftime("%Y-%m-%d")

        with patch("app.services.report_service.db", populated_db):
            with patch("app.services.report_service.settings") as mock_settings:
                mock_settings.timezone = "UTC"
                mock_settings.equity_curve_enabled = True

                original_get_dd = populated_db.get_drawdown_for_period

                with patch.object(
                    populated_db,
                    "get_drawdown_for_period",
                    wraps=original_get_dd
                ) as spy:
                    await service.generate_daily_report(today)

                    spy.assert_called_once_with(today, today)

    @pytest.mark.asyncio
    async def test_report_uses_shared_exchange_function(self, populated_db):
        """Test that report uses get_exchange_stats_for_period."""
        from app.services.report_service import ReportService

        service = ReportService()
        today = datetime.now().strftime("%Y-%m-%d")

        with patch("app.services.report_service.db", populated_db):
            with patch("app.services.report_service.settings") as mock_settings:
                mock_settings.timezone = "UTC"
                mock_settings.equity_curve_enabled = True

                original_get_exchange = populated_db.get_exchange_stats_for_period

                with patch.object(
                    populated_db,
                    "get_exchange_stats_for_period",
                    wraps=original_get_exchange
                ) as spy:
                    await service.generate_daily_report(today)

                    spy.assert_called_once_with(today, today)

    @pytest.mark.asyncio
    async def test_report_uses_shared_trades_function(self, populated_db):
        """Test that report uses get_trades_for_period."""
        from app.services.report_service import ReportService

        service = ReportService()
        today = datetime.now().strftime("%Y-%m-%d")

        with patch("app.services.report_service.db", populated_db):
            with patch("app.services.report_service.settings") as mock_settings:
                mock_settings.timezone = "UTC"
                mock_settings.equity_curve_enabled = True

                original_get_trades = populated_db.get_trades_for_period

                with patch.object(
                    populated_db,
                    "get_trades_for_period",
                    wraps=original_get_trades
                ) as spy:
                    await service.generate_daily_report(today)

                    spy.assert_called_once_with(today, today, limit=1000)

    @pytest.mark.asyncio
    async def test_report_by_exchange_breakdown(self, populated_db):
        """Test that exchange breakdown is correctly populated."""
        from app.services.report_service import ReportService

        service = ReportService()
        today = datetime.now().strftime("%Y-%m-%d")

        with patch("app.services.report_service.db", populated_db):
            with patch("app.services.report_service.settings") as mock_settings:
                mock_settings.timezone = "UTC"
                mock_settings.equity_curve_enabled = False

                report = await service.generate_daily_report(today)

                assert "binance" in report.by_exchange
                assert "bybit" in report.by_exchange

                # Binance: 100.50 - 30.25 = 70.25
                assert abs(report.by_exchange["binance"]["pnl"] - 70.25) < 0.01
                assert report.by_exchange["binance"]["trades"] == 2

                # Bybit: 50.00
                assert abs(report.by_exchange["bybit"]["pnl"] - 50.0) < 0.01
                assert report.by_exchange["bybit"]["trades"] == 1

    @pytest.mark.asyncio
    async def test_report_chart_stats_included(self, populated_db):
        """Test that chart stats are included when equity curve enabled."""
        from app.services.report_service import ReportService

        service = ReportService()
        today = datetime.now().strftime("%Y-%m-%d")

        with patch("app.services.report_service.db", populated_db):
            with patch("app.services.report_service.settings") as mock_settings:
                mock_settings.timezone = "UTC"
                mock_settings.equity_curve_enabled = True

                report = await service.generate_daily_report(today)

                assert report.chart_stats is not None
                assert report.chart_stats.total_net_pnl > 0
                assert report.chart_stats.win_rate > 0

    @pytest.mark.asyncio
    async def test_report_defaults_to_yesterday(self, populated_db):
        """Test that report defaults to yesterday when no date provided."""
        from app.services.report_service import ReportService

        service = ReportService()

        with patch("app.services.report_service.db", populated_db):
            with patch("app.services.report_service.settings") as mock_settings:
                mock_settings.timezone = "UTC"
                mock_settings.equity_curve_enabled = False

                report = await service.generate_daily_report(None)

                # Use timezone-aware calculation to match the service logic
                tz = pytz.timezone("UTC")
                yesterday = (datetime.now(tz) - timedelta(days=1)).strftime("%Y-%m-%d")
                assert report.date == yesterday


class TestGenerateAndSendDailyReport:
    """Tests for generate_and_send_daily_report method."""

    @pytest.mark.asyncio
    async def test_send_report_with_trades(self, populated_db):
        """Test sending report when there are trades."""
        from app.services.report_service import ReportService

        service = ReportService()
        today = datetime.now().strftime("%Y-%m-%d")

        with patch("app.services.report_service.db", populated_db):
            with patch("app.services.report_service.settings") as mock_settings:
                mock_settings.timezone = "UTC"
                mock_settings.equity_curve_enabled = False

                with patch("app.services.report_service.telegram_service") as mock_telegram:
                    mock_telegram.send_daily_report = AsyncMock(return_value=True)

                    result = await service.generate_and_send_daily_report(today)

                    assert result is True
                    mock_telegram.send_daily_report.assert_called_once()

    @pytest.mark.asyncio
    async def test_skip_send_when_no_trades(self, test_db):
        """Test that report is not sent when no trades."""
        from app.services.report_service import ReportService

        service = ReportService()

        with patch("app.services.report_service.db", test_db):
            with patch("app.services.report_service.settings") as mock_settings:
                mock_settings.timezone = "UTC"
                mock_settings.equity_curve_enabled = False

                with patch("app.services.report_service.telegram_service") as mock_telegram:
                    result = await service.generate_and_send_daily_report("2030-01-01")

                    assert result is True
                    mock_telegram.send_daily_report.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_exception(self, populated_db):
        """Test handling of exceptions during report generation."""
        from app.services.report_service import ReportService

        service = ReportService()

        with patch("app.services.report_service.db") as mock_db:
            mock_db.get_statistics_for_period = AsyncMock(
                side_effect=Exception("Database error")
            )

            with patch("app.services.report_service.settings") as mock_settings:
                mock_settings.timezone = "UTC"

                result = await service.generate_and_send_daily_report("2026-01-20")

                assert result is False


class TestReportDataConsistency:
    """Tests to verify report data matches other command outputs."""

    @pytest.mark.asyncio
    async def test_report_stats_match_stats_command(self, populated_db):
        """Test that report statistics match /stats command output."""
        from app.services.report_service import ReportService

        service = ReportService()
        today = datetime.now().strftime("%Y-%m-%d")

        with patch("app.services.report_service.db", populated_db):
            with patch("app.services.report_service.settings") as mock_settings:
                mock_settings.timezone = "UTC"
                mock_settings.equity_curve_enabled = True

                # Generate report
                report = await service.generate_daily_report(today)

                # Get stats directly (what /stats command uses)
                stats = await populated_db.get_statistics_for_period(today, today)

                # Verify they match
                assert report.chart_stats.win_rate == stats["win_rate"]
                assert report.chart_stats.profit_factor == stats["profit_factor"]

    @pytest.mark.asyncio
    async def test_report_pnl_matches_pnl_command(self, populated_db):
        """Test that report PnL matches /pnl command output."""
        from app.services.report_service import ReportService

        service = ReportService()
        today = datetime.now().strftime("%Y-%m-%d")

        with patch("app.services.report_service.db", populated_db):
            with patch("app.services.report_service.settings") as mock_settings:
                mock_settings.timezone = "UTC"
                mock_settings.equity_curve_enabled = False

                # Generate report
                report = await service.generate_daily_report(today)

                # Get PnL directly (what /pnl command uses)
                pnl, count = await populated_db.get_realized_pnl_for_period(today, today)

                # Verify they match
                assert abs(report.total_pnl_usdt - pnl) < 0.01
                assert report.total_trades == count

    @pytest.mark.asyncio
    async def test_report_drawdown_matches_drawdown_command(self, populated_db):
        """Test that report drawdown matches /drawdown command output."""
        from app.services.report_service import ReportService

        service = ReportService()
        today = datetime.now().strftime("%Y-%m-%d")

        with patch("app.services.report_service.db", populated_db):
            with patch("app.services.report_service.settings") as mock_settings:
                mock_settings.timezone = "UTC"
                mock_settings.equity_curve_enabled = True

                # Generate report
                report = await service.generate_daily_report(today)

                # Get drawdown directly (what /drawdown command uses)
                dd_data = await populated_db.get_drawdown_for_period(today, today)

                # Verify they match
                assert (
                    abs(report.chart_stats.max_drawdown_usdt - dd_data["max_drawdown"])
                    < 0.01
                )
                assert (
                    abs(report.chart_stats.max_drawdown_percent - dd_data["max_drawdown_percent"])
                    < 0.01
                )
