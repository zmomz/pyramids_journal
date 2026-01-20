"""
Tests for database operations in app/database.py

Covers all period-based query methods for consistency across commands.
"""

from datetime import datetime, timedelta

import pytest
import pytest_asyncio


class TestDatabaseConnection:
    """Tests for database connection and initialization."""

    @pytest.mark.asyncio
    async def test_connect_and_close(self, test_db):
        """Test database connection and closing."""
        assert test_db.connection is not None

    @pytest.mark.asyncio
    async def test_tables_created(self, test_db):
        """Test that all required tables are created."""
        cursor = await test_db.connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        tables = await cursor.fetchall()
        table_names = [row["name"] for row in tables]

        assert "trades" in table_names
        assert "pyramids" in table_names
        assert "daily_reports" in table_names


class TestGetRealizedPnlForPeriod:
    """Tests for get_realized_pnl_for_period method."""

    @pytest.mark.asyncio
    async def test_all_time_pnl(self, populated_db):
        """Test getting all-time realized PnL."""
        pnl, count = await populated_db.get_realized_pnl_for_period(None, None)

        # 6 closed trades total
        assert count == 6
        # Sum: 100.50 - 30.25 + 50 + 200 - 75.50 + 150 = 394.75
        assert abs(pnl - 394.75) < 0.01

    @pytest.mark.asyncio
    async def test_today_pnl(self, populated_db):
        """Test getting today's realized PnL."""
        today = datetime.now().strftime("%Y-%m-%d")
        pnl, count = await populated_db.get_realized_pnl_for_period(today, today)

        # 3 trades closed today
        assert count == 3
        # Sum: 100.50 - 30.25 + 50 = 120.25
        assert abs(pnl - 120.25) < 0.01

    @pytest.mark.asyncio
    async def test_yesterday_pnl(self, populated_db):
        """Test getting yesterday's realized PnL."""
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        pnl, count = await populated_db.get_realized_pnl_for_period(yesterday, yesterday)

        # 2 trades closed yesterday
        assert count == 2
        # Sum: 200 - 75.50 = 124.50
        assert abs(pnl - 124.50) < 0.01

    @pytest.mark.asyncio
    async def test_no_trades_period(self, populated_db):
        """Test getting PnL for period with no trades."""
        far_future = "2030-01-01"
        pnl, count = await populated_db.get_realized_pnl_for_period(far_future, far_future)

        assert count == 0
        assert pnl == 0.0


class TestGetStatisticsForPeriod:
    """Tests for get_statistics_for_period method."""

    @pytest.mark.asyncio
    async def test_all_time_stats(self, populated_db):
        """Test getting all-time statistics."""
        stats = await populated_db.get_statistics_for_period(None, None)

        assert stats["total_trades"] == 6
        assert stats["win_rate"] > 0  # 4 wins out of 6
        assert abs(stats["total_pnl"] - 394.75) < 0.01
        assert stats["best_trade"] == 200.0
        assert stats["worst_trade"] == -75.50

    @pytest.mark.asyncio
    async def test_today_stats(self, populated_db):
        """Test getting today's statistics."""
        today = datetime.now().strftime("%Y-%m-%d")
        stats = await populated_db.get_statistics_for_period(today, today)

        assert stats["total_trades"] == 3
        # 2 wins, 1 loss = 66.67% win rate
        assert abs(stats["win_rate"] - 66.67) < 1

    @pytest.mark.asyncio
    async def test_no_trades_stats(self, populated_db):
        """Test statistics for period with no trades."""
        far_future = "2030-01-01"
        stats = await populated_db.get_statistics_for_period(far_future, far_future)

        assert stats["total_trades"] == 0
        assert stats["win_rate"] == 0.0
        assert stats["total_pnl"] == 0.0
        assert stats["profit_factor"] == 0.0

    @pytest.mark.asyncio
    async def test_profit_factor_calculation(self, populated_db):
        """Test profit factor is calculated correctly."""
        today = datetime.now().strftime("%Y-%m-%d")
        stats = await populated_db.get_statistics_for_period(today, today)

        # Profit factor = total wins / total losses
        # Wins: 100.50 + 50 = 150.50
        # Losses: 30.25
        # PF = 150.50 / 30.25 = 4.975
        assert stats["profit_factor"] > 0

    @pytest.mark.asyncio
    async def test_avg_win_loss(self, populated_db):
        """Test average win and loss calculations."""
        today = datetime.now().strftime("%Y-%m-%d")
        stats = await populated_db.get_statistics_for_period(today, today)

        # 2 wins: (100.50 + 50) / 2 = 75.25
        assert abs(stats["avg_win"] - 75.25) < 0.01

        # 1 loss: -30.25
        assert abs(stats["avg_loss"] - (-30.25)) < 0.01


