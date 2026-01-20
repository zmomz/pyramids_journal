"""
Tests for FastAPI application in app/main.py

Tests the webhook endpoint and API routes.
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestVerifyWebhookSecret:
    """Tests for webhook secret verification."""

    def test_no_secret_configured_allows_all(self):
        """Test that no secret configured allows all requests."""
        from app.main import verify_webhook_secret

        with patch("app.main.settings") as mock_settings:
            mock_settings.webhook_secret = ""
            assert verify_webhook_secret(None) is True
            assert verify_webhook_secret("any_secret") is True

    def test_secret_configured_validates(self):
        """Test that configured secret validates correctly."""
        from app.main import verify_webhook_secret

        with patch("app.main.settings") as mock_settings:
            mock_settings.webhook_secret = "test_secret"
            assert verify_webhook_secret("test_secret") is True
            assert verify_webhook_secret("wrong_secret") is False
            assert verify_webhook_secret(None) is False


class TestHealthEndpoint:
    """Tests for /health endpoint."""

    def test_health_returns_ok(self):
        """Test health check returns healthy status."""
        from fastapi.testclient import TestClient

        # Mock all external dependencies
        with patch("app.main.db") as mock_db, \
             patch("app.main.telegram_bot") as mock_bot, \
             patch("app.main.report_service") as mock_report:

            mock_db.connect = AsyncMock()
            mock_db.disconnect = AsyncMock()
            mock_bot.initialize = AsyncMock()
            mock_bot.start = AsyncMock()
            mock_bot.stop = AsyncMock()
            mock_report.start_scheduler = MagicMock()
            mock_report.stop_scheduler = MagicMock()

            from app.main import app
            client = TestClient(app, raise_server_exceptions=False)

            response = client.get("/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            assert data["service"] == "pyramids-journal"


class TestWebhookPayloadValidation:
    """Tests for webhook payload validation."""

    def test_valid_payload_structure(self):
        """Test that valid payload passes validation."""
        from app.models import TradingViewAlert

        # This should not raise
        alert = TradingViewAlert(
            timestamp="2026-01-20T10:00:00Z",
            exchange="binance",
            symbol="BTCUSDT",
            timeframe="1h",
            action="buy",
            order_id="test_123",
            contracts=0.01,
            close=50000.0,
            position_side="long",
            position_qty=0.01
        )

        assert alert.action == "buy"
        assert alert.position_side == "long"

    def test_is_entry_signal(self):
        """Test is_entry detection."""
        from app.models import TradingViewAlert

        # Buy + long = entry
        alert = TradingViewAlert(
            timestamp="2026-01-20T10:00:00Z",
            exchange="binance",
            symbol="BTCUSDT",
            timeframe="1h",
            action="buy",
            order_id="test_123",
            contracts=0.01,
            close=50000.0,
            position_side="long",
            position_qty=0.01
        )
        assert alert.is_entry() is True
        assert alert.is_exit() is False

    def test_is_exit_signal(self):
        """Test is_exit detection."""
        from app.models import TradingViewAlert

        # Sell + flat = exit
        alert = TradingViewAlert(
            timestamp="2026-01-20T10:00:00Z",
            exchange="binance",
            symbol="BTCUSDT",
            timeframe="1h",
            action="sell",
            order_id="test_123",
            contracts=0.0,
            close=52000.0,
            position_side="flat",
            position_qty=0.0
        )
        assert alert.is_exit() is True
        assert alert.is_entry() is False


class TestTradesEndpoint:
    """Tests for /trades endpoint."""

    def test_list_trades(self):
        """Test listing recent trades."""
        from fastapi.testclient import TestClient

        with patch("app.main.db") as mock_db, \
             patch("app.main.telegram_bot") as mock_bot, \
             patch("app.main.report_service") as mock_report:

            mock_db.connect = AsyncMock()
            mock_db.disconnect = AsyncMock()
            mock_db.get_recent_trades = AsyncMock(return_value=[
                {"id": "trade_1", "exchange": "binance", "base": "BTC", "quote": "USDT"}
            ])
            mock_bot.initialize = AsyncMock()
            mock_bot.start = AsyncMock()
            mock_bot.stop = AsyncMock()
            mock_report.start_scheduler = MagicMock()
            mock_report.stop_scheduler = MagicMock()

            from app.main import app
            client = TestClient(app, raise_server_exceptions=False)

            response = client.get("/trades")
            assert response.status_code == 200
            data = response.json()
            assert data["count"] == 1
            assert len(data["trades"]) == 1


class TestGetTradeEndpoint:
    """Tests for /trades/{trade_id} endpoint."""

    def test_get_trade_found(self):
        """Test getting a trade that exists."""
        from fastapi.testclient import TestClient

        with patch("app.main.db") as mock_db, \
             patch("app.main.telegram_bot") as mock_bot, \
             patch("app.main.report_service") as mock_report:

            mock_db.connect = AsyncMock()
            mock_db.disconnect = AsyncMock()
            mock_db.get_trade_with_pyramids = AsyncMock(return_value={
                "trade": {"id": "trade_1", "status": "open"},
                "pyramids": [],
                "exit": None
            })
            mock_bot.initialize = AsyncMock()
            mock_bot.start = AsyncMock()
            mock_bot.stop = AsyncMock()
            mock_report.start_scheduler = MagicMock()
            mock_report.stop_scheduler = MagicMock()

            from app.main import app
            client = TestClient(app, raise_server_exceptions=False)

            response = client.get("/trades/trade_1")
            assert response.status_code == 200
            data = response.json()
            assert data["trade"]["id"] == "trade_1"

    def test_get_trade_not_found(self):
        """Test getting a trade that doesn't exist."""
        from fastapi.testclient import TestClient

        with patch("app.main.db") as mock_db, \
             patch("app.main.telegram_bot") as mock_bot, \
             patch("app.main.report_service") as mock_report:

            mock_db.connect = AsyncMock()
            mock_db.disconnect = AsyncMock()
            mock_db.get_trade_with_pyramids = AsyncMock(return_value=None)
            mock_bot.initialize = AsyncMock()
            mock_bot.start = AsyncMock()
            mock_bot.stop = AsyncMock()
            mock_report.start_scheduler = MagicMock()
            mock_report.stop_scheduler = MagicMock()

            from app.main import app
            client = TestClient(app, raise_server_exceptions=False)

            response = client.get("/trades/nonexistent")
            assert response.status_code == 404


