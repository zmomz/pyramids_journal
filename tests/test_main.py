"""
Tests for FastAPI application in app/main.py

Comprehensive endpoint testing with TestClient.
Each test covers a specific API behavior that could cause bugs in production.
"""

from datetime import datetime, UTC
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi.testclient import TestClient


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def mock_dependencies():
    """Mock all external dependencies for FastAPI testing."""
    with patch("app.main.db") as mock_db, \
         patch("app.main.telegram_bot") as mock_bot, \
         patch("app.main.report_service") as mock_report:

        # Database
        mock_db.connect = AsyncMock()
        mock_db.disconnect = AsyncMock()
        mock_db.is_paused = AsyncMock(return_value=False)
        mock_db.is_pair_ignored = AsyncMock(return_value=False)
        mock_db.get_recent_trades = AsyncMock(return_value=[])
        mock_db.get_trade_with_pyramids = AsyncMock(return_value=None)

        # Telegram bot
        mock_bot.initialize = AsyncMock()
        mock_bot.start = AsyncMock()
        mock_bot.stop = AsyncMock()

        # Report service
        mock_report.start_scheduler = AsyncMock()
        mock_report.stop_scheduler = MagicMock()
        mock_report.generate_daily_report = AsyncMock()
        mock_report.generate_and_send_daily_report = AsyncMock(return_value=True)

        yield {
            "db": mock_db,
            "bot": mock_bot,
            "report": mock_report,
        }


@pytest.fixture
def client(mock_dependencies):
    """Create TestClient with mocked dependencies."""
    from app.main import app
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def valid_entry_payload():
    """Valid webhook payload for an entry signal."""
    return {
        "timestamp": "2026-01-20T10:00:00Z",
        "exchange": "binance",
        "symbol": "BTCUSDT",
        "timeframe": "1h",
        "action": "buy",
        "order_id": "test_123",
        "contracts": 0.01,
        "close": 50000.0,
        "position_side": "long",
        "position_qty": 0.01,
    }


@pytest.fixture
def valid_exit_payload():
    """Valid webhook payload for an exit signal."""
    return {
        "timestamp": "2026-01-20T12:00:00Z",
        "exchange": "binance",
        "symbol": "BTCUSDT",
        "timeframe": "1h",
        "action": "sell",
        "order_id": "test_456",
        "contracts": 0.0,
        "close": 52000.0,
        "position_side": "flat",
        "position_qty": 0.0,
    }


# =============================================================================
# HEALTH ENDPOINT
# =============================================================================

class TestHealthEndpoint:
    """Tests for GET /health endpoint."""

    def test_health_returns_healthy_status(self, client):
        """
        Bug prevented: Health check fails silently.
        API behavior: Always returns 200 with status "healthy".
        """
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "pyramids-journal"


# =============================================================================
# WEBHOOK ENDPOINT - AUTHENTICATION
# =============================================================================

