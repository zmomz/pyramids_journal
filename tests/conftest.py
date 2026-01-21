"""
Pytest fixtures and configuration for the test suite.
"""

import asyncio
import os
import tempfile
from datetime import datetime, timedelta
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, patch, Mock

import pytest
import pytest_asyncio

# Set test environment before importing app modules
os.environ["TESTING"] = "1"
os.environ["TELEGRAM_BOT_TOKEN"] = "test_token"
os.environ["TELEGRAM_CHAT_ID"] = "-1001234567890"
os.environ["TIMEZONE"] = "UTC"  # Use UTC for predictable date calculations


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def test_db():
    """Create an isolated in-memory database for testing."""
    from app.database import Database

    # Use a temporary file for the test database
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        temp_db_path = f.name

    # Create database instance with temp path
    db = Database(db_path=temp_db_path)

    # Patch ensure_data_directory to do nothing (we're using temp file)
    with patch("app.database.ensure_data_directory"):
        await db.connect()

    yield db

    await db.disconnect()

    # Clean up temp file
    if os.path.exists(temp_db_path):
        os.unlink(temp_db_path)


@pytest_asyncio.fixture
async def populated_db(test_db):
    """Create a database with sample trade data."""
    # Insert sample trades for testing
    today = datetime.now().strftime("%Y-%m-%d")
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

    # Sample trades
    trades = [
        # Today's trades
        {
            "id": "trade_1",
            "exchange": "binance",
            "base": "BTC",
            "quote": "USDT",
            "status": "closed",
            "timeframe": "1h",
            "group_id": "group_1",
            "total_pnl_usdt": 100.50,
            "total_pnl_percent": 5.25,
            "created_at": f"{today} 09:00:00",
            "closed_at": f"{today} 10:00:00",
        },
        {
            "id": "trade_2",
            "exchange": "binance",
            "base": "ETH",
            "quote": "USDT",
            "status": "closed",
            "timeframe": "1h",
            "group_id": "group_2",
            "total_pnl_usdt": -30.25,
            "total_pnl_percent": -2.15,
            "created_at": f"{today} 11:00:00",
            "closed_at": f"{today} 12:00:00",
        },
        {
            "id": "trade_3",
            "exchange": "bybit",
            "base": "SOL",
            "quote": "USDT",
            "status": "closed",
            "timeframe": "4h",
            "group_id": "group_3",
            "total_pnl_usdt": 50.00,
            "total_pnl_percent": 3.50,
            "created_at": f"{today} 13:00:00",
            "closed_at": f"{today} 14:00:00",
        },
        # Yesterday's trades
        {
            "id": "trade_4",
            "exchange": "binance",
            "base": "BTC",
            "quote": "USDT",
            "status": "closed",
            "timeframe": "1h",
            "group_id": "group_4",
            "total_pnl_usdt": 200.00,
            "total_pnl_percent": 10.00,
            "created_at": f"{yesterday} 09:00:00",
            "closed_at": f"{yesterday} 10:00:00",
        },
        {
            "id": "trade_5",
            "exchange": "bybit",
            "base": "DOGE",
            "quote": "USDT",
            "status": "closed",
            "timeframe": "15m",
            "group_id": "group_5",
            "total_pnl_usdt": -75.50,
            "total_pnl_percent": -5.50,
            "created_at": f"{yesterday} 14:00:00",
            "closed_at": f"{yesterday} 15:00:00",
        },
        # Week-old trade
        {
            "id": "trade_6",
            "exchange": "binance",
            "base": "XRP",
            "quote": "USDT",
            "status": "closed",
            "timeframe": "1d",
            "group_id": "group_6",
            "total_pnl_usdt": 150.00,
            "total_pnl_percent": 7.50,
            "created_at": f"{week_ago} 09:00:00",
            "closed_at": f"{week_ago} 18:00:00",
        },
        # Open trade (still active)
        {
            "id": "trade_7",
            "exchange": "binance",
            "base": "LINK",
            "quote": "USDT",
            "status": "open",
            "timeframe": "1h",
            "group_id": "group_7",
            "total_pnl_usdt": None,
            "total_pnl_percent": None,
            "created_at": f"{today} 15:00:00",
            "closed_at": None,
        },
    ]

    # Insert trades
    for trade in trades:
        await test_db.connection.execute(
            """
            INSERT INTO trades (id, exchange, base, quote, status, timeframe, group_id,
                              total_pnl_usdt, total_pnl_percent, created_at, closed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                trade["id"],
                trade["exchange"],
                trade["base"],
                trade["quote"],
                trade["status"],
                trade["timeframe"],
                trade["group_id"],
                trade["total_pnl_usdt"],
                trade["total_pnl_percent"],
                trade["created_at"],
                trade["closed_at"],
            ),
        )

    # Insert sample pyramids
    pyramids = [
        ("pyr_1", "trade_1", 1, 50000.0, 0.02, 1000.0, f"{today} 09:00:00", 0.001, 1.0),
        ("pyr_2", "trade_1", 2, 49500.0, 0.02, 990.0, f"{today} 09:30:00", 0.001, 0.99),
        ("pyr_3", "trade_2", 1, 3000.0, 0.5, 1500.0, f"{today} 11:00:00", 0.001, 1.5),
        ("pyr_4", "trade_3", 1, 100.0, 10.0, 1000.0, f"{today} 13:00:00", 0.001, 1.0),
        ("pyr_5", "trade_4", 1, 48000.0, 0.025, 1200.0, f"{yesterday} 09:00:00", 0.001, 1.2),
        ("pyr_6", "trade_7", 1, 15.0, 100.0, 1500.0, f"{today} 15:00:00", 0.001, 1.5),
    ]

    for pyr in pyramids:
        await test_db.connection.execute(
            """
            INSERT INTO pyramids (id, trade_id, pyramid_index, entry_price, position_size,
                                capital_usdt, entry_time, fee_rate, fee_usdt)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            pyr,
        )

    await test_db.connection.commit()

    yield test_db