class TestReportsEndpoints:
    """Tests for /reports endpoints."""

    def test_send_daily_report(self):
        """Test sending daily report."""
        from fastapi.testclient import TestClient

        with patch("app.main.db") as mock_db, \
             patch("app.main.telegram_bot") as mock_bot, \
             patch("app.main.report_service") as mock_report:

            mock_db.connect = AsyncMock()
            mock_db.disconnect = AsyncMock()
            mock_bot.initialize = AsyncMock()
            mock_bot.start = AsyncMock()
            mock_bot.stop = AsyncMock()
            mock_report.start_scheduler = MagicMock()
            mock_report.stop_scheduler = MagicMock()
            mock_report.generate_and_send_daily_report = AsyncMock(return_value=True)

            from app.main import app
            client = TestClient(app, raise_server_exceptions=False)

            response = client.post("/reports/send")
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True


class TestDailyReportData:
    """Tests for DailyReportData model."""

    def test_daily_report_data_all_fields(self):
        """Test DailyReportData with all required fields."""
        from app.models import DailyReportData

        report = DailyReportData(
            date="2026-01-20",
            total_trades=5,
            total_pyramids=8,
            total_pnl_usdt=150.0,
            total_pnl_percent=5.0,
            trades=[],
            by_exchange={"binance": {"pnl": 150.0, "trades": 5}},
            by_timeframe={"1h": {"pnl": 150.0, "trades": 5}},
            by_pair={"BTC/USDT": 150.0},
            equity_points=[],
            chart_stats=None
        )

        assert report.date == "2026-01-20"
        assert report.total_trades == 5
        assert report.total_pnl_usdt == 150.0

    def test_daily_report_data_default_lists(self):
        """Test DailyReportData with default empty lists."""
        from app.models import DailyReportData

        report = DailyReportData(
            date="2026-01-20",
            total_trades=0,
            total_pyramids=0,
            total_pnl_usdt=0.0,
            total_pnl_percent=0.0,
            by_exchange={},
            by_timeframe={},
            by_pair={},
        )

        assert report.trades == []
        assert report.equity_points == []
        assert report.chart_stats is None