class TestWebhookAuthentication:
    """Tests for webhook secret verification."""

    def test_no_secret_configured_allows_all(self):
        """
        Bug prevented: Webhook rejects valid requests when no secret configured.
        API behavior: When webhook_secret is empty, all requests pass.
        """
        from app.main import verify_webhook_secret

        with patch("app.main.settings") as mock_settings:
            mock_settings.webhook_secret = ""
            assert verify_webhook_secret(None) is True
            assert verify_webhook_secret("any_value") is True

    def test_correct_secret_passes(self):
        """
        Bug prevented: Valid webhook rejected.
        API behavior: Matching secret returns True.
        """
        from app.main import verify_webhook_secret

        with patch("app.main.settings") as mock_settings:
            mock_settings.webhook_secret = "test_secret"
            assert verify_webhook_secret("test_secret") is True

    def test_wrong_secret_rejected(self):
        """
        Bug prevented: Invalid webhook accepted, allowing unauthorized signals.
        API behavior: Non-matching secret returns False.
        """
        from app.main import verify_webhook_secret

        with patch("app.main.settings") as mock_settings:
            mock_settings.webhook_secret = "test_secret"
            assert verify_webhook_secret("wrong") is False
            assert verify_webhook_secret(None) is False

    def test_webhook_rejects_wrong_secret(self, valid_entry_payload):
        """
        Bug prevented: Unauthorized signals processed.
        API behavior: Returns 401 for invalid secret.
        """
        with patch("app.main.db") as mock_db, \
             patch("app.main.telegram_bot") as mock_bot, \
             patch("app.main.report_service") as mock_report, \
             patch("app.main.settings") as mock_settings:

            mock_db.connect = AsyncMock()
            mock_db.disconnect = AsyncMock()
            mock_bot.initialize = AsyncMock()
            mock_bot.start = AsyncMock()
            mock_bot.stop = AsyncMock()
            mock_report.start_scheduler = AsyncMock()
            mock_report.stop_scheduler = MagicMock()
            mock_settings.webhook_secret = "correct_secret"

            from app.main import app
            client = TestClient(app, raise_server_exceptions=False)

            response = client.post(
                "/webhook",
                json=valid_entry_payload,
                headers={"X-Webhook-Secret": "wrong_secret"}
            )

            assert response.status_code == 401
            assert "Invalid webhook secret" in response.json()["detail"]


# =============================================================================
# WEBHOOK ENDPOINT - PAYLOAD VALIDATION
# =============================================================================

class TestWebhookPayloadValidation:
    """Tests for webhook payload validation."""

    def test_invalid_json_returns_400(self, mock_dependencies):
        """
        Bug prevented: Invalid JSON crashes the server.
        API behavior: Returns 400 with "Invalid JSON payload".
        """
        from app.main import app
        client = TestClient(app, raise_server_exceptions=False)

        response = client.post(
            "/webhook",
            content="not valid json {{{",
            headers={"Content-Type": "application/json"}
        )

        assert response.status_code == 400
        assert "Invalid JSON" in response.json()["detail"]

    def test_missing_required_field_returns_400(self, mock_dependencies):
        """
        Bug prevented: Incomplete payload causes server error.
        API behavior: Returns 400 with Pydantic validation error.
        """
        from app.main import app
        client = TestClient(app, raise_server_exceptions=False)

        # Missing 'action' field
        incomplete_payload = {
            "timestamp": "2026-01-20T10:00:00Z",
            "exchange": "binance",
            "symbol": "BTCUSDT",
            # "action" missing
        }

        response = client.post("/webhook", json=incomplete_payload)

        assert response.status_code == 400
        assert "Invalid payload" in response.json()["detail"]

    def test_invalid_action_value_returns_400(self, mock_dependencies):
        """
        Bug prevented: Invalid action value processed incorrectly.
        API behavior: Returns 400 when action is not 'buy' or 'sell'.
        """
        from app.main import app
        client = TestClient(app, raise_server_exceptions=False)

        invalid_payload = {
            "timestamp": "2026-01-20T10:00:00Z",
            "exchange": "binance",
            "symbol": "BTCUSDT",
            "timeframe": "1h",
            "action": "invalid",  # Not 'buy' or 'sell'
            "order_id": "test_123",
            "contracts": 0.01,
            "close": 50000.0,
            "position_side": "long",
            "position_qty": 0.01,
        }

        response = client.post("/webhook", json=invalid_payload)

        assert response.status_code == 400

    def test_invalid_position_side_returns_400(self, mock_dependencies):
        """
        Bug prevented: Invalid position_side processed incorrectly.
        API behavior: Returns 400 when position_side is invalid.
        """
        from app.main import app
        client = TestClient(app, raise_server_exceptions=False)

        invalid_payload = {
            "timestamp": "2026-01-20T10:00:00Z",
            "exchange": "binance",
            "symbol": "BTCUSDT",
            "timeframe": "1h",
            "action": "buy",
            "order_id": "test_123",
            "contracts": 0.01,
            "close": 50000.0,
            "position_side": "invalid",  # Not long/short/flat
            "position_qty": 0.01,
        }

        response = client.post("/webhook", json=invalid_payload)

        assert response.status_code == 400