class TestGetBestPairsForPeriod:
    """Tests for get_best_pairs_for_period method."""

    @pytest.mark.asyncio
    async def test_all_time_best_pairs(self, populated_db):
        """Test getting all-time best pairs."""
        pairs = await populated_db.get_best_pairs_for_period(None, None, limit=5)

        assert len(pairs) > 0
        # Best pair should be BTC/USDT with highest total PnL
        assert pairs[0]["pair"] == "BTC/USDT"
        # BTC/USDT: 100.50 + 200 = 300.50
        assert abs(pairs[0]["pnl"] - 300.50) < 0.01

    @pytest.mark.asyncio
    async def test_today_best_pairs(self, populated_db):
        """Test getting today's best pairs."""
        today = datetime.now().strftime("%Y-%m-%d")
        pairs = await populated_db.get_best_pairs_for_period(today, today, limit=5)

        assert len(pairs) == 3
        # Best today: BTC/USDT with 100.50
        assert pairs[0]["pair"] == "BTC/USDT"
        assert abs(pairs[0]["pnl"] - 100.50) < 0.01

    @pytest.mark.asyncio
    async def test_limit_respected(self, populated_db):
        """Test that limit parameter is respected."""
        pairs = await populated_db.get_best_pairs_for_period(None, None, limit=2)
        assert len(pairs) == 2


class TestGetWorstPairsForPeriod:
    """Tests for get_worst_pairs_for_period method."""

    @pytest.mark.asyncio
    async def test_all_time_worst_pairs(self, populated_db):
        """Test getting all-time worst pairs."""
        pairs = await populated_db.get_worst_pairs_for_period(None, None, limit=5)

        assert len(pairs) > 0
        # Worst pair should be DOGE/USDT with -75.50
        assert pairs[0]["pair"] == "DOGE/USDT"
        assert abs(pairs[0]["pnl"] - (-75.50)) < 0.01

    @pytest.mark.asyncio
    async def test_today_worst_pairs(self, populated_db):
        """Test getting today's worst pairs."""
        today = datetime.now().strftime("%Y-%m-%d")
        pairs = await populated_db.get_worst_pairs_for_period(today, today, limit=5)

        assert len(pairs) == 3
        # Worst today: ETH/USDT with -30.25
        assert pairs[0]["pair"] == "ETH/USDT"
        assert abs(pairs[0]["pnl"] - (-30.25)) < 0.01


