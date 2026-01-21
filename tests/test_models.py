"""
Tests for Pydantic models in app/models.py
"""

from datetime import datetime

import pytest
from pydantic import ValidationError

from app.models import (
    TradingViewAlert,
    PyramidEntryData,
    SymbolRules,
    PyramidRecord,
    TradeRecord,
    WebhookResponse,
    TradeClosedData,
    TradeHistoryItem,
    EquityPoint,
    ChartStats,
    DailyReportData,
    ValidationError as AppValidationError,
)


class TestTradingViewAlert:
    """Tests for TradingViewAlert model."""

    def test_valid_buy_alert(self):
        """Test creating a valid buy alert."""
        alert = TradingViewAlert(
            timestamp="2026-01-20T10:00:00",
            exchange="BINANCE",
            symbol="btcusdt",
            timeframe="1H",
            action="buy",
            order_id="order_123",
            contracts=0.1,
            close=50000.0,
            position_side="long",
            position_qty=0.1,
        )

        assert alert.exchange == "binance"  # Normalized to lowercase
        assert alert.symbol == "BTCUSDT"  # Normalized to uppercase
        assert alert.timeframe == "1h"  # Normalized to lowercase
        assert alert.action == "buy"
        assert alert.is_entry() is True
        assert alert.is_exit() is False

    def test_valid_sell_alert(self):
        """Test creating a valid sell alert."""
        alert = TradingViewAlert(
            timestamp="2026-01-20T11:00:00",
            exchange="bybit",
            symbol="ETHUSDT",
            timeframe="4h",
            action="sell",
            order_id="order_456",
            contracts=0.5,
            close=3000.0,
            position_side="flat",
            position_qty=0.0,
        )

        assert alert.is_entry() is False
        assert alert.is_exit() is True

    def test_invalid_action(self):
        """Test that invalid action raises validation error."""
        with pytest.raises(ValidationError):
            TradingViewAlert(
                timestamp="2026-01-20T10:00:00",
                exchange="binance",
                symbol="BTCUSDT",
                timeframe="1h",
                action="invalid",  # Invalid action
                order_id="order_123",
                contracts=0.1,
                close=50000.0,
                position_side="long",
                position_qty=0.1,
            )

    def test_invalid_position_side(self):
        """Test that invalid position_side raises validation error."""
        with pytest.raises(ValidationError):
            TradingViewAlert(
                timestamp="2026-01-20T10:00:00",
                exchange="binance",
                symbol="BTCUSDT",
                timeframe="1h",
                action="buy",
                order_id="order_123",
                contracts=0.1,
                close=50000.0,
                position_side="invalid",  # Invalid position side
                position_qty=0.1,
            )

    def test_negative_contracts(self):
        """Test that negative contracts raises validation error."""
        with pytest.raises(ValidationError):
            TradingViewAlert(
                timestamp="2026-01-20T10:00:00",
                exchange="binance",
                symbol="BTCUSDT",
                timeframe="1h",
                action="buy",
                order_id="order_123",
                contracts=-0.1,  # Negative contracts
                close=50000.0,
                position_side="long",
                position_qty=0.1,
            )

    def test_zero_close_price(self):
        """Test that zero close price raises validation error."""
        with pytest.raises(ValidationError):
            TradingViewAlert(
                timestamp="2026-01-20T10:00:00",
                exchange="binance",
                symbol="BTCUSDT",
                timeframe="1h",
                action="buy",
                order_id="order_123",
                contracts=0.1,
                close=0.0,  # Zero close price
                position_side="long",
                position_qty=0.1,
            )

    def test_empty_exchange(self):
        """Test that empty exchange raises validation error."""
        with pytest.raises(ValidationError):
            TradingViewAlert(
                timestamp="2026-01-20T10:00:00",
                exchange="",  # Empty exchange
                symbol="BTCUSDT",
                timeframe="1h",
                action="buy",
                order_id="order_123",
                contracts=0.1,
                close=50000.0,
                position_side="long",
                position_qty=0.1,
            )

    def test_exchange_normalization(self):
        """Test exchange name normalization."""
        alert = TradingViewAlert(
            timestamp="2026-01-20T10:00:00",
            exchange="  BINANCE  ",
            symbol="BTCUSDT",
            timeframe="1h",
            action="buy",
            order_id="order_123",
            contracts=0.1,
            close=50000.0,
            position_side="long",
            position_qty=0.1,
        )

        assert alert.exchange == "binance"

    def test_symbol_normalization(self):
        """Test symbol normalization."""
        alert = TradingViewAlert(
            timestamp="2026-01-20T10:00:00",
            exchange="binance",
            symbol="  btcusdt  ",
            timeframe="1h",
            action="buy",
            order_id="order_123",
            contracts=0.1,
            close=50000.0,
            position_side="long",
            position_qty=0.1,
        )

        assert alert.symbol == "BTCUSDT"


