import aiosqlite
from contextlib import asynccontextmanager
from datetime import datetime
from typing import AsyncGenerator

from .config import settings, ensure_data_directory

# SQL Schema
SCHEMA = """
-- Trades table
CREATE TABLE IF NOT EXISTS trades (
    id TEXT PRIMARY KEY,
    exchange TEXT NOT NULL,
    base TEXT NOT NULL,
    quote TEXT NOT NULL,
    status TEXT DEFAULT 'open',
    created_at TIMESTAMP NOT NULL,
    closed_at TIMESTAMP,
    total_pnl_usdt REAL,
    total_pnl_percent REAL
);

-- Pyramids table
CREATE TABLE IF NOT EXISTS pyramids (
    id TEXT PRIMARY KEY,
    trade_id TEXT NOT NULL,
    pyramid_index INTEGER NOT NULL,
    entry_price REAL NOT NULL,
    position_size REAL NOT NULL,
    notional_usdt REAL NOT NULL,
    entry_time TIMESTAMP NOT NULL,
    fee_rate REAL NOT NULL,
    fee_usdt REAL NOT NULL,
    pnl_usdt REAL,
    pnl_percent REAL,
    FOREIGN KEY (trade_id) REFERENCES trades(id)
);

-- Exits table
CREATE TABLE IF NOT EXISTS exits (
    id TEXT PRIMARY KEY,
    trade_id TEXT NOT NULL UNIQUE,
    exit_price REAL NOT NULL,
    exit_time TIMESTAMP NOT NULL,
    fee_usdt REAL NOT NULL,
    FOREIGN KEY (trade_id) REFERENCES trades(id)
);

-- Symbol rules cache
CREATE TABLE IF NOT EXISTS symbol_rules (
    exchange TEXT NOT NULL,
    base TEXT NOT NULL,
    quote TEXT NOT NULL,
    price_precision INTEGER,
    qty_precision INTEGER,
    min_qty REAL,
    min_notional REAL,
    tick_size REAL,
    updated_at TIMESTAMP,
    PRIMARY KEY (exchange, base, quote)
);

-- Daily reports
CREATE TABLE IF NOT EXISTS daily_reports (
    date TEXT PRIMARY KEY,
    total_trades INTEGER,
    total_pyramids INTEGER,
    total_pnl_usdt REAL,
    report_json TEXT,
    sent_at TIMESTAMP
);

-- Processed alerts (for idempotency)
CREATE TABLE IF NOT EXISTS processed_alerts (
    alert_id TEXT PRIMARY KEY,
    processed_at TIMESTAMP NOT NULL
);

-- Settings table (for bot configuration)
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TIMESTAMP
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_trades_status ON trades(status);
CREATE INDEX IF NOT EXISTS idx_trades_exchange ON trades(exchange);
CREATE INDEX IF NOT EXISTS idx_pyramids_trade_id ON pyramids(trade_id);
CREATE INDEX IF NOT EXISTS idx_symbol_rules_exchange ON symbol_rules(exchange);
"""


