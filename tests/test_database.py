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


class TestGetOpenTrade:
    """Tests for get_open_trade method."""

    @pytest.mark.asyncio
    async def test_get_open_trade(self, populated_db):
        """Test getting an open trade for specific exchange/symbol."""
        # trade_7 is open: exchange=binance, base=LINK, quote=USDT
        trade = await populated_db.get_open_trade("binance", "LINK", "USDT")

        assert trade is not None
        assert trade["id"] == "trade_7"
        assert trade["status"] == "open"

    @pytest.mark.asyncio
    async def test_get_open_trade_not_found(self, populated_db):
        """Test getting open trade when none exists for symbol."""
        # BTC/USDT is closed, not open
        trade = await populated_db.get_open_trade("binance", "BTC", "USDT")

        # Should return None since BTC/USDT trade is closed
        assert trade is None

    @pytest.mark.asyncio
    async def test_get_open_trade_wrong_exchange(self, populated_db):
        """Test getting open trade with wrong exchange."""
        # LINK trade is on binance, not bybit
        trade = await populated_db.get_open_trade("bybit", "LINK", "USDT")

        assert trade is None


class TestAlertIdempotency:
    """Tests for alert idempotency methods."""

    @pytest.mark.asyncio
    async def test_is_alert_processed_false(self, test_db):
        """Test that new alert is not processed."""
        is_processed = await test_db.is_alert_processed("new_alert_id")
        assert is_processed is False

    @pytest.mark.asyncio
    async def test_mark_alert_processed(self, test_db):
        """Test marking an alert as processed."""
        await test_db.mark_alert_processed("test_alert_1")

        is_processed = await test_db.is_alert_processed("test_alert_1")
        assert is_processed is True

    @pytest.mark.asyncio
    async def test_mark_alert_processed_idempotent(self, test_db):
        """Test that marking same alert twice doesn't cause error."""
        await test_db.mark_alert_processed("test_alert_2")
        await test_db.mark_alert_processed("test_alert_2")  # Should not raise

        is_processed = await test_db.is_alert_processed("test_alert_2")
        assert is_processed is True


class TestCreateTrade:
    """Tests for create_trade method."""

    @pytest.mark.asyncio
    async def test_create_trade(self, test_db):
        """Test creating a new trade."""
        await test_db.create_trade("new_trade_1", "binance", "BTC", "USDT")

        trade = await test_db.get_open_trade("binance", "BTC", "USDT")
        assert trade is not None
        assert trade["id"] == "new_trade_1"
        assert trade["exchange"] == "binance"
        assert trade["base"] == "BTC"
        assert trade["quote"] == "USDT"
        assert trade["status"] == "open"


class TestCloseTrade:
    """Tests for close_trade method."""

    @pytest.mark.asyncio
    async def test_close_trade(self, test_db):
        """Test closing a trade."""
        # First create a trade
        await test_db.create_trade("trade_to_close", "binance", "ETH", "USDT")

        # Close it
        await test_db.close_trade("trade_to_close", 100.50, 5.25)

        # Verify it's closed
        trade = await test_db.get_open_trade("binance", "ETH", "USDT")
        assert trade is None  # Should not find open trade

        # Verify in database
        cursor = await test_db.connection.execute(
            "SELECT * FROM trades WHERE id = ?", ("trade_to_close",)
        )
        row = await cursor.fetchone()
        assert row["status"] == "closed"
        assert abs(row["total_pnl_usdt"] - 100.50) < 0.01
        assert abs(row["total_pnl_percent"] - 5.25) < 0.01


class TestGetTradeWithPyramids:
    """Tests for get_trade_with_pyramids method."""

    @pytest.mark.asyncio
    async def test_get_trade_with_pyramids(self, populated_db):
        """Test getting a trade with its pyramids."""
        result = await populated_db.get_trade_with_pyramids("trade_1")

        assert result is not None
        assert "trade" in result
        assert "pyramids" in result
        assert "exit" in result
        assert result["trade"]["id"] == "trade_1"
        assert len(result["pyramids"]) == 2

    @pytest.mark.asyncio
    async def test_get_trade_with_pyramids_not_found(self, populated_db):
        """Test getting non-existent trade returns None."""
        result = await populated_db.get_trade_with_pyramids("nonexistent")
        assert result is None