class TestPyramidEntryData:
    """Tests for PyramidEntryData model."""

    def test_valid_pyramid_entry(self):
        """Test creating valid pyramid entry data."""
        entry = PyramidEntryData(
            group_id="group_123",
            pyramid_index=1,
            exchange="binance",
            base="BTC",
            quote="USDT",
            timeframe="1h",
            entry_price=50000.0,
            position_size=0.1,
            capital_usdt=5000.0,
            exchange_timestamp="2026-01-20T10:00:00",
            received_timestamp=datetime.now(),
            total_pyramids=3,
        )

        assert entry.group_id == "group_123"
        assert entry.pyramid_index == 1
        assert entry.capital_usdt == 5000.0


class TestSymbolRules:
    """Tests for SymbolRules model."""

    def test_default_values(self):
        """Test default values for symbol rules."""
        rules = SymbolRules(
            exchange="binance",
            base="BTC",
            quote="USDT",
        )

        assert rules.price_precision == 8
        assert rules.qty_precision == 8
        assert rules.min_qty == 0.0
        assert rules.min_notional == 0.0
        assert rules.tick_size == 0.00000001

    def test_custom_values(self):
        """Test custom values for symbol rules."""
        rules = SymbolRules(
            exchange="binance",
            base="BTC",
            quote="USDT",
            price_precision=2,
            qty_precision=6,
            min_qty=0.001,
            min_notional=10.0,
            tick_size=0.01,
        )

        assert rules.price_precision == 2
        assert rules.min_notional == 10.0


class TestPyramidRecord:
    """Tests for PyramidRecord model."""

    def test_valid_pyramid_record(self):
        """Test creating valid pyramid record."""
        record = PyramidRecord(
            id="pyr_123",
            trade_id="trade_123",
            pyramid_index=1,
            entry_price=50000.0,
            position_size=0.1,
            capital_usdt=5000.0,
            entry_time=datetime.now(),
            fee_rate=0.001,
            fee_usdt=5.0,
            pnl_usdt=100.0,
            pnl_percent=2.0,
        )

        assert record.pnl_usdt == 100.0
        assert record.pnl_percent == 2.0

    def test_optional_pnl_fields(self):
        """Test that PnL fields are optional."""
        record = PyramidRecord(
            id="pyr_123",
            trade_id="trade_123",
            pyramid_index=1,
            entry_price=50000.0,
            position_size=0.1,
            capital_usdt=5000.0,
            entry_time=datetime.now(),
            fee_rate=0.001,
            fee_usdt=5.0,
        )

        assert record.pnl_usdt is None
        assert record.pnl_percent is None


class TestTradeRecord:
    """Tests for TradeRecord model."""

    def test_open_trade(self):
        """Test creating an open trade record."""
        record = TradeRecord(
            id="trade_123",
            exchange="binance",
            base="BTC",
            quote="USDT",
            status="open",
            created_at=datetime.now(),
        )

        assert record.status == "open"
        assert record.closed_at is None
        assert record.total_pnl_usdt is None
        assert record.pyramids == []

    def test_closed_trade(self):
        """Test creating a closed trade record."""
        record = TradeRecord(
            id="trade_123",
            exchange="binance",
            base="BTC",
            quote="USDT",
            status="closed",
            created_at=datetime.now(),
            closed_at=datetime.now(),
            total_pnl_usdt=500.0,
            total_pnl_percent=10.0,
        )

        assert record.status == "closed"
        assert record.total_pnl_usdt == 500.0


class TestWebhookResponse:
    """Tests for WebhookResponse model."""

    def test_success_response(self):
        """Test successful webhook response."""
        response = WebhookResponse(
            success=True,
            message="Trade executed successfully",
            trade_id="trade_123",
            price=50000.0,
        )

        assert response.success is True
        assert response.error is None

    def test_error_response(self):
        """Test error webhook response."""
        response = WebhookResponse(
            success=False,
            message="Trade failed",
            error="Invalid symbol",
        )

        assert response.success is False
        assert response.error == "Invalid symbol"