class TestWebhookEndpoint:
    """Tests for /webhook endpoint."""

    def test_webhook_unauthorized(self):
        """Test webhook rejects requests with wrong secret."""
        from fastapi.testclient import TestClient

        with patch("app.main.db") as mock_db, \
             patch("app.main.telegram_bot") as mock_bot, \
             patch("app.main.report_service") as mock_report, \
             patch("app.main.settings") as mock_settings:

            mock_db.connect = AsyncMock()
            mock_db.disconnect = AsyncMock()
            mock_bot.initialize = AsyncMock()
            mock_bot.start = AsyncMock()
            mock_bot.stop = AsyncMock()
            mock_report.start_scheduler = MagicMock()
            mock_report.stop_scheduler = MagicMock()
            mock_settings.webhook_secret = "correct_secret"

            from app.main import app
            client = TestClient(app, raise_server_exceptions=False)

            response = client.post(
                "/webhook",
                json={"action": "buy"},
                headers={"X-Webhook-Secret": "wrong_secret"}
            )
            assert response.status_code == 401


class TestTradingViewAlertModel:
    """Tests for TradingViewAlert model."""

    def test_long_entry_signal(self):
        """Test buy + long = entry for long position."""
        from app.models import TradingViewAlert

        alert = TradingViewAlert(
            timestamp="2026-01-20T10:00:00Z",
            exchange="binance",
            symbol="BTCUSDT",
            timeframe="1h",
            action="buy",
            order_id="test_123",
            contracts=0.01,
            close=50000.0,
            position_side="long",
            position_qty=0.01
        )
        assert alert.is_entry() is True
        assert alert.is_exit() is False

    def test_long_exit_signal(self):
        """Test sell + flat = exit for long position."""
        from app.models import TradingViewAlert

        alert = TradingViewAlert(
            timestamp="2026-01-20T10:00:00Z",
            exchange="binance",
            symbol="BTCUSDT",
            timeframe="1h",
            action="sell",
            order_id="test_123",
            contracts=0.0,
            close=52000.0,
            position_side="flat",
            position_qty=0.0
        )
        assert alert.is_exit() is True
        assert alert.is_entry() is False

    def test_short_signal_not_entry(self):
        """Test sell + short is NOT considered entry (long only)."""
        from app.models import TradingViewAlert

        alert = TradingViewAlert(
            timestamp="2026-01-20T10:00:00Z",
            exchange="binance",
            symbol="BTCUSDT",
            timeframe="1h",
            action="sell",
            order_id="test_456",
            contracts=0.01,
            close=50000.0,
            position_side="short",
            position_qty=0.01
        )
        # Short positions not supported as entry
        assert alert.is_entry() is False

    def test_get_pair(self):
        """Test get_pair method extracts base/quote correctly."""
        from app.models import TradingViewAlert
        from app.services.symbol_normalizer import parse_symbol

        alert = TradingViewAlert(
            timestamp="2026-01-20T10:00:00Z",
            exchange="binance",
            symbol="ETHUSDT",
            timeframe="4h",
            action="buy",
            order_id="test_789",
            contracts=0.5,
            close=3000.0,
            position_side="long",
            position_qty=0.5
        )

        parsed = parse_symbol(alert.symbol)
        assert parsed.base == "ETH"
        assert parsed.quote == "USDT"