# =============================================================================
# WEBHOOK ENDPOINT - PAUSED/IGNORED
# =============================================================================

class TestWebhookPausedIgnored:
    """Tests for paused processing and ignored pairs."""

    def test_paused_returns_success_with_message(self, valid_entry_payload):
        """
        Bug prevented: Paused signals still processed.
        API behavior: Returns success=True with "paused" message.
        """
        with patch("app.main.db") as mock_db, \
             patch("app.main.telegram_bot") as mock_bot, \
             patch("app.main.report_service") as mock_report:

            mock_db.connect = AsyncMock()
            mock_db.disconnect = AsyncMock()
            mock_db.is_paused = AsyncMock(return_value=True)  # Paused
            mock_bot.initialize = AsyncMock()
            mock_bot.start = AsyncMock()
            mock_bot.stop = AsyncMock()
            mock_report.start_scheduler = AsyncMock()
            mock_report.stop_scheduler = MagicMock()

            from app.main import app
            client = TestClient(app, raise_server_exceptions=False)

            response = client.post("/webhook", json=valid_entry_payload)

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "paused" in data["message"].lower()

    def test_ignored_pair_returns_success_with_message(self, valid_entry_payload):
        """
        Bug prevented: Ignored pair signals still processed.
        API behavior: Returns success=True with "ignored" message.
        """
        with patch("app.main.db") as mock_db, \
             patch("app.main.telegram_bot") as mock_bot, \
             patch("app.main.report_service") as mock_report:

            mock_db.connect = AsyncMock()
            mock_db.disconnect = AsyncMock()
            mock_db.is_paused = AsyncMock(return_value=False)
            mock_db.is_pair_ignored = AsyncMock(return_value=True)  # Ignored
            mock_bot.initialize = AsyncMock()
            mock_bot.start = AsyncMock()
            mock_bot.stop = AsyncMock()
            mock_report.start_scheduler = AsyncMock()
            mock_report.stop_scheduler = MagicMock()

            from app.main import app
            client = TestClient(app, raise_server_exceptions=False)

            response = client.post("/webhook", json=valid_entry_payload)

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "ignored" in data["message"].lower()


# =============================================================================
# WEBHOOK ENDPOINT - SIGNAL PROCESSING
# =============================================================================