class TestConnectionProperty:
    """Tests for connection property."""

    @pytest.mark.asyncio
    async def test_connection_raises_when_disconnected(self):
        """Test that connection raises when not connected."""
        from app.database import Database

        db = Database(db_path=":memory:")
        with pytest.raises(RuntimeError, match="not connected"):
            _ = db.connection


class TestTransaction:
    """Tests for transaction context manager."""

    @pytest.mark.asyncio
    async def test_transaction_commits(self, test_db):
        """Test that transaction commits on success."""
        async with test_db.transaction():
            await test_db.connection.execute(
                "INSERT INTO processed_alerts (alert_id, processed_at) VALUES (?, ?)",
                ("tx_test_1", "2026-01-20T12:00:00")
            )

        # Verify commit happened
        is_processed = await test_db.is_alert_processed("tx_test_1")
        assert is_processed is True

    @pytest.mark.asyncio
    async def test_transaction_rollback_on_error(self, test_db):
        """Test that transaction rolls back on error."""
        try:
            async with test_db.transaction():
                await test_db.connection.execute(
                    "INSERT INTO processed_alerts (alert_id, processed_at) VALUES (?, ?)",
                    ("tx_test_2", "2026-01-20T12:00:00")
                )
                raise Exception("Simulated error")
        except Exception:
            pass

        # Verify rollback happened
        is_processed = await test_db.is_alert_processed("tx_test_2")
        assert is_processed is False


class TestAddPyramid:
    """Tests for add_pyramid method."""

    @pytest.mark.asyncio
    async def test_add_pyramid(self, test_db):
        """Test adding a pyramid to a trade."""
        # First create a trade
        await test_db.create_trade("pyramid_test_trade", "binance", "BTC", "USDT")

        # Add a pyramid
        await test_db.add_pyramid(
            pyramid_id="pyr_test_1",
            trade_id="pyramid_test_trade",
            pyramid_index=0,
            entry_price=50000.0,
            position_size=0.02,
            capital_usdt=1000.0,
            fee_rate=0.001,
            fee_usdt=1.0,
            exchange_timestamp="2026-01-20T10:00:00Z",
            received_timestamp="2026-01-20T10:00:01Z"
        )

        # Verify it was added
        pyramids = await test_db.get_pyramids_for_trade("pyramid_test_trade")
        assert len(pyramids) == 1
        assert pyramids[0]["id"] == "pyr_test_1"
        assert pyramids[0]["entry_price"] == 50000.0
        assert pyramids[0]["position_size"] == 0.02

    @pytest.mark.asyncio
    async def test_add_multiple_pyramids(self, test_db):
        """Test adding multiple pyramids to a trade."""
        await test_db.create_trade("multi_pyr_trade", "binance", "ETH", "USDT")

        # Add 3 pyramids
        for i in range(3):
            await test_db.add_pyramid(
                pyramid_id=f"pyr_{i}",
                trade_id="multi_pyr_trade",
                pyramid_index=i,
                entry_price=3000.0 - (i * 100),  # Decreasing prices
                position_size=0.1,
                capital_usdt=300.0,
                fee_rate=0.001,
                fee_usdt=0.3,
            )

        pyramids = await test_db.get_pyramids_for_trade("multi_pyr_trade")
        assert len(pyramids) == 3
        # Should be ordered by pyramid_index
        for i, p in enumerate(pyramids):
            assert p["pyramid_index"] == i


class TestAddExit:
    """Tests for add_exit method."""

    @pytest.mark.asyncio
    async def test_add_exit(self, test_db):
        """Test adding an exit record."""
        await test_db.create_trade("exit_test_trade", "binance", "BTC", "USDT")

        await test_db.add_exit(
            exit_id="exit_1",
            trade_id="exit_test_trade",
            exit_price=51000.0,
            fee_usdt=1.0,
            exchange_timestamp="2026-01-20T12:00:00Z",
            received_timestamp="2026-01-20T12:00:01Z"
        )

        # Verify it was added
        cursor = await test_db.connection.execute(
            "SELECT * FROM exits WHERE trade_id = ?", ("exit_test_trade",)
        )
        row = await cursor.fetchone()
        assert row is not None
        assert row["exit_price"] == 51000.0
        assert row["fee_usdt"] == 1.0


