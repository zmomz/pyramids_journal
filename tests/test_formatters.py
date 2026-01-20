"""
Tests for message formatters in app/bot/formatters.py
"""

from datetime import datetime
from unittest.mock import patch

import pytest
import pytz

from app.bot.formatters import (
    get_local_time,
    format_price,
    format_pnl,
    format_percent,
    format_status,
    format_live,
    format_stats,
    format_pnl_summary,
    format_best_worst,
    format_streak,
    format_drawdown,
    format_trades_list,
    format_fees,
    format_help,
)


class TestGetLocalTime:
    """Tests for get_local_time function."""

    def test_converts_utc_to_local(self):
        """Test that UTC time is converted to configured timezone."""
        utc_time = datetime(2026, 1, 20, 12, 0, 0, tzinfo=pytz.UTC)

        with patch("app.bot.formatters.settings") as mock_settings:
            mock_settings.timezone = "America/New_York"
            local_time = get_local_time(utc_time)

            # New York is UTC-5 in January
            assert local_time.hour == 7

    def test_handles_naive_datetime(self):
        """Test handling of naive datetime."""
        naive_time = datetime(2026, 1, 20, 12, 0, 0)

        with patch("app.bot.formatters.settings") as mock_settings:
            mock_settings.timezone = "UTC"
            local_time = get_local_time(naive_time)

            assert local_time.hour == 12

    def test_uses_current_time_when_none(self):
        """Test that current time is used when no time provided."""
        with patch("app.bot.formatters.settings") as mock_settings:
            mock_settings.timezone = "UTC"
            local_time = get_local_time(None)

            assert local_time is not None
            assert local_time.tzinfo is not None


class TestFormatPrice:
    """Tests for format_price function."""

    def test_large_price(self):
        """Test formatting large prices (>= 1000)."""
        assert format_price(50000.00) == "$50,000.00"
        assert format_price(1000.00) == "$1,000.00"
        assert format_price(12345.67) == "$12,345.67"

    def test_medium_price(self):
        """Test formatting medium prices (1-999)."""
        assert format_price(100.1234) == "$100.1234"
        assert format_price(1.0000) == "$1.0000"
        assert format_price(50.5555) == "$50.5555"

    def test_small_price(self):
        """Test formatting small prices (< 1)."""
        assert format_price(0.00001234) == "$0.00001234"
        assert format_price(0.50000000) == "$0.50000000"

    def test_zero_price(self):
        """Test formatting zero price."""
        assert format_price(0) == "$0.00000000"


class TestFormatPnl:
    """Tests for format_pnl function."""

    def test_positive_pnl(self):
        """Test formatting positive PnL."""
        assert format_pnl(100.50) == "+$100.50"
        assert format_pnl(0.00) == "+$0.00"

    def test_negative_pnl(self):
        """Test formatting negative PnL."""
        assert format_pnl(-50.25) == "$-50.25"
        assert format_pnl(-0.01) == "$-0.01"


class TestFormatPercent:
    """Tests for format_percent function."""

    def test_positive_percent(self):
        """Test formatting positive percentage."""
        assert format_percent(5.25) == "+5.25%"
        assert format_percent(0.00) == "+0.00%"

    def test_negative_percent(self):
        """Test formatting negative percentage."""
        assert format_percent(-3.50) == "-3.50%"


class TestFormatStatus:
    """Tests for format_status function."""

    def test_empty_trades(self):
        """Test formatting empty trades list."""
        result = format_status([], {})
        assert result == "📊 No open trades"

    def test_single_trade(self):
        """Test formatting single open trade."""
        trades = [{
            "base": "BTC",
            "quote": "USDT",
            "exchange": "binance",
            "pyramids": [
                {"position_size": 0.1, "entry_price": 50000.0},
            ]
        }]
        prices = {"binance:BTCUSDT": 51000.0}

        result = format_status(trades, prices)

        assert "BTC/USDT" in result
        assert "Binance" in result
        assert "Pyramids: 1" in result

    def test_multiple_pyramids(self):
        """Test formatting trade with multiple pyramids."""
        trades = [{
            "base": "ETH",
            "quote": "USDT",
            "exchange": "bybit",
            "pyramids": [
                {"position_size": 1.0, "entry_price": 3000.0},
                {"position_size": 1.0, "entry_price": 2900.0},
            ]
        }]
        prices = {"bybit:ETHUSDT": 3100.0}

        result = format_status(trades, prices)

        assert "ETH/USDT" in result
        assert "Pyramids: 2" in result
        # Avg entry: (3000 * 1 + 2900 * 1) / 2 = 2950
        assert "2,950" in result or "2950" in result