class TestWebhookSignalProcessing:
    """Tests for signal processing through trade_service."""

    def test_successful_entry_signal(self, valid_entry_payload):
        """
        Bug prevented: Successful entry not recorded.
        API behavior: Returns success=True with trade_id and price.
        """
        from app.services.trade_service import TradeResult
        from app.models import PyramidEntryData

        mock_entry_data = PyramidEntryData(
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
            received_timestamp=datetime.now(UTC),
            total_pyramids=1,
        )

        with patch("app.main.db") as mock_db, \
             patch("app.main.telegram_bot") as mock_bot, \
             patch("app.main.report_service") as mock_report, \
             patch("app.main.trade_service") as mock_trade, \
             patch("app.main.telegram_service") as mock_telegram:

            mock_db.connect = AsyncMock()
            mock_db.disconnect = AsyncMock()
            mock_db.is_paused = AsyncMock(return_value=False)
            mock_db.is_pair_ignored = AsyncMock(return_value=False)
            mock_bot.initialize = AsyncMock()
            mock_bot.start = AsyncMock()
            mock_bot.stop = AsyncMock()
            mock_report.start_scheduler = AsyncMock()
            mock_report.stop_scheduler = MagicMock()

            mock_trade.process_signal = AsyncMock(return_value=(
                TradeResult(
                    success=True,
                    message="Trade created",
                    trade_id="trade_001",
                    group_id="BTC_Binance_1h_001",
                    price=50000.0,
                ),
                mock_entry_data,
            ))
            mock_telegram.send_pyramid_entry = AsyncMock()

            from app.main import app
            client = TestClient(app, raise_server_exceptions=False)

            response = client.post("/webhook", json=valid_entry_payload)

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["trade_id"] == "trade_001"
            assert data["price"] == 50000.0

    def test_successful_exit_signal(self, valid_exit_payload):
        """
        Bug prevented: Successful exit not recorded.
        API behavior: Returns success=True with trade details.
        """
        from app.services.trade_service import TradeResult
        from app.models import TradeClosedData

        mock_exit_data = TradeClosedData(
            trade_id="trade_001",
            group_id="BTC_Binance_1h_001",
            timeframe="1h",
            exchange="binance",
            base="BTC",
            quote="USDT",
            pyramids=[],
            exit_price=52000.0,
            exit_time=datetime.now(UTC),
            exchange_timestamp="2026-01-20T12:00:00Z",
            received_timestamp=datetime.now(UTC),
            gross_pnl=40.0,
            total_fees=2.0,
            net_pnl=38.0,
            net_pnl_percent=3.8,
        )

        with patch("app.main.db") as mock_db, \
             patch("app.main.telegram_bot") as mock_bot, \
             patch("app.main.report_service") as mock_report, \
             patch("app.main.trade_service") as mock_trade, \
             patch("app.main.telegram_service") as mock_telegram:

            mock_db.connect = AsyncMock()
            mock_db.disconnect = AsyncMock()
            mock_db.is_paused = AsyncMock(return_value=False)
            mock_db.is_pair_ignored = AsyncMock(return_value=False)
            mock_bot.initialize = AsyncMock()
            mock_bot.start = AsyncMock()
            mock_bot.stop = AsyncMock()
            mock_report.start_scheduler = AsyncMock()
            mock_report.stop_scheduler = MagicMock()

            mock_trade.process_signal = AsyncMock(return_value=(
                TradeResult(
                    success=True,
                    message="Trade closed",
                    trade_id="trade_001",
                    price=52000.0,
                ),
                mock_exit_data,
            ))
            mock_telegram.send_trade_closed = AsyncMock()

            from app.main import app
            client = TestClient(app, raise_server_exceptions=False)

            response = client.post("/webhook", json=valid_exit_payload)

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True

    def test_failed_signal_processing(self, valid_entry_payload):
        """
        Bug prevented: Failed signal silently ignored.
        API behavior: Returns success=False with error message.
        """
        from app.services.trade_service import TradeResult

        with patch("app.main.db") as mock_db, \
             patch("app.main.telegram_bot") as mock_bot, \
             patch("app.main.report_service") as mock_report, \
             patch("app.main.trade_service") as mock_trade:

            mock_db.connect = AsyncMock()
            mock_db.disconnect = AsyncMock()
            mock_db.is_paused = AsyncMock(return_value=False)
            mock_db.is_pair_ignored = AsyncMock(return_value=False)
            mock_bot.initialize = AsyncMock()
            mock_bot.start = AsyncMock()
            mock_bot.stop = AsyncMock()
            mock_report.start_scheduler = AsyncMock()
            mock_report.stop_scheduler = MagicMock()

            mock_trade.process_signal = AsyncMock(return_value=(
                TradeResult(
                    success=False,
                    message="Price fetch failed",
                    error="PRICE_FETCH_FAILED",
                ),
                None,
            ))

            from app.main import app
            client = TestClient(app, raise_server_exceptions=False)

            response = client.post("/webhook", json=valid_entry_payload)

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is False
            assert data["error"] == "PRICE_FETCH_FAILED"

    def test_telegram_notification_error_doesnt_fail_webhook(self, valid_entry_payload):
        """
        Bug prevented: Telegram error causes webhook to fail.
        API behavior: Returns success=True even if Telegram fails.
        """
        from app.services.trade_service import TradeResult
        from app.models import PyramidEntryData

        mock_entry_data = PyramidEntryData(
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
            received_timestamp=datetime.now(UTC),
            total_pyramids=1,
        )

        with patch("app.main.db") as mock_db, \
             patch("app.main.telegram_bot") as mock_bot, \
             patch("app.main.report_service") as mock_report, \
             patch("app.main.trade_service") as mock_trade, \
             patch("app.main.telegram_service") as mock_telegram:

            mock_db.connect = AsyncMock()
            mock_db.disconnect = AsyncMock()
            mock_db.is_paused = AsyncMock(return_value=False)
            mock_db.is_pair_ignored = AsyncMock(return_value=False)
            mock_bot.initialize = AsyncMock()
            mock_bot.start = AsyncMock()
            mock_bot.stop = AsyncMock()
            mock_report.start_scheduler = AsyncMock()
            mock_report.stop_scheduler = MagicMock()

            mock_trade.process_signal = AsyncMock(return_value=(
                TradeResult(
                    success=True,
                    message="Trade created",
                    trade_id="trade_001",
                    price=50000.0,
                ),
                mock_entry_data,
            ))
            # Telegram fails
            mock_telegram.send_pyramid_entry = AsyncMock(
                side_effect=Exception("Telegram connection failed")
            )

            from app.main import app
            client = TestClient(app, raise_server_exceptions=False)

            response = client.post("/webhook", json=valid_entry_payload)

            # Should still succeed
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True