class TestUpdatePyramidPnl:
    """Tests for update_pyramid_pnl method."""

    @pytest.mark.asyncio
    async def test_update_pyramid_pnl(self, test_db):
        """Test updating pyramid PnL after exit."""
        await test_db.create_trade("pnl_update_trade", "binance", "BTC", "USDT")
        await test_db.add_pyramid(
            pyramid_id="pnl_pyr_1",
            trade_id="pnl_update_trade",
            pyramid_index=0,
            entry_price=50000.0,
            position_size=0.02,
            capital_usdt=1000.0,
            fee_rate=0.001,
            fee_usdt=1.0,
        )

        # Update PnL
        await test_db.update_pyramid_pnl("pnl_pyr_1", 50.0, 5.0)

        # Verify update
        cursor = await test_db.connection.execute(
            "SELECT pnl_usdt, pnl_percent FROM pyramids WHERE id = ?", ("pnl_pyr_1",)
        )
        row = await cursor.fetchone()
        assert row["pnl_usdt"] == 50.0
        assert row["pnl_percent"] == 5.0


class TestSymbolRules:
    """Tests for symbol rules cache methods."""

    @pytest.mark.asyncio
    async def test_get_symbol_rules_not_found(self, test_db):
        """Test getting non-existent symbol rules."""
        rules = await test_db.get_symbol_rules("binance", "BTC", "USDT")
        assert rules is None

    @pytest.mark.asyncio
    async def test_upsert_symbol_rules(self, test_db):
        """Test upserting symbol rules."""
        await test_db.upsert_symbol_rules(
            exchange="binance",
            base="BTC",
            quote="USDT",
            price_precision=2,
            qty_precision=6,
            min_qty=0.000001,
            min_notional=5.0,
            tick_size=0.01,
        )

        rules = await test_db.get_symbol_rules("binance", "BTC", "USDT")
        assert rules is not None
        assert rules["price_precision"] == 2
        assert rules["qty_precision"] == 6
        assert rules["min_qty"] == 0.000001
        assert rules["min_notional"] == 5.0
        assert rules["tick_size"] == 0.01

    @pytest.mark.asyncio
    async def test_upsert_symbol_rules_update(self, test_db):
        """Test updating existing symbol rules."""
        # Insert first version
        await test_db.upsert_symbol_rules(
            exchange="binance", base="ETH", quote="USDT",
            price_precision=2, qty_precision=4,
            min_qty=0.001, min_notional=5.0, tick_size=0.01,
        )

        # Update
        await test_db.upsert_symbol_rules(
            exchange="binance", base="ETH", quote="USDT",
            price_precision=3, qty_precision=5,
            min_qty=0.0001, min_notional=10.0, tick_size=0.001,
        )

        rules = await test_db.get_symbol_rules("binance", "ETH", "USDT")
        assert rules["price_precision"] == 3
        assert rules["qty_precision"] == 5
        assert rules["min_notional"] == 10.0


class TestSettings:
    """Tests for settings methods."""

    @pytest.mark.asyncio
    async def test_get_setting_not_found(self, test_db):
        """Test getting non-existent setting."""
        value = await test_db.get_setting("nonexistent_key")
        assert value is None

    @pytest.mark.asyncio
    async def test_set_and_get_setting(self, test_db):
        """Test setting and getting a setting."""
        await test_db.set_setting("test_key", "test_value")

        value = await test_db.get_setting("test_key")
        assert value == "test_value"

    @pytest.mark.asyncio
    async def test_set_setting_update(self, test_db):
        """Test updating an existing setting."""
        await test_db.set_setting("update_key", "value1")
        await test_db.set_setting("update_key", "value2")

        value = await test_db.get_setting("update_key")
        assert value == "value2"


class TestIsPaused:
    """Tests for is_paused method."""

    @pytest.mark.asyncio
    async def test_is_paused_default(self, test_db):
        """Test is_paused returns False by default."""
        is_paused = await test_db.is_paused()
        assert is_paused is False

    @pytest.mark.asyncio
    async def test_is_paused_true(self, test_db):
        """Test is_paused returns True when set."""
        await test_db.set_setting("paused", "true")

        is_paused = await test_db.is_paused()
        assert is_paused is True

    @pytest.mark.asyncio
    async def test_is_paused_false(self, test_db):
        """Test is_paused returns False when explicitly set."""
        await test_db.set_setting("paused", "false")

        is_paused = await test_db.is_paused()
        assert is_paused is False