class TestTradeClosedData:
    """Tests for TradeClosedData model."""

    def test_valid_trade_closed_data(self):
        """Test creating valid trade closed data."""
        data = TradeClosedData(
            trade_id="trade_123",
            group_id="group_123",
            exchange="binance",
            base="BTC",
            quote="USDT",
            timeframe="1h",
            pyramids=[{"id": "pyr_1", "pnl": 50.0}],
            exit_price=51000.0,
            exit_time=datetime.now(),
            gross_pnl=1000.0,
            total_fees=10.0,
            net_pnl=990.0,
            net_pnl_percent=19.8,
            exchange_timestamp="2026-01-20T11:00:00",
            received_timestamp=datetime.now(),
        )

        assert data.net_pnl == 990.0


class TestTradeHistoryItem:
    """Tests for TradeHistoryItem model."""

    def test_valid_trade_history_item(self):
        """Test creating valid trade history item."""
        item = TradeHistoryItem(
            group_id="group_123",
            exchange="binance",
            pair="BTC/USDT",
            timeframe="1h",
            pyramids_count=2,
            pnl_usdt=100.0,
            pnl_percent=5.0,
        )

        assert item.pair == "BTC/USDT"
        assert item.pyramids_count == 2


class TestEquityPoint:
    """Tests for EquityPoint model."""

    def test_valid_equity_point(self):
        """Test creating valid equity point."""
        point = EquityPoint(
            timestamp=datetime.now(),
            cumulative_pnl=500.0,
        )

        assert point.cumulative_pnl == 500.0


class TestChartStats:
    """Tests for ChartStats model."""

    def test_default_values(self):
        """Test default values for chart stats."""
        stats = ChartStats()

        assert stats.total_net_pnl == 0.0
        assert stats.max_drawdown_percent == 0.0
        assert stats.trades_opened_today == 0
        assert stats.trades_closed_today == 0
        assert stats.win_rate == 0.0

    def test_custom_values(self):
        """Test custom values for chart stats."""
        stats = ChartStats(
            total_net_pnl=500.0,
            max_drawdown_percent=10.5,
            max_drawdown_usdt=50.0,
            trades_opened_today=5,
            trades_closed_today=4,
            win_rate=75.0,
            total_used_equity=10000.0,
            profit_factor=2.5,
            win_loss_ratio=1.8,
            cumulative_pnl=1500.0,
        )

        assert stats.total_net_pnl == 500.0
        assert stats.trades_opened_today == 5


class TestDailyReportData:
    """Tests for DailyReportData model."""

    def test_empty_report(self):
        """Test creating empty daily report."""
        report = DailyReportData(
            date="2026-01-20",
            total_trades=0,
            total_pyramids=0,
            total_pnl_usdt=0.0,
            total_pnl_percent=0.0,
            trades=[],
            by_exchange={},
            by_timeframe={},
            by_pair={},
        )

        assert report.total_trades == 0
        assert report.equity_points == []
        assert report.chart_stats is None

    def test_full_report(self):
        """Test creating full daily report."""
        trade = TradeHistoryItem(
            group_id="group_1",
            exchange="binance",
            pair="BTC/USDT",
            timeframe="1h",
            pyramids_count=2,
            pnl_usdt=100.0,
            pnl_percent=5.0,
        )

        equity_point = EquityPoint(
            timestamp=datetime.now(),
            cumulative_pnl=100.0,
        )

        chart_stats = ChartStats(total_net_pnl=100.0)

        report = DailyReportData(
            date="2026-01-20",
            total_trades=1,
            total_pyramids=2,
            total_pnl_usdt=100.0,
            total_pnl_percent=5.0,
            trades=[trade],
            by_exchange={"binance": {"pnl": 100.0, "trades": 1}},
            by_timeframe={"1h": {"pnl": 100.0, "trades": 1}},
            by_pair={"BTC/USDT": 100.0},
            equity_points=[equity_point],
            chart_stats=chart_stats,
        )

        assert report.total_trades == 1
        assert len(report.trades) == 1
        assert len(report.equity_points) == 1
        assert report.chart_stats is not None


class TestAppValidationError:
    """Tests for custom ValidationError model."""

    def test_validation_error(self):
        """Test creating validation error."""
        error = AppValidationError(
            field="symbol",
            message="Symbol is required",
            value=None,
        )

        assert error.field == "symbol"
        assert error.message == "Symbol is required"

    def test_validation_error_with_value(self):
        """Test validation error with value."""
        error = AppValidationError(
            field="price",
            message="Price must be positive",
            value=-100.0,
        )

        assert error.value == -100.0
