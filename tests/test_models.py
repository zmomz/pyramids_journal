"""
Tests for Pydantic models in app/models.py

Critical tests here:
1. TradingViewAlert.is_entry() and is_exit() - determines trade flow
2. Field validation - prevents invalid data from entering the system
3. Normalization - ensures consistent data format

Bug categories prevented:
- Entry signal treated as exit (or vice versa)
- Invalid data accepted and causing downstream errors
- Inconsistent casing causing lookup failures
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


class TestTradingViewAlertEntryExit:
    """
    Critical tests for entry/exit signal classification.

    Bug prevented: Entry signal treated as exit, causing:
    - Trade closed when it should have added a pyramid
    - Trade opened when it should have closed

    This is the most critical business logic in the webhook flow.
    """

    @pytest.mark.parametrize(
        "action,position_side,is_entry,is_exit,description",
        [
            # Clear entry signals
            ("buy", "long", True, False, "Buy + long = entry"),
            # Clear exit signals
            ("sell", "flat", False, True, "Sell + flat = exit"),
            # Ambiguous signals (neither entry nor exit)
            ("buy", "flat", False, False, "Buy + flat = ambiguous"),
            ("buy", "short", False, False, "Buy + short = ambiguous (shorts not supported)"),
            ("sell", "long", False, False, "Sell + long = ambiguous (partial exit?)"),
            ("sell", "short", False, False, "Sell + short = ambiguous"),
        ],
        ids=[
            "entry-buy-long",
            "exit-sell-flat",
            "ambiguous-buy-flat",
            "ambiguous-buy-short",
            "ambiguous-sell-long",
            "ambiguous-sell-short",
        ],
    )
    def test_signal_classification(
        self, action, position_side, is_entry, is_exit, description
    ):
        """
        Verify signal classification based on action and position_side.

        The system is LONG-ONLY:
        - Entry: action=buy AND position_side=long
        - Exit: action=sell AND position_side=flat
        - All other combinations are ignored
        """
        alert = TradingViewAlert(
            timestamp="2026-01-20T10:00:00",
            exchange="binance",
            symbol="BTCUSDT",
            timeframe="1h",
            action=action,
            order_id="test_order",
            contracts=0.1,
            close=50000.0,
            position_side=position_side,
            position_qty=0.1 if position_side != "flat" else 0.0,
        )

        assert alert.is_entry() == is_entry, f"is_entry() failed for: {description}"
        assert alert.is_exit() == is_exit, f"is_exit() failed for: {description}"

    def test_entry_and_exit_are_mutually_exclusive(self):
        """
        Verify a signal cannot be both entry AND exit.

        Bug prevented: Signal processed twice (as entry and exit).
        """
        # Test all possible combinations
        for action in ["buy", "sell"]:
            for position_side in ["long", "short", "flat"]:
                alert = TradingViewAlert(
                    timestamp="2026-01-20T10:00:00",
                    exchange="binance",
                    symbol="BTCUSDT",
                    timeframe="1h",
                    action=action,
                    order_id="test",
                    contracts=0.1,
                    close=50000.0,
                    position_side=position_side,
                    position_qty=0.1,
                )

                # Cannot be both entry and exit
                assert not (
                    alert.is_entry() and alert.is_exit()
                ), f"Signal is both entry AND exit: action={action}, position_side={position_side}"


class TestTradingViewAlertValidation:
    """
    Tests for field validation in TradingViewAlert.

    Bug prevented: Invalid webhook data accepted, causing crashes
    or incorrect trades downstream.
    """

    def test_valid_alert_all_fields(self):
        """Verify valid alert with all fields passes validation."""
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

        # Verify normalization
        assert alert.exchange == "binance"  # lowercase
        assert alert.symbol == "BTCUSDT"  # uppercase
        assert alert.timeframe == "1h"  # lowercase

    @pytest.mark.parametrize(
        "field,value,expected_error",
        [
            ("action", "invalid", "action"),
            ("action", "BUY", "action"),  # Must be lowercase
            ("action", "", "action"),
            ("position_side", "invalid", "position_side"),
            ("position_side", "LONG", "position_side"),  # Must be lowercase
        ],
        ids=[
            "invalid-action",
            "uppercase-action",
            "empty-action",
            "invalid-position-side",
            "uppercase-position-side",
        ],
    )
    def test_literal_field_validation(self, field, value, expected_error):
        """Verify Literal fields reject invalid values."""
        kwargs = {
            "timestamp": "2026-01-20T10:00:00",
            "exchange": "binance",
            "symbol": "BTCUSDT",
            "timeframe": "1h",
            "action": "buy",
            "order_id": "test",
            "contracts": 0.1,
            "close": 50000.0,
            "position_side": "long",
            "position_qty": 0.1,
        }
        kwargs[field] = value

        with pytest.raises(ValidationError) as exc_info:
            TradingViewAlert(**kwargs)

        # Verify error is about the expected field
        errors = exc_info.value.errors()
        assert any(expected_error in str(e.get("loc", "")) for e in errors)

    @pytest.mark.parametrize(
        "field,value",
        [
            ("contracts", -0.1),  # Negative
            ("close", 0.0),  # Zero (gt=0)
            ("close", -100.0),  # Negative
            ("position_qty", -1.0),  # Negative
        ],
        ids=["negative-contracts", "zero-close", "negative-close", "negative-position-qty"],
    )
    def test_numeric_field_constraints(self, field, value):
        """Verify numeric field constraints are enforced."""
        kwargs = {
            "timestamp": "2026-01-20T10:00:00",
            "exchange": "binance",
            "symbol": "BTCUSDT",
            "timeframe": "1h",
            "action": "buy",
            "order_id": "test",
            "contracts": 0.1,
            "close": 50000.0,
            "position_side": "long",
            "position_qty": 0.1,
        }
        kwargs[field] = value

        with pytest.raises(ValidationError):
            TradingViewAlert(**kwargs)

    @pytest.mark.parametrize(
        "field",
        ["exchange", "symbol", "timeframe", "order_id"],
    )
    def test_min_length_validation(self, field):
        """Verify min_length=1 is enforced on string fields."""
        kwargs = {
            "timestamp": "2026-01-20T10:00:00",
            "exchange": "binance",
            "symbol": "BTCUSDT",
            "timeframe": "1h",
            "action": "buy",
            "order_id": "test",
            "contracts": 0.1,
            "close": 50000.0,
            "position_side": "long",
            "position_qty": 0.1,
        }
        kwargs[field] = ""

        with pytest.raises(ValidationError):
            TradingViewAlert(**kwargs)


class TestTradingViewAlertNormalization:
    """
    Tests for field normalization in TradingViewAlert.

    Bug prevented: Case-sensitive lookups failing due to inconsistent casing.
    """

    @pytest.mark.parametrize(
        "exchange_input,expected",
        [
            ("BINANCE", "binance"),
            ("Binance", "binance"),
            ("binance", "binance"),
            ("  binance  ", "binance"),
            ("BYBIT", "bybit"),
        ],
    )
    def test_exchange_normalized_to_lowercase(self, exchange_input, expected):
        """Verify exchange is normalized to lowercase with trimmed whitespace."""
        alert = TradingViewAlert(
            timestamp="2026-01-20T10:00:00",
            exchange=exchange_input,
            symbol="BTCUSDT",
            timeframe="1h",
            action="buy",
            order_id="test",
            contracts=0.1,
            close=50000.0,
            position_side="long",
            position_qty=0.1,
        )

        assert alert.exchange == expected

    @pytest.mark.parametrize(
        "symbol_input,expected",
        [
            ("btcusdt", "BTCUSDT"),
            ("BtcUsdt", "BTCUSDT"),
            ("BTCUSDT", "BTCUSDT"),
            ("  btcusdt  ", "BTCUSDT"),
        ],
    )
    def test_symbol_normalized_to_uppercase(self, symbol_input, expected):
        """Verify symbol is normalized to uppercase with trimmed whitespace."""
        alert = TradingViewAlert(
            timestamp="2026-01-20T10:00:00",
            exchange="binance",
            symbol=symbol_input,
            timeframe="1h",
            action="buy",
            order_id="test",
            contracts=0.1,
            close=50000.0,
            position_side="long",
            position_qty=0.1,
        )

        assert alert.symbol == expected

    @pytest.mark.parametrize(
        "timeframe_input,expected",
        [
            ("1H", "1h"),
            ("4H", "4h"),
            ("1D", "1d"),
            ("15M", "15m"),
            ("  1h  ", "1h"),
        ],
    )
    def test_timeframe_normalized_to_lowercase(self, timeframe_input, expected):
        """Verify timeframe is normalized to lowercase with trimmed whitespace."""
        alert = TradingViewAlert(
            timestamp="2026-01-20T10:00:00",
            exchange="binance",
            symbol="BTCUSDT",
            timeframe=timeframe_input,
            action="buy",
            order_id="test",
            contracts=0.1,
            close=50000.0,
            position_side="long",
            position_qty=0.1,
        )

        assert alert.timeframe == expected


class TestSymbolRules:
    """Tests for SymbolRules model defaults and custom values."""

    def test_default_values(self):
        """Verify defaults are set for optional fields."""
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

    def test_custom_values_override_defaults(self):
        """Verify custom values override defaults."""
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
        assert rules.qty_precision == 6
        assert rules.min_qty == 0.001
        assert rules.min_notional == 10.0
        assert rules.tick_size == 0.01


class TestPyramidRecord:
    """Tests for PyramidRecord model."""

    def test_pnl_fields_optional_before_exit(self):
        """
        Verify PnL fields are optional (None before trade is closed).

        Bug prevented: Validation error when creating pyramid before exit.
        """
        record = PyramidRecord(
            id="pyr_123",
            trade_id="trade_123",
            pyramid_index=0,
            entry_price=50000.0,
            position_size=0.1,
            capital_usdt=5000.0,
            entry_time=datetime.now(),
            fee_rate=0.001,
            fee_usdt=5.0,
        )

        assert record.pnl_usdt is None
        assert record.pnl_percent is None

    def test_pnl_fields_populated_after_exit(self):
        """Verify PnL fields can be set after trade exit."""
        record = PyramidRecord(
            id="pyr_123",
            trade_id="trade_123",
            pyramid_index=0,
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


class TestTradeRecord:
    """Tests for TradeRecord model."""

    def test_open_trade_has_none_closed_fields(self):
        """Verify open trade has None for closed_at and PnL."""
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
        assert record.total_pnl_percent is None
        assert record.pyramids == []

    def test_closed_trade_has_pnl(self):
        """Verify closed trade has PnL fields populated."""
        now = datetime.now()
        record = TradeRecord(
            id="trade_123",
            exchange="binance",
            base="BTC",
            quote="USDT",
            status="closed",
            created_at=now,
            closed_at=now,
            total_pnl_usdt=500.0,
            total_pnl_percent=10.0,
        )

        assert record.status == "closed"
        assert record.closed_at is not None
        assert record.total_pnl_usdt == 500.0
        assert record.total_pnl_percent == 10.0


class TestWebhookResponse:
    """Tests for WebhookResponse model."""

    def test_success_response(self):
        """Verify success response structure."""
        response = WebhookResponse(
            success=True,
            message="Trade executed successfully",
            trade_id="trade_123",
            price=50000.0,
        )

        assert response.success is True
        assert response.error is None
        assert response.trade_id == "trade_123"

    def test_error_response(self):
        """Verify error response structure."""
        response = WebhookResponse(
            success=False,
            message="Trade failed",
            error="INVALID_SYMBOL",
        )

        assert response.success is False
        assert response.error == "INVALID_SYMBOL"
        assert response.trade_id is None


class TestChartStats:
    """Tests for ChartStats model."""

    def test_all_fields_default_to_zero(self):
        """Verify all numeric fields default to 0."""
        stats = ChartStats()

        assert stats.total_net_pnl == 0.0
        assert stats.max_drawdown_percent == 0.0
        assert stats.max_drawdown_usdt == 0.0
        assert stats.trades_opened_today == 0
        assert stats.trades_closed_today == 0
        assert stats.win_rate == 0.0
        assert stats.total_used_equity == 0.0
        assert stats.profit_factor == 0.0
        assert stats.win_loss_ratio == 0.0
        assert stats.cumulative_pnl == 0.0


class TestDailyReportData:
    """Tests for DailyReportData model."""

    def test_empty_report_defaults(self):
        """Verify empty report has sensible defaults."""
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

        assert report.equity_points == []
        assert report.chart_stats is None

    def test_report_with_all_data(self):
        """Verify report can hold all data types."""
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

        chart_stats = ChartStats(total_net_pnl=100.0, win_rate=75.0)

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

        assert len(report.trades) == 1
        assert len(report.equity_points) == 1
        assert report.chart_stats.win_rate == 75.0


class TestAppValidationError:
    """Tests for custom ValidationError model."""

    def test_error_captures_context(self):
        """Verify error captures field, message, and value."""
        error = AppValidationError(
            field="price",
            message="Price must be positive",
            value=-100.0,
        )

        assert error.field == "price"
        assert error.message == "Price must be positive"
        assert error.value == -100.0

    def test_value_is_optional(self):
        """Verify value field is optional."""
        error = AppValidationError(
            field="symbol",
            message="Symbol is required",
        )

        assert error.value is None