class TestModelsValidation:
    """Tests for model validation."""

    def test_pyramid_entry_data(self):
        """Test PyramidEntryData model."""
        from app.models import PyramidEntryData

        data = PyramidEntryData(
            group_id="BTC_Binance_1h_001",
            pyramid_index=0,
            exchange="binance",
            base="BTC",
            quote="USDT",
            timeframe="1h",
            entry_price=50000.0,
            position_size=0.02,
            capital_usdt=1000.0,
            exchange_timestamp="2026-01-20T10:00:00Z",
            received_timestamp=datetime.utcnow(),
            total_pyramids=1
        )

        assert data.group_id == "BTC_Binance_1h_001"
        assert data.pyramid_index == 0
        assert data.entry_price == 50000.0

    def test_trade_closed_data(self):
        """Test TradeClosedData model."""
        from app.models import TradeClosedData

        data = TradeClosedData(
            trade_id="trade_001",
            group_id="BTC_Binance_1h_001",
            timeframe="1h",
            exchange="binance",
            base="BTC",
            quote="USDT",
            pyramids=[{"index": 0, "entry_price": 50000.0, "size": 0.02}],
            exit_price=51000.0,
            exit_time=datetime.utcnow(),
            exchange_timestamp="2026-01-20T12:00:00Z",
            received_timestamp=datetime.utcnow(),
            gross_pnl=20.0,
            total_fees=2.0,
            net_pnl=18.0,
            net_pnl_percent=1.8
        )

        assert data.exit_price == 51000.0
        assert data.net_pnl == 18.0
        assert data.trade_id == "trade_001"

    def test_equity_point(self):
        """Test EquityPoint model."""
        from app.models import EquityPoint

        point = EquityPoint(
            timestamp=datetime.utcnow(),
            cumulative_pnl=150.0
        )

        assert point.cumulative_pnl == 150.0

    def test_chart_stats(self):
        """Test ChartStats model."""
        from app.models import ChartStats

        stats = ChartStats(
            total_net_pnl=150.0,
            max_drawdown_percent=5.5,
            max_drawdown_usdt=100.0,
            trades_opened_today=5,
            trades_closed_today=3,
            trades_still_open=2,
            win_rate=65.0,
            total_used_equity=10000.0,
            profit_factor=2.5,
            win_loss_ratio=1.8,
            cumulative_pnl=500.0
        )

        assert stats.total_net_pnl == 150.0
        assert stats.win_rate == 65.0
        assert stats.profit_factor == 2.5
        assert stats.trades_closed_today == 3

    def test_trade_history_item(self):
        """Test TradeHistoryItem model."""
        from app.models import TradeHistoryItem

        item = TradeHistoryItem(
            group_id="ETH_Bybit_4h_001",
            exchange="bybit",
            pair="ETH/USDT",
            timeframe="4h",
            pyramids_count=3,
            pnl_usdt=250.50,
            pnl_percent=8.35
        )

        assert item.group_id == "ETH_Bybit_4h_001"
        assert item.pnl_usdt == 250.50


class TestAppContext:
    """Tests for application context."""

    def test_app_has_routes(self):
        """Test that app has expected routes registered."""
        from fastapi.testclient import TestClient

        with patch("app.main.db") as mock_db, \
             patch("app.main.telegram_bot") as mock_bot, \
             patch("app.main.report_service") as mock_report:

            mock_db.connect = AsyncMock()
            mock_db.disconnect = AsyncMock()
            mock_bot.initialize = AsyncMock()
            mock_bot.start = AsyncMock()
            mock_bot.stop = AsyncMock()
            mock_report.start_scheduler = MagicMock()
            mock_report.stop_scheduler = MagicMock()

            from app.main import app

            # Verify routes exist
            route_paths = [route.path for route in app.routes]
            assert "/health" in route_paths
            assert "/webhook" in route_paths
            assert "/trades" in route_paths