class TestFormatLive:
    """Tests for format_live function."""

    def test_empty_prices(self):
        """Test formatting empty prices dict."""
        result = format_live({})
        assert result == "📈 No open positions to track"

    def test_single_price_positive(self):
        """Test formatting single price with positive change."""
        prices = {
            "binance:BTCUSDT": {
                "pair": "BTC/USDT",
                "exchange": "binance",
                "price": 50000.0,
                "change": 2.5,
            }
        }

        result = format_live(prices)

        assert "📈 Live Prices" in result
        assert "🟢" in result  # Positive change
        assert "BTC/USDT" in result
        assert "+2.50%" in result

    def test_single_price_negative(self):
        """Test formatting single price with negative change."""
        prices = {
            "bybit:ETHUSDT": {
                "pair": "ETH/USDT",
                "exchange": "bybit",
                "price": 3000.0,
                "change": -5.0,
            }
        }

        result = format_live(prices)

        assert "🔴" in result  # Negative change
        assert "-5.00%" in result


class TestFormatStats:
    """Tests for format_stats function."""

    def test_all_time_stats(self):
        """Test formatting all-time statistics."""
        stats = {
            "total_trades": 100,
            "win_rate": 65.5,
            "total_pnl": 5000.0,
            "avg_win": 100.0,
            "avg_loss": -50.0,
            "best_trade": 500.0,
            "worst_trade": -200.0,
            "profit_factor": 2.5,
            "avg_trade": 50.0,
        }

        result = format_stats(stats)

        assert "📊 Statistics - All-Time" in result
        assert "Total Trades: 100" in result
        assert "Win Rate: 65.5%" in result
        assert "Profit Factor: 2.50" in result

    def test_period_label(self):
        """Test formatting stats with custom period label."""
        stats = {
            "total_trades": 10,
            "win_rate": 70.0,
            "total_pnl": 500.0,
            "period_label": "Today",
        }

        result = format_stats(stats)

        assert "📊 Statistics - Today" in result


class TestFormatPnlSummary:
    """Tests for format_pnl_summary function."""

    def test_positive_total(self):
        """Test formatting positive total PnL."""
        result = format_pnl_summary(realized=500.0, unrealized=100.0)

        assert "💰 PnL Summary" in result
        assert "Realized PnL: +$500.00" in result
        assert "Unrealized PnL: +$100.00" in result
        assert "🟢" in result  # Positive indicator
        assert "Net PnL: +$600.00" in result

    def test_negative_total(self):
        """Test formatting negative total PnL."""
        result = format_pnl_summary(realized=-200.0, unrealized=-50.0)

        assert "🔻" in result  # Negative indicator
        assert "Net PnL: $-250.00" in result


class TestFormatBestWorst:
    """Tests for format_best_worst function."""

    def test_best_pairs_empty(self):
        """Test formatting empty best pairs."""
        result = format_best_worst([], is_best=True)
        assert "🏆 No data available" in result

    def test_worst_pairs_empty(self):
        """Test formatting empty worst pairs."""
        result = format_best_worst([], is_best=False)
        assert "📉 No data available" in result

    def test_best_pairs_with_data(self):
        """Test formatting best pairs with data."""
        pairs = [
            {"pair": "BTC/USDT", "pnl": 500.0, "trades": 10},
            {"pair": "ETH/USDT", "pnl": 300.0, "trades": 8},
            {"pair": "SOL/USDT", "pnl": 200.0, "trades": 5},
        ]

        result = format_best_worst(pairs, is_best=True)

        assert "🏆 Best Pairs - All-Time" in result
        assert "🥇 BTC/USDT: +$500.00 (10 trades)" in result
        assert "🥈 ETH/USDT: +$300.00 (8 trades)" in result
        assert "🥉 SOL/USDT: +$200.00 (5 trades)" in result

    def test_worst_pairs_with_data(self):
        """Test formatting worst pairs with data."""
        pairs = [
            {"pair": "DOGE/USDT", "pnl": -150.0, "trades": 5},
        ]

        result = format_best_worst(pairs, is_best=False, period_label="Today")

        assert "📉 Worst Pairs - Today" in result
        assert "🥇 DOGE/USDT: $-150.00 (5 trades)" in result