# =============================================================================
# TRADES ENDPOINTS
# =============================================================================

class TestTradesEndpoints:
    """Tests for /trades endpoints."""

    def test_list_trades_empty(self, client, mock_dependencies):
        """
        Bug prevented: Empty list causes error.
        API behavior: Returns count=0 and empty list.
        """
        response = client.get("/trades")

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0
        assert data["trades"] == []

    def test_list_trades_with_data(self, mock_dependencies):
        """
        Bug prevented: Trade data not returned correctly.
        API behavior: Returns all trades with count.
        """
        mock_dependencies["db"].get_recent_trades = AsyncMock(return_value=[
            {"id": "trade_1", "exchange": "binance", "base": "BTC", "quote": "USDT"},
            {"id": "trade_2", "exchange": "bybit", "base": "ETH", "quote": "USDT"},
        ])

        from app.main import app
        client = TestClient(app, raise_server_exceptions=False)

        response = client.get("/trades")

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 2
        assert len(data["trades"]) == 2

    def test_list_trades_with_limit(self, mock_dependencies):
        """
        Bug prevented: Limit parameter ignored.
        API behavior: Passes limit to database query.
        """
        from app.main import app
        client = TestClient(app, raise_server_exceptions=False)

        response = client.get("/trades?limit=10")

        assert response.status_code == 200
        mock_dependencies["db"].get_recent_trades.assert_called_with(10)

    def test_get_trade_found(self, mock_dependencies):
        """
        Bug prevented: Existing trade not returned.
        API behavior: Returns full trade details with pyramids.
        """
        mock_dependencies["db"].get_trade_with_pyramids = AsyncMock(return_value={
            "trade": {"id": "trade_1", "status": "open"},
            "pyramids": [{"id": "pyr_1", "pyramid_index": 0}],
            "exit": None,
        })

        from app.main import app
        client = TestClient(app, raise_server_exceptions=False)

        response = client.get("/trades/trade_1")

        assert response.status_code == 200
        data = response.json()
        assert data["trade"]["id"] == "trade_1"
        assert len(data["pyramids"]) == 1

    def test_get_trade_not_found(self, client, mock_dependencies):
        """
        Bug prevented: Missing trade returns wrong status code.
        API behavior: Returns 404 for non-existent trade.
        """
        response = client.get("/trades/nonexistent")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


# =============================================================================
# REPORTS ENDPOINTS
# =============================================================================