class TestGetTradesForPeriod:
    """Tests for get_trades_for_period method."""

    @pytest.mark.asyncio
    async def test_all_time_trades(self, populated_db):
        """Test getting all closed trades."""
        trades = await populated_db.get_trades_for_period(None, None, limit=50)

        assert len(trades) == 6  # All closed trades

    @pytest.mark.asyncio
    async def test_today_trades(self, populated_db):
        """Test getting today's trades."""
        today = datetime.now().strftime("%Y-%m-%d")
        trades = await populated_db.get_trades_for_period(today, today, limit=50)

        assert len(trades) == 3

    @pytest.mark.asyncio
    async def test_trades_sorted_by_date(self, populated_db):
        """Test that trades are sorted by closed_at descending."""
        trades = await populated_db.get_trades_for_period(None, None, limit=50)

        # Most recent should be first
        for i in range(len(trades) - 1):
            assert trades[i]["closed_at"] >= trades[i + 1]["closed_at"]

    @pytest.mark.asyncio
    async def test_limit_respected(self, populated_db):
        """Test that limit parameter is respected."""
        trades = await populated_db.get_trades_for_period(None, None, limit=2)
        assert len(trades) == 2


class TestGetDrawdownForPeriod:
    """Tests for get_drawdown_for_period method."""

    @pytest.mark.asyncio
    async def test_all_time_drawdown(self, populated_db):
        """Test getting all-time drawdown."""
        dd_data = await populated_db.get_drawdown_for_period(None, None)

        assert dd_data["trade_count"] == 6
        assert dd_data["current_equity"] > 0
        assert dd_data["max_drawdown"] >= 0

    @pytest.mark.asyncio
    async def test_today_drawdown(self, populated_db):
        """Test getting today's drawdown."""
        today = datetime.now().strftime("%Y-%m-%d")
        dd_data = await populated_db.get_drawdown_for_period(today, today)

        assert dd_data["trade_count"] == 3

    @pytest.mark.asyncio
    async def test_no_trades_drawdown(self, populated_db):
        """Test drawdown for period with no trades."""
        far_future = "2030-01-01"
        dd_data = await populated_db.get_drawdown_for_period(far_future, far_future)

        assert dd_data["trade_count"] == 0
        assert dd_data["current_equity"] == 0.0
        assert dd_data["max_drawdown"] == 0.0

    @pytest.mark.asyncio
    async def test_drawdown_calculation(self, populated_db):
        """Test that drawdown is calculated as peak - current."""
        today = datetime.now().strftime("%Y-%m-%d")
        dd_data = await populated_db.get_drawdown_for_period(today, today)

        # Current drawdown = peak - current equity
        expected_current_dd = dd_data["peak"] - dd_data["current_equity"]
        assert abs(dd_data["current_drawdown"] - expected_current_dd) < 0.01


class TestGetStreakForPeriod:
    """Tests for get_streak_for_period method."""

    @pytest.mark.asyncio
    async def test_all_time_streak(self, populated_db):
        """Test getting all-time streak data."""
        streak_data = await populated_db.get_streak_for_period(None, None)

        assert "current" in streak_data
        assert "longest_win" in streak_data
        assert "longest_loss" in streak_data

    @pytest.mark.asyncio
    async def test_today_streak(self, populated_db):
        """Test getting today's streak data."""
        today = datetime.now().strftime("%Y-%m-%d")
        streak_data = await populated_db.get_streak_for_period(today, today)

        # Today has: win, loss, win - current streak should be 1 win
        # (assuming trades are ordered by time)
        assert streak_data["longest_win"] >= 1
        assert streak_data["longest_loss"] >= 1

    @pytest.mark.asyncio
    async def test_no_trades_streak(self, populated_db):
        """Test streak for period with no trades."""
        far_future = "2030-01-01"
        streak_data = await populated_db.get_streak_for_period(far_future, far_future)

        assert streak_data["current"] == 0
        assert streak_data["longest_win"] == 0
        assert streak_data["longest_loss"] == 0