class TestIsPairIgnored:
    """Tests for is_pair_ignored method."""

    @pytest.mark.asyncio
    async def test_is_pair_ignored_default(self, test_db):
        """Test is_pair_ignored returns False by default."""
        is_ignored = await test_db.is_pair_ignored("BTC", "USDT")
        assert is_ignored is False

    @pytest.mark.asyncio
    async def test_is_pair_ignored_true(self, test_db):
        """Test is_pair_ignored returns True when pair is ignored."""
        await test_db.set_setting("ignored_pairs", "BTC/USDT,ETH/USDT")

        assert await test_db.is_pair_ignored("BTC", "USDT") is True
        assert await test_db.is_pair_ignored("ETH", "USDT") is True
        assert await test_db.is_pair_ignored("XRP", "USDT") is False


class TestGetNextGroupSequence:
    """Tests for get_next_group_sequence method."""

    @pytest.mark.asyncio
    async def test_first_sequence(self, test_db):
        """Test getting first sequence number."""
        seq = await test_db.get_next_group_sequence("BTC", "binance", "1h")

        assert seq == 1

    @pytest.mark.asyncio
    async def test_increment_sequence(self, test_db):
        """Test sequence increments correctly."""
        seq1 = await test_db.get_next_group_sequence("ETH", "binance", "1h")
        seq2 = await test_db.get_next_group_sequence("ETH", "binance", "1h")
        seq3 = await test_db.get_next_group_sequence("ETH", "binance", "1h")

        assert seq1 == 1
        assert seq2 == 2
        assert seq3 == 3

    @pytest.mark.asyncio
    async def test_different_keys_separate_sequences(self, test_db):
        """Test different base/exchange/timeframe have separate sequences."""
        seq1 = await test_db.get_next_group_sequence("BTC", "binance", "1h")
        seq2 = await test_db.get_next_group_sequence("BTC", "bybit", "1h")
        seq3 = await test_db.get_next_group_sequence("BTC", "binance", "4h")

        # All should be 1 since they're different keys
        assert seq1 == 1
        assert seq2 == 1
        assert seq3 == 1


class TestGetOpenTradeByGroup:
    """Tests for get_open_trade_by_group method."""

    @pytest.mark.asyncio
    async def test_get_open_trade_by_group(self, test_db):
        """Test getting open trade by group."""
        await test_db.create_trade_with_group(
            trade_id="group_trade_1",
            group_id="BTC_Binance_1h_001",
            exchange="binance",
            base="BTC",
            quote="USDT",
            timeframe="1h",
        )

        trade = await test_db.get_open_trade_by_group(
            "binance", "BTC", "USDT", "1h"
        )

        assert trade is not None
        assert trade["id"] == "group_trade_1"
        assert trade["group_id"] == "BTC_Binance_1h_001"

    @pytest.mark.asyncio
    async def test_get_open_trade_by_group_not_found(self, test_db):
        """Test get_open_trade_by_group returns None when not found."""
        trade = await test_db.get_open_trade_by_group(
            "binance", "NONEXISTENT", "USDT", "1h"
        )
        assert trade is None


class TestCreateTradeWithGroup:
    """Tests for create_trade_with_group method."""

    @pytest.mark.asyncio
    async def test_create_trade_with_group(self, test_db):
        """Test creating a trade with group ID."""
        await test_db.create_trade_with_group(
            trade_id="grouped_trade",
            group_id="ETH_Binance_4h_001",
            exchange="binance",
            base="ETH",
            quote="USDT",
            timeframe="4h",
            position_side="long",
        )

        # Verify
        cursor = await test_db.connection.execute(
            "SELECT * FROM trades WHERE id = ?", ("grouped_trade",)
        )
        row = await cursor.fetchone()

        assert row is not None
        assert row["group_id"] == "ETH_Binance_4h_001"
        assert row["timeframe"] == "4h"
        assert row["position_side"] == "long"
        assert row["status"] == "open"