class TestReportsEndpoints:
    """Tests for /reports endpoints."""

    def test_generate_daily_report(self, mock_dependencies):
        """
        Bug prevented: Report generation fails.
        API behavior: Returns generated report data.
        """
        from app.models import DailyReportData

        mock_report_data = DailyReportData(
            date="2026-01-20",
            total_trades=5,
            total_pyramids=8,
            total_pnl_usdt=150.0,
            total_pnl_percent=5.0,
            trades=[],
            by_exchange={"binance": {"pnl": 150.0, "trades": 5}},
            by_timeframe={"1h": {"pnl": 150.0, "trades": 5}},
            by_pair={"BTC/USDT": 150.0},
        )

        mock_dependencies["report"].generate_daily_report = AsyncMock(
            return_value=mock_report_data
        )

        from app.main import app
        client = TestClient(app, raise_server_exceptions=False)

        response = client.post("/reports/daily")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["report"]["date"] == "2026-01-20"
        assert data["report"]["total_trades"] == 5

    def test_generate_daily_report_with_date(self, mock_dependencies):
        """
        Bug prevented: Custom date ignored.
        API behavior: Passes date to report service.
        """
        from app.models import DailyReportData

        mock_report_data = DailyReportData(
            date="2026-01-15",
            total_trades=0,
            total_pyramids=0,
            total_pnl_usdt=0.0,
            total_pnl_percent=0.0,
            trades=[],
            by_exchange={},
            by_timeframe={},
            by_pair={},
        )

        mock_dependencies["report"].generate_daily_report = AsyncMock(
            return_value=mock_report_data
        )

        from app.main import app
        client = TestClient(app, raise_server_exceptions=False)

        response = client.post("/reports/daily?date=2026-01-15")

        assert response.status_code == 200
        mock_dependencies["report"].generate_daily_report.assert_called_with("2026-01-15")

    def test_send_daily_report_success(self, client, mock_dependencies):
        """
        Bug prevented: Report sent but wrong response.
        API behavior: Returns success=True with message.
        """
        response = client.post("/reports/send")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "sent" in data["message"].lower()

    def test_send_daily_report_failure(self, mock_dependencies):
        """
        Bug prevented: Failed send returns success.
        API behavior: Returns success=False when send fails.
        """
        mock_dependencies["report"].generate_and_send_daily_report = AsyncMock(
            return_value=False
        )

        from app.main import app
        client = TestClient(app, raise_server_exceptions=False)

        response = client.post("/reports/send")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "failed" in data["message"].lower()


# =============================================================================
# GLOBAL EXCEPTION HANDLER
# =============================================================================

class TestGlobalExceptionHandler:
    """Tests for global exception handler."""

    def test_unhandled_exception_returns_500(self, mock_dependencies):
        """
        Bug prevented: Unhandled exception leaks stack trace.
        API behavior: Returns 500 with generic error message.
        """
        # Force an unhandled exception in the trades endpoint
        mock_dependencies["db"].get_recent_trades = AsyncMock(
            side_effect=RuntimeError("Database connection lost")
        )

        from app.main import app
        client = TestClient(app, raise_server_exceptions=False)

        response = client.get("/trades")

        assert response.status_code == 500
        data = response.json()
        assert data["success"] is False
        assert "error" in data


# =============================================================================
# MODEL VALIDATION
# =============================================================================