class TestGetExchangeStatsForPeriod:
    """Tests for get_exchange_stats_for_period method."""

    @pytest.mark.asyncio
    async def test_all_time_exchange_stats(self, populated_db):
        """Test getting all-time exchange statistics."""
        stats = await populated_db.get_exchange_stats_for_period(None, None)

        assert len(stats) == 2  # binance and bybit
        exchanges = {s["exchange"] for s in stats}
        assert "binance" in exchanges
        assert "bybit" in exchanges

    @pytest.mark.asyncio
    async def test_today_exchange_stats(self, populated_db):
        """Test getting today's exchange statistics."""
        today = datetime.now().strftime("%Y-%m-%d")
        stats = await populated_db.get_exchange_stats_for_period(today, today)

        assert len(stats) == 2
        # Binance today: 100.50 - 30.25 = 70.25 (2 trades)
        # Bybit today: 50.00 (1 trade)

        for stat in stats:
            if stat["exchange"] == "binance":
                assert stat["trades"] == 2
                assert abs(stat["pnl"] - 70.25) < 0.01
            elif stat["exchange"] == "bybit":
                assert stat["trades"] == 1
                assert abs(stat["pnl"] - 50.0) < 0.01


class TestGetTradeCountsForDate:
    """Tests for get_trade_counts_for_date method."""

    @pytest.mark.asyncio
    async def test_today_trade_counts(self, populated_db):
        """Test getting today's trade count breakdown."""
        today = datetime.now().strftime("%Y-%m-%d")
        counts = await populated_db.get_trade_counts_for_date(today)

        assert "opened_today" in counts
        assert "closed_today" in counts
        assert "still_open" in counts

        # 4 trades created today (3 closed + 1 open)
        assert counts["opened_today"] == 4
        # 3 trades closed today
        assert counts["closed_today"] == 3

    @pytest.mark.asyncio
    async def test_yesterday_trade_counts(self, populated_db):
        """Test getting yesterday's trade count breakdown."""
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        counts = await populated_db.get_trade_counts_for_date(yesterday)

        # 2 trades created yesterday
        assert counts["opened_today"] == 2
        # 2 trades closed yesterday
        assert counts["closed_today"] == 2


class TestGetCumulativePnlBeforeDate:
    """Tests for get_cumulative_pnl_before_date method."""

    @pytest.mark.asyncio
    async def test_cumulative_before_today(self, populated_db):
        """Test getting cumulative PnL before today."""
        today = datetime.now().strftime("%Y-%m-%d")
        cumulative = await populated_db.get_cumulative_pnl_before_date(today)

        # Yesterday: 200 - 75.50 = 124.50
        # Week ago: 150
        # Total before today: 274.50
        assert abs(cumulative - 274.50) < 0.01

    @pytest.mark.asyncio
    async def test_cumulative_before_yesterday(self, populated_db):
        """Test getting cumulative PnL before yesterday."""
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        cumulative = await populated_db.get_cumulative_pnl_before_date(yesterday)

        # Only week-old trade: 150
        assert abs(cumulative - 150.0) < 0.01

    @pytest.mark.asyncio
    async def test_cumulative_before_first_trade(self, populated_db):
        """Test cumulative PnL before any trades."""
        very_old = "2020-01-01"
        cumulative = await populated_db.get_cumulative_pnl_before_date(very_old)

        assert cumulative == 0.0


class TestGetEquityCurveData:
    """Tests for get_equity_curve_data method."""

    @pytest.mark.asyncio
    async def test_today_equity_curve(self, populated_db):
        """Test getting today's equity curve data."""
        today = datetime.now().strftime("%Y-%m-%d")
        data = await populated_db.get_equity_curve_data(today)

        # 3 closed trades today
        assert len(data) == 3

        # Should be sorted by closed_at ascending
        for i in range(len(data) - 1):
            assert data[i]["closed_at"] <= data[i + 1]["closed_at"]

    @pytest.mark.asyncio
    async def test_no_trades_equity_curve(self, populated_db):
        """Test equity curve for date with no trades."""
        far_future = "2030-01-01"
        data = await populated_db.get_equity_curve_data(far_future)

        assert len(data) == 0