@pytest.fixture
def mock_telegram_bot():
    """Create a mock Telegram bot."""
    bot = MagicMock()
    bot.send_message = AsyncMock(return_value=MagicMock(message_id=123))
    bot.send_photo = AsyncMock(return_value=MagicMock(message_id=124))
    bot.send_document = AsyncMock(return_value=MagicMock(message_id=125))
    return bot


@pytest.fixture
def mock_update():
    """Create a mock Telegram Update object."""
    update = MagicMock()
    update.effective_chat.id = -1001234567890
    update.message.reply_text = AsyncMock()
    update.message.reply_photo = AsyncMock()
    update.message.reply_document = AsyncMock()
    update.message.chat_id = -1001234567890
    return update


@pytest.fixture
def mock_context():
    """Create a mock Telegram context object."""
    context = MagicMock()
    context.args = []
    context.bot = MagicMock()
    context.bot.send_message = AsyncMock()
    return context


@pytest.fixture
def mock_callback_query():
    """Create a mock callback query for menu tests."""
    query = MagicMock()
    query.data = "menu_main"
    query.message.chat_id = -1001234567890
    query.message.chat = MagicMock(id=-1001234567890)
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    query.message.reply_text = AsyncMock()
    return query


@pytest.fixture
def sample_equity_points():
    """Create sample equity points for chart testing."""
    from app.models import EquityPoint

    base_time = datetime(2026, 1, 20, 9, 0, 0)
    return [
        EquityPoint(timestamp=base_time, cumulative_pnl=0.0),
        EquityPoint(timestamp=base_time + timedelta(hours=1), cumulative_pnl=50.0),
        EquityPoint(timestamp=base_time + timedelta(hours=2), cumulative_pnl=30.0),
        EquityPoint(timestamp=base_time + timedelta(hours=3), cumulative_pnl=100.0),
        EquityPoint(timestamp=base_time + timedelta(hours=4), cumulative_pnl=120.25),
    ]


@pytest.fixture
def sample_chart_stats():
    """Create sample chart stats for testing."""
    from app.models import ChartStats

    return ChartStats(
        total_net_pnl=120.25,
        max_drawdown_percent=5.50,
        max_drawdown_usdt=20.0,
        trades_opened_today=3,
        trades_closed_today=3,
        win_rate=66.67,
        total_used_equity=3500.0,
        profit_factor=2.5,
        win_loss_ratio=1.8,
        cumulative_pnl=500.0,
    )


@pytest.fixture
def sample_daily_report_data(sample_equity_points, sample_chart_stats):
    """Create sample daily report data for testing."""
    from app.models import DailyReportData, TradeHistoryItem

    return DailyReportData(
        date="2026-01-20",
        total_trades=3,
        total_pyramids=4,
        total_pnl_usdt=120.25,
        total_pnl_percent=3.43,
        trades=[
            TradeHistoryItem(
                group_id="group_1",
                exchange="binance",
                pair="BTC/USDT",
                timeframe="1h",
                pyramids_count=2,
                pnl_usdt=100.50,
                pnl_percent=5.25,
            ),
            TradeHistoryItem(
                group_id="group_2",
                exchange="binance",
                pair="ETH/USDT",
                timeframe="1h",
                pyramids_count=1,
                pnl_usdt=-30.25,
                pnl_percent=-2.15,
            ),
            TradeHistoryItem(
                group_id="group_3",
                exchange="bybit",
                pair="SOL/USDT",
                timeframe="4h",
                pyramids_count=1,
                pnl_usdt=50.00,
                pnl_percent=3.50,
            ),
        ],
        by_exchange={"binance": {"pnl": 70.25, "trades": 2}, "bybit": {"pnl": 50.0, "trades": 1}},
        by_timeframe={"1h": {"pnl": 70.25, "trades": 2}, "4h": {"pnl": 50.0, "trades": 1}},
        by_pair={"BTC/USDT": 100.50, "ETH/USDT": -30.25, "SOL/USDT": 50.0},
        equity_points=sample_equity_points,
        chart_stats=sample_chart_stats,
    )