class TestTradingViewAlertModel:
    """Tests for TradingViewAlert model validation."""

    def test_entry_signal_classification(self):
        """
        Bug prevented: Entry misclassified as exit.
        API behavior: buy + long = entry.
        """
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
            position_qty=0.01,
        )

        assert alert.is_entry() is True
        assert alert.is_exit() is False

    def test_exit_signal_classification(self):
        """
        Bug prevented: Exit misclassified as entry.
        API behavior: sell + flat = exit.
        """
        from app.models import TradingViewAlert

        alert = TradingViewAlert(
            timestamp="2026-01-20T12:00:00Z",
            exchange="binance",
            symbol="BTCUSDT",
            timeframe="1h",
            action="sell",
            order_id="test_456",
            contracts=0.0,
            close=52000.0,
            position_side="flat",
            position_qty=0.0,
        )

        assert alert.is_exit() is True
        assert alert.is_entry() is False

    def test_short_signal_not_entry(self):
        """
        Bug prevented: Short signal treated as entry (long-only system).
        API behavior: sell + short != entry.
        """
        from app.models import TradingViewAlert

        alert = TradingViewAlert(
            timestamp="2026-01-20T10:00:00Z",
            exchange="binance",
            symbol="BTCUSDT",
            timeframe="1h",
            action="sell",
            order_id="test_789",
            contracts=0.01,
            close=50000.0,
            position_side="short",
            position_qty=0.01,
        )

        assert alert.is_entry() is False

    def test_normalization_exchange_lowercase(self):
        """
        Bug prevented: Exchange case mismatch causes lookup failure.
        API behavior: Exchange normalized to lowercase.
        """
        from app.models import TradingViewAlert

        alert = TradingViewAlert(
            timestamp="2026-01-20T10:00:00Z",
            exchange="BINANCE",  # Uppercase
            symbol="BTCUSDT",
            timeframe="1h",
            action="buy",
            order_id="test_123",
            contracts=0.01,
            close=50000.0,
            position_side="long",
            position_qty=0.01,
        )

        assert alert.exchange == "binance"  # Normalized

    def test_normalization_symbol_uppercase(self):
        """
        Bug prevented: Symbol case mismatch causes lookup failure.
        API behavior: Symbol normalized to uppercase.
        """
        from app.models import TradingViewAlert

        alert = TradingViewAlert(
            timestamp="2026-01-20T10:00:00Z",
            exchange="binance",
            symbol="btcusdt",  # Lowercase
            timeframe="1h",
            action="buy",
            order_id="test_123",
            contracts=0.01,
            close=50000.0,
            position_side="long",
            position_qty=0.01,
        )

        assert alert.symbol == "BTCUSDT"  # Normalized


# =============================================================================
# APPLICATION ROUTES
# =============================================================================

class TestApplicationRoutes:
    """Tests for application route registration."""

    def test_all_expected_routes_registered(self, mock_dependencies):
        """
        Bug prevented: Route not registered, returns 404.
        API behavior: All expected routes are available.
        """
        from app.main import app

        route_paths = [route.path for route in app.routes]

        assert "/health" in route_paths
        assert "/webhook" in route_paths
        assert "/trades" in route_paths
        assert "/trades/{trade_id}" in route_paths
        assert "/reports/daily" in route_paths
        assert "/reports/send" in route_paths


# =============================================================================
# DATA MODELS
# =============================================================================

class TestDataModels:
    """Tests for data model validation."""

    def test_pyramid_entry_data_all_fields(self):
        """Test PyramidEntryData model creation."""
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
            received_timestamp=datetime.now(UTC),
            total_pyramids=1,
        )

        assert data.group_id == "BTC_Binance_1h_001"
        assert data.pyramid_index == 0
        assert data.entry_price == 50000.0

    def test_trade_closed_data_all_fields(self):
        """Test TradeClosedData model creation."""
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
            exit_time=datetime.now(UTC),
            exchange_timestamp="2026-01-20T12:00:00Z",
            received_timestamp=datetime.now(UTC),
            gross_pnl=20.0,
            total_fees=2.0,
            net_pnl=18.0,
            net_pnl_percent=1.8,
        )

        assert data.exit_price == 51000.0
        assert data.net_pnl == 18.0

    def test_daily_report_data_defaults(self):
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

    def test_chart_stats_all_fields(self):
        """Test ChartStats model with all fields."""
        from app.models import ChartStats

        stats = ChartStats(
            total_net_pnl=150.0,
            max_drawdown_percent=5.5,
            max_drawdown_usdt=100.0,
            trades_opened_today=5,
            trades_closed_today=3,
            win_rate=65.0,
            total_used_equity=10000.0,
            profit_factor=2.5,
            win_loss_ratio=1.8,
            cumulative_pnl=500.0,
        )

        assert stats.total_net_pnl == 150.0
        assert stats.win_rate == 65.0
        assert stats.profit_factor == 2.5