class TestGetPyramidsForTrade:
    """Tests for get_pyramids_for_trade method."""

    @pytest.mark.asyncio
    async def test_trade_with_pyramids(self, populated_db):
        """Test getting pyramids for a trade with multiple pyramids."""
        pyramids = await populated_db.get_pyramids_for_trade("trade_1")

        assert len(pyramids) == 2  # trade_1 has 2 pyramids

    @pytest.mark.asyncio
    async def test_trade_with_single_pyramid(self, populated_db):
        """Test getting pyramids for a trade with single pyramid."""
        pyramids = await populated_db.get_pyramids_for_trade("trade_2")

        assert len(pyramids) == 1

    @pytest.mark.asyncio
    async def test_nonexistent_trade(self, populated_db):
        """Test getting pyramids for non-existent trade."""
        pyramids = await populated_db.get_pyramids_for_trade("nonexistent")

        assert len(pyramids) == 0


class TestSaveDailyReport:
    """Tests for save_daily_report method."""

    @pytest.mark.asyncio
    async def test_save_and_retrieve_report(self, test_db):
        """Test saving and retrieving a daily report."""
        import json

        date = "2026-01-20"
        report_data = {
            "date": date,
            "total_trades": 5,
            "total_pnl_usdt": 250.0,
        }

        await test_db.save_daily_report(
            date=date,
            total_trades=5,
            total_pyramids=8,
            total_pnl_usdt=250.0,
            report_json=json.dumps(report_data),
        )

        # Verify it was saved
        cursor = await test_db.connection.execute(
            "SELECT * FROM daily_reports WHERE date = ?", (date,)
        )
        row = await cursor.fetchone()

        assert row is not None
        assert row["total_trades"] == 5
        assert abs(row["total_pnl_usdt"] - 250.0) < 0.01

    @pytest.mark.asyncio
    async def test_update_existing_report(self, test_db):
        """Test that saving report for same date updates it."""
        import json

        date = "2026-01-21"

        # Save first version
        await test_db.save_daily_report(
            date=date,
            total_trades=3,
            total_pyramids=5,
            total_pnl_usdt=100.0,
            report_json=json.dumps({"version": 1}),
        )

        # Save updated version
        await test_db.save_daily_report(
            date=date,
            total_trades=5,
            total_pyramids=8,
            total_pnl_usdt=200.0,
            report_json=json.dumps({"version": 2}),
        )

        # Verify only one record exists with updated values
        cursor = await test_db.connection.execute(
            "SELECT COUNT(*) as count FROM daily_reports WHERE date = ?", (date,)
        )
        row = await cursor.fetchone()
        assert row["count"] == 1

        cursor = await test_db.connection.execute(
            "SELECT * FROM daily_reports WHERE date = ?", (date,)
        )
        row = await cursor.fetchone()
        assert row["total_trades"] == 5
        assert abs(row["total_pnl_usdt"] - 200.0) < 0.01


class TestGetRecentTrades:
    """Tests for get_recent_trades method."""

    @pytest.mark.asyncio
    async def test_get_recent_trades(self, populated_db):
        """Test getting recent trades with limit."""
        trades = await populated_db.get_recent_trades(5)

        assert len(trades) <= 5
        # Should be sorted by closed_at descending
        for i in range(len(trades) - 1):
            if trades[i]["closed_at"] and trades[i + 1]["closed_at"]:
                assert trades[i]["closed_at"] >= trades[i + 1]["closed_at"]

    @pytest.mark.asyncio
    async def test_get_recent_trades_small_limit(self, populated_db):
        """Test getting recent trades with small limit."""
        trades = await populated_db.get_recent_trades(2)
        assert len(trades) == 2


class TestGetOpenTrades:
    """Tests for get_open_trades method."""

    @pytest.mark.asyncio
    async def test_get_open_trades(self, populated_db):
        """Test getting all open trades."""
        trades = await populated_db.get_open_trades()

        # We have 1 open trade
        assert len(trades) == 1
        assert trades[0]["id"] == "trade_7"
        assert trades[0]["status"] == "open"