class TestFormatStreak:
    """Tests for format_streak function."""

    def test_winning_streak(self):
        """Test formatting winning streak."""
        result = format_streak(current=5, longest_win=10, longest_loss=3)

        assert "📊 Streak Info - All-Time" in result
        assert "🔥 5 wins" in result
        assert "Longest Win Streak: 10" in result
        assert "Longest Loss Streak: 3" in result

    def test_losing_streak(self):
        """Test formatting losing streak."""
        result = format_streak(current=-3, longest_win=5, longest_loss=7)

        assert "❄️ 3 losses" in result

    def test_no_streak(self):
        """Test formatting no active streak."""
        result = format_streak(current=0, longest_win=5, longest_loss=5)

        assert "➖ No active streak" in result

    def test_with_period_label(self):
        """Test formatting streak with period label."""
        result = format_streak(current=2, longest_win=3, longest_loss=1, period_label="Week")

        assert "📊 Streak Info - Week" in result


class TestFormatDrawdown:
    """Tests for format_drawdown function."""

    def test_format_drawdown(self):
        """Test formatting drawdown information."""
        result = format_drawdown(
            max_dd=500.0,
            max_dd_percent=10.5,
            current_dd=200.0
        )

        assert "📉 Drawdown Info - All-Time" in result
        assert "Max Drawdown: $-500.00 (-10.50%)" in result
        assert "Current Drawdown: $-200.00" in result

    def test_with_period_label(self):
        """Test formatting drawdown with period label."""
        result = format_drawdown(
            max_dd=100.0,
            max_dd_percent=5.0,
            current_dd=50.0,
            period_label="Today"
        )

        assert "📉 Drawdown Info - Today" in result


class TestFormatTradesList:
    """Tests for format_trades_list function."""

    def test_empty_trades(self):
        """Test formatting empty trades list."""
        result = format_trades_list([])
        assert result == "📋 No trades found"

    def test_trades_with_data(self):
        """Test formatting trades list with data."""
        trades = [
            {
                "base": "BTC",
                "quote": "USDT",
                "exchange": "binance",
                "total_pnl_usdt": 100.0,
                "closed_at": "2026-01-20 10:00:00",
            },
            {
                "base": "ETH",
                "quote": "USDT",
                "exchange": "bybit",
                "total_pnl_usdt": -50.0,
                "closed_at": "2026-01-20 11:00:00",
            },
        ]

        result = format_trades_list(trades)

        assert "📋 Recent Trades (Page 1)" in result
        assert "🟢 BTC/USDT (Binance) | +$100.00 | 2026-01-20" in result
        assert "🔴 ETH/USDT (Bybit) | $-50.00 | 2026-01-20" in result

    def test_open_trade(self):
        """Test formatting list with open trade."""
        trades = [
            {
                "base": "LINK",
                "quote": "USDT",
                "exchange": "binance",
                "total_pnl_usdt": None,
                "closed_at": None,
            },
        ]

        result = format_trades_list(trades)

        assert "Open" in result


class TestFormatFees:
    """Tests for format_fees function."""

    def test_format_fees(self):
        """Test formatting exchange fees."""
        fees = {
            "binance": {"maker_fee": 0.1, "taker_fee": 0.1},
            "bybit": {"maker_fee": 0.075, "taker_fee": 0.075},
        }

        result = format_fees(fees)

        assert "💸 Exchange Fees" in result
        assert "Binance: Maker 0.1% | Taker 0.1%" in result
        assert "Bybit: Maker 0.075% | Taker 0.075%" in result


class TestFormatHelp:
    """Tests for format_help function."""

    def test_format_help(self):
        """Test formatting help message."""
        result = format_help()

        assert "📖 Available Commands" in result
        assert "/menu" in result
        assert "/status" in result
        assert "/report" in result
        assert "/stats" in result
        assert "/pnl" in result
        assert "/best" in result
        assert "/worst" in result
        assert "/drawdown" in result
        assert "/streak" in result
        assert "/trades" in result
        assert "/help" in result
        assert "Period options:" in result