class Database:
    """Async SQLite database handler."""

    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or settings.database_path
        self._connection: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        """Connect to the database and initialize schema."""
        ensure_data_directory()
        self._connection = await aiosqlite.connect(self.db_path)
        self._connection.row_factory = aiosqlite.Row
        await self._connection.executescript(SCHEMA)
        await self._connection.commit()

    async def disconnect(self) -> None:
        """Close database connection."""
        if self._connection:
            await self._connection.close()
            self._connection = None

    @property
    def connection(self) -> aiosqlite.Connection:
        """Get the active connection."""
        if not self._connection:
            raise RuntimeError("Database not connected")
        return self._connection

    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator[aiosqlite.Connection, None]:
        """Context manager for database transactions."""
        try:
            yield self.connection
            await self.connection.commit()
        except Exception:
            await self.connection.rollback()
            raise

    # Alert idempotency methods
    async def is_alert_processed(self, alert_id: str) -> bool:
        """Check if an alert has already been processed."""
        cursor = await self.connection.execute(
            "SELECT 1 FROM processed_alerts WHERE alert_id = ?", (alert_id,)
        )
        return await cursor.fetchone() is not None

    async def mark_alert_processed(self, alert_id: str) -> None:
        """Mark an alert as processed."""
        await self.connection.execute(
            "INSERT OR IGNORE INTO processed_alerts (alert_id, processed_at) VALUES (?, ?)",
            (alert_id, datetime.utcnow().isoformat()),
        )
        await self.connection.commit()

    # Trade methods
    async def get_open_trade(self, exchange: str, base: str, quote: str) -> dict | None:
        """Get an open trade for the given exchange and symbol."""
        cursor = await self.connection.execute(
            """
            SELECT * FROM trades
            WHERE exchange = ? AND base = ? AND quote = ? AND status = 'open'
            ORDER BY created_at DESC LIMIT 1
            """,
            (exchange, base, quote),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def create_trade(
        self, trade_id: str, exchange: str, base: str, quote: str
    ) -> None:
        """Create a new trade."""
        await self.connection.execute(
            """
            INSERT INTO trades (id, exchange, base, quote, status, created_at)
            VALUES (?, ?, ?, ?, 'open', ?)
            """,
            (trade_id, exchange, base, quote, datetime.utcnow().isoformat()),
        )
        await self.connection.commit()

    async def close_trade(
        self, trade_id: str, total_pnl_usdt: float, total_pnl_percent: float
    ) -> None:
        """Close a trade with final PnL."""
        await self.connection.execute(
            """
            UPDATE trades
            SET status = 'closed', closed_at = ?, total_pnl_usdt = ?, total_pnl_percent = ?
            WHERE id = ?
            """,
            (datetime.utcnow().isoformat(), total_pnl_usdt, total_pnl_percent, trade_id),
        )
        await self.connection.commit()

    async def get_trade_with_pyramids(self, trade_id: str) -> dict | None:
        """Get a trade with all its pyramids."""
        cursor = await self.connection.execute(
            "SELECT * FROM trades WHERE id = ?", (trade_id,)
        )
        trade = await cursor.fetchone()
        if not trade:
            return None

        cursor = await self.connection.execute(
            "SELECT * FROM pyramids WHERE trade_id = ? ORDER BY pyramid_index",
            (trade_id,),
        )
        pyramids = await cursor.fetchall()

        cursor = await self.connection.execute(
            "SELECT * FROM exits WHERE trade_id = ?", (trade_id,)
        )
        exit_record = await cursor.fetchone()

        return {
            "trade": dict(trade),
            "pyramids": [dict(p) for p in pyramids],
            "exit": dict(exit_record) if exit_record else None,
        }

    # Pyramid methods
    async def add_pyramid(
        self,
        pyramid_id: str,
        trade_id: str,
        pyramid_index: int,
        entry_price: float,
        position_size: float,
        notional_usdt: float,
        fee_rate: float,
        fee_usdt: float,
    ) -> None:
        """Add a pyramid to a trade."""
        await self.connection.execute(
            """
            INSERT INTO pyramids
            (id, trade_id, pyramid_index, entry_price, position_size, notional_usdt,
             entry_time, fee_rate, fee_usdt)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                pyramid_id,
                trade_id,
                pyramid_index,
                entry_price,
                position_size,
                notional_usdt,
                datetime.utcnow().isoformat(),
                fee_rate,
                fee_usdt,
            ),
        )
        await self.connection.commit()

    async def get_pyramids_for_trade(self, trade_id: str) -> list[dict]:
        """Get all pyramids for a trade."""
        cursor = await self.connection.execute(
            "SELECT * FROM pyramids WHERE trade_id = ? ORDER BY pyramid_index",
            (trade_id,),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def update_pyramid_pnl(
        self, pyramid_id: str, pnl_usdt: float, pnl_percent: float
    ) -> None:
        """Update pyramid PnL after exit."""
        await self.connection.execute(
            "UPDATE pyramids SET pnl_usdt = ?, pnl_percent = ? WHERE id = ?",
            (pnl_usdt, pnl_percent, pyramid_id),
        )
        await self.connection.commit()

    # Exit methods
    async def add_exit(
        self, exit_id: str, trade_id: str, exit_price: float, fee_usdt: float
    ) -> None:
        """Add an exit record for a trade."""
        await self.connection.execute(
            """
            INSERT INTO exits (id, trade_id, exit_price, exit_time, fee_usdt)
            VALUES (?, ?, ?, ?, ?)
            """,
            (exit_id, trade_id, exit_price, datetime.utcnow().isoformat(), fee_usdt),
        )
        await self.connection.commit()

    # Symbol rules methods
    async def get_symbol_rules(
        self, exchange: str, base: str, quote: str
    ) -> dict | None:
        """Get cached symbol rules."""
        cursor = await self.connection.execute(
            """
            SELECT * FROM symbol_rules
            WHERE exchange = ? AND base = ? AND quote = ?
            """,
            (exchange, base, quote),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def upsert_symbol_rules(
        self,
        exchange: str,
        base: str,
        quote: str,
        price_precision: int,
        qty_precision: int,
        min_qty: float,
        min_notional: float,
        tick_size: float,
    ) -> None:
        """Insert or update symbol rules."""
        await self.connection.execute(
            """
            INSERT OR REPLACE INTO symbol_rules
            (exchange, base, quote, price_precision, qty_precision, min_qty,
             min_notional, tick_size, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                exchange,
                base,
                quote,
                price_precision,
                qty_precision,
                min_qty,
                min_notional,
                tick_size,
                datetime.utcnow().isoformat(),
            ),
        )
        await self.connection.commit()

    # Report methods
    async def get_trades_for_date(self, date: str) -> list[dict]:
        """Get all closed trades for a specific date."""
        cursor = await self.connection.execute(
            """
            SELECT * FROM trades
            WHERE status = 'closed' AND DATE(closed_at) = ?
            """,
            (date,),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def save_daily_report(
        self,
        date: str,
        total_trades: int,
        total_pyramids: int,
        total_pnl_usdt: float,
        report_json: str,
    ) -> None:
        """Save daily report."""
        await self.connection.execute(
            """
            INSERT OR REPLACE INTO daily_reports
            (date, total_trades, total_pyramids, total_pnl_usdt, report_json, sent_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                date,
                total_trades,
                total_pyramids,
                total_pnl_usdt,
                report_json,
                datetime.utcnow().isoformat(),
            ),
        )
        await self.connection.commit()

    # Utility methods
    async def get_recent_trades(self, limit: int = 50) -> list[dict]:
        """Get recent trades for debugging."""
        cursor = await self.connection.execute(
            "SELECT * FROM trades ORDER BY created_at DESC LIMIT ?", (limit,)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    # Settings methods
    async def get_setting(self, key: str) -> str | None:
        """Get a setting value."""
        cursor = await self.connection.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        )
        row = await cursor.fetchone()
        return row["value"] if row else None

    async def set_setting(self, key: str, value: str) -> None:
        """Set a setting value."""
        await self.connection.execute(
            "INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?, ?, ?)",
            (key, value, datetime.utcnow().isoformat()),
        )
        await self.connection.commit()

    async def is_paused(self) -> bool:
        """Check if signal processing is paused."""
        value = await self.get_setting("paused")
        return value == "true"

    async def is_pair_ignored(self, base: str, quote: str) -> bool:
        """Check if a pair is ignored."""
        value = await self.get_setting("ignored_pairs")
        if not value:
            return False
        ignored = value.split(",")
        return f"{base}/{quote}" in ignored


# Global database instance
db = Database()
