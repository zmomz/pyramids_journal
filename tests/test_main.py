"""
Tests for FastAPI application in app/main.py

Tests the webhook endpoint and API routes.
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


class TestHealthEndpoint:
    """Tests for /health endpoint."""

    def test_health_returns_ok(self):
        """Test health check returns healthy status."""
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


class TestWebhookEndpoint:
    """Tests for /webhook endpoint."""

    @pytest.mark.asyncio
    async def test_webhook_invalid_secret(self):
        """Test webhook rejects invalid secret."""
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
            mock_settings.log_level = "INFO"

            from app.main import app
            client = TestClient(app, raise_server_exceptions=False)

            response = client.post(
                "/webhook",
                json={"action": "buy", "symbol": "BTCUSDT", "exchange": "binance"},
                headers={"X-Webhook-Secret": "wrong_secret"}
            )
            assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_webhook_invalid_json(self):
        """Test webhook rejects invalid JSON."""
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
            mock_settings.webhook_secret = ""
            mock_settings.log_level = "INFO"

            from app.main import app
            client = TestClient(app, raise_server_exceptions=False)

            response = client.post(
                "/webhook",
                content="not valid json",
                headers={"Content-Type": "application/json"}
            )
            assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_webhook_paused_processing(self):
        """Test webhook returns success when processing is paused."""
        with patch("app.main.db") as mock_db, \
             patch("app.main.telegram_bot") as mock_bot, \
             patch("app.main.report_service") as mock_report, \
             patch("app.main.settings") as mock_settings:

            mock_db.connect = AsyncMock()
            mock_db.disconnect = AsyncMock()
            mock_db.is_paused = AsyncMock(return_value=True)
            mock_bot.initialize = AsyncMock()
            mock_bot.start = AsyncMock()
            mock_bot.stop = AsyncMock()
            mock_report.start_scheduler = MagicMock()
            mock_report.stop_scheduler = MagicMock()
            mock_settings.webhook_secret = ""
            mock_settings.log_level = "INFO"

            from app.main import app
            client = TestClient(app, raise_server_exceptions=False)

            response = client.post(
                "/webhook",
                json={
                    "action": "buy",
                    "symbol": "BTCUSDT",
                    "exchange": "binance",
                    "timeframe": "1h",
                    "position_side": "long",
                    "order_id": "test_123"
                }
            )
            assert response.status_code == 200
            data = response.json()
            assert "paused" in data["message"].lower()

    @pytest.mark.asyncio
    async def test_webhook_ignored_pair(self):
        """Test webhook returns success for ignored pairs."""
        with patch("app.main.db") as mock_db, \
             patch("app.main.telegram_bot") as mock_bot, \
             patch("app.main.report_service") as mock_report, \
             patch("app.main.settings") as mock_settings, \
             patch("app.main.parse_symbol") as mock_parse:

            mock_db.connect = AsyncMock()
            mock_db.disconnect = AsyncMock()
            mock_db.is_paused = AsyncMock(return_value=False)
            mock_db.is_pair_ignored = AsyncMock(return_value=True)
            mock_bot.initialize = AsyncMock()
            mock_bot.start = AsyncMock()
            mock_bot.stop = AsyncMock()
            mock_report.start_scheduler = MagicMock()
            mock_report.stop_scheduler = MagicMock()
            mock_settings.webhook_secret = ""
            mock_settings.log_level = "INFO"

            # Mock parse_symbol
            mock_parsed = MagicMock()
            mock_parsed.base = "BTC"
            mock_parsed.quote = "USDT"
            mock_parse.return_value = mock_parsed

            from app.main import app
            client = TestClient(app, raise_server_exceptions=False)

            response = client.post(
                "/webhook",
                json={
                    "action": "buy",
                    "symbol": "BTCUSDT",
                    "exchange": "binance",
                    "timeframe": "1h",
                    "position_side": "long",
                    "order_id": "test_123"
                }
            )
            assert response.status_code == 200
            data = response.json()
            assert "ignored" in data["message"].lower()

    @pytest.mark.asyncio
    async def test_webhook_successful_entry(self):
        """Test webhook processes entry signal successfully."""
        from app.models import PyramidEntryData
        from app.services.trade_service import TradeResult

        with patch("app.main.db") as mock_db, \
             patch("app.main.telegram_bot") as mock_bot, \
             patch("app.main.report_service") as mock_report, \
             patch("app.main.settings") as mock_settings, \
             patch("app.main.trade_service") as mock_trade_svc, \
             patch("app.main.telegram_service") as mock_telegram:

            mock_db.connect = AsyncMock()
            mock_db.disconnect = AsyncMock()
            mock_db.is_paused = AsyncMock(return_value=False)
            mock_db.is_pair_ignored = AsyncMock(return_value=False)
            mock_bot.initialize = AsyncMock()
            mock_bot.start = AsyncMock()
            mock_bot.stop = AsyncMock()
            mock_report.start_scheduler = MagicMock()
            mock_report.stop_scheduler = MagicMock()
            mock_settings.webhook_secret = ""
            mock_settings.log_level = "INFO"

            # Mock trade service result
            entry_data = MagicMock(spec=PyramidEntryData)
            result = TradeResult(
                success=True,
                message="Pyramid 0 recorded",
                trade_id="trade_123",
                group_id="BTC_Binance_1h_001",
                price=50000.0,
                entry_data=entry_data
            )
            mock_trade_svc.process_signal = AsyncMock(return_value=(result, entry_data))
            mock_telegram.send_pyramid_entry = AsyncMock()

            from app.main import app
            client = TestClient(app, raise_server_exceptions=False)

            response = client.post(
                "/webhook",
                json={
                    "action": "buy",
                    "symbol": "BTCUSDT",
                    "exchange": "binance",
                    "timeframe": "1h",
                    "position_side": "long",
                    "order_id": "test_123"
                }
            )
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["trade_id"] == "trade_123"


class TestTradesEndpoint:
    """Tests for /trades endpoint."""

    def test_list_trades(self):
        """Test listing recent trades."""
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

    def test_generate_daily_report(self):
        """Test generating daily report."""
        from app.models import DailyReportData

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

            # Create mock report data
            mock_report_data = DailyReportData(
                date="2026-01-20",
                total_trades=5,
                total_pyramids=8,
                total_pnl_usdt=150.0,
                total_pnl_percent=5.0
            )
            mock_report.generate_daily_report = AsyncMock(return_value=mock_report_data)

            from app.main import app
            client = TestClient(app, raise_server_exceptions=False)

            response = client.post("/reports/daily")
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["report"]["date"] == "2026-01-20"

    def test_send_daily_report(self):
        """Test sending daily report."""
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