class TestPyramidCapital:
    """Tests for pyramid capital methods."""

    @pytest.mark.asyncio
    async def test_get_pyramid_capital_default(self, test_db):
        """Test getting default capital when not set."""
        capital = await test_db.get_pyramid_capital(
            pyramid_index=0,
            exchange="binance",
            base="BTC",
            quote="USDT",
            timeframe="1h",
        )
        assert capital == 1000.0  # Default

    @pytest.mark.asyncio
    async def test_set_and_get_pyramid_capital(self, test_db):
        """Test setting and getting pyramid capital."""
        await test_db.set_pyramid_capital(
            pyramid_index=0,
            capital=500.0,
            exchange="binance",
            base="BTC",
            quote="USDT",
            timeframe="1h",
        )

        capital = await test_db.get_pyramid_capital(
            pyramid_index=0,
            exchange="binance",
            base="BTC",
            quote="USDT",
            timeframe="1h",
        )
        assert capital == 500.0

    @pytest.mark.asyncio
    async def test_get_all_pyramid_capitals_empty(self, test_db):
        """Test getting all capitals when none set."""
        capitals = await test_db.get_all_pyramid_capitals()
        assert capitals == {}

    @pytest.mark.asyncio
    async def test_get_all_pyramid_capitals(self, test_db):
        """Test getting all pyramid capitals."""
        await test_db.set_pyramid_capital(
            0, 500.0, "binance", "BTC", "USDT", "1h"
        )
        await test_db.set_pyramid_capital(
            1, 750.0, "binance", "BTC", "USDT", "1h"
        )

        capitals = await test_db.get_all_pyramid_capitals()
        assert len(capitals) == 2

    @pytest.mark.asyncio
    async def test_clear_pyramid_capital(self, test_db):
        """Test clearing specific pyramid capital."""
        await test_db.set_pyramid_capital(
            0, 500.0, "binance", "BTC", "USDT", "1h"
        )
        await test_db.set_pyramid_capital(
            0, None, "binance", "BTC", "USDT", "1h"  # Clear it
        )

        capital = await test_db.get_pyramid_capital(
            0, "binance", "BTC", "USDT", "1h"
        )
        assert capital == 1000.0  # Back to default

    @pytest.mark.asyncio
    async def test_clear_all_pyramid_capitals(self, test_db):
        """Test clearing all pyramid capitals."""
        await test_db.set_pyramid_capital(
            0, 500.0, "binance", "BTC", "USDT", "1h"
        )
        await test_db.set_pyramid_capital(
            0, 750.0, "binance", "ETH", "USDT", "1h"
        )

        await test_db.clear_all_pyramid_capitals()

        capitals = await test_db.get_all_pyramid_capitals()
        assert capitals == {}


class TestResetMethods:
    """Tests for database reset methods."""

    @pytest.mark.asyncio
    async def test_reset_trades(self, populated_db):
        """Test reset_trades clears all trade data."""
        counts = await populated_db.reset_trades()

        assert counts["trades"] > 0
        assert counts["pyramids"] > 0

        # Verify data was cleared
        cursor = await populated_db.connection.execute("SELECT COUNT(*) FROM trades")
        row = await cursor.fetchone()
        assert row[0] == 0

        cursor = await populated_db.connection.execute("SELECT COUNT(*) FROM pyramids")
        row = await cursor.fetchone()
        assert row[0] == 0

    @pytest.mark.asyncio
    async def test_reset_settings(self, test_db):
        """Test reset_settings clears all settings."""
        # Add some settings
        await test_db.set_setting("key1", "value1")
        await test_db.set_setting("key2", "value2")

        counts = await test_db.reset_settings()

        assert counts["settings"] == 2

        # Verify cleared
        value = await test_db.get_setting("key1")
        assert value is None

    @pytest.mark.asyncio
    async def test_reset_cache(self, test_db):
        """Test reset_cache clears cached data."""
        # Add some symbol rules
        await test_db.upsert_symbol_rules(
            "binance", "BTC", "USDT", 2, 6, 0.00001, 5.0, 0.01
        )

        counts = await test_db.reset_cache()

        assert counts["symbol_rules"] > 0

        # Verify cleared
        rules = await test_db.get_symbol_rules("binance", "BTC", "USDT")
        assert rules is None

    @pytest.mark.asyncio
    async def test_reset_all(self, populated_db):
        """Test reset_all clears everything."""
        # Add some settings
        await populated_db.set_setting("key1", "value1")
        await populated_db.upsert_symbol_rules(
            "binance", "BTC", "USDT", 2, 6, 0.00001, 5.0, 0.01
        )

        counts = await populated_db.reset_all()

        # Should have counts from all reset methods
        assert "trades" in counts
        assert "settings" in counts
        assert "symbol_rules" in counts

        # Verify everything is empty
        cursor = await populated_db.connection.execute("SELECT COUNT(*) FROM trades")
        assert (await cursor.fetchone())[0] == 0

        cursor = await populated_db.connection.execute("SELECT COUNT(*) FROM settings")
        assert (await cursor.fetchone())[0] == 0

        cursor = await populated_db.connection.execute("SELECT COUNT(*) FROM symbol_rules")
        assert (await cursor.fetchone())[0] == 0
