import aiosqlite
from contextlib import asynccontextmanager
from datetime import datetime, UTC
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
    timeframe TEXT,
    group_id TEXT,
    position_side TEXT DEFAULT 'long',
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
    capital_usdt REAL NOT NULL,
    entry_time TIMESTAMP NOT NULL,
    fee_rate REAL NOT NULL,
    fee_usdt REAL NOT NULL,
    pnl_usdt REAL,
    pnl_percent REAL,
    exchange_timestamp TEXT,
    received_timestamp TEXT,
    FOREIGN KEY (trade_id) REFERENCES trades(id)
);

-- Exits table
CREATE TABLE IF NOT EXISTS exits (
    id TEXT PRIMARY KEY,
    trade_id TEXT NOT NULL UNIQUE,
    exit_price REAL NOT NULL,
    exit_time TIMESTAMP NOT NULL,
    fee_usdt REAL NOT NULL,
    exchange_timestamp TEXT,
    received_timestamp TEXT,
    FOREIGN KEY (trade_id) REFERENCES trades(id)
);

-- Pyramid group sequences (for generating group IDs)
CREATE TABLE IF NOT EXISTS pyramid_group_sequences (
    base TEXT NOT NULL,
    exchange TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    next_sequence INTEGER DEFAULT 1,
    updated_at TIMESTAMP,
    PRIMARY KEY (base, exchange, timeframe)
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
CREATE INDEX IF NOT EXISTS idx_trades_group_id ON trades(group_id);
CREATE INDEX IF NOT EXISTS idx_trades_timeframe ON trades(timeframe);
CREATE INDEX IF NOT EXISTS idx_pyramids_trade_id ON pyramids(trade_id);
CREATE INDEX IF NOT EXISTS idx_symbol_rules_exchange ON symbol_rules(exchange);
"""

# Migration queries for existing databases
MIGRATIONS = """
-- Add new columns to trades table if not exist
ALTER TABLE trades ADD COLUMN timeframe TEXT;
ALTER TABLE trades ADD COLUMN group_id TEXT;
ALTER TABLE trades ADD COLUMN position_side TEXT DEFAULT 'long';

-- Add new columns to pyramids table
ALTER TABLE pyramids ADD COLUMN exchange_timestamp TEXT;
ALTER TABLE pyramids ADD COLUMN received_timestamp TEXT;

-- Add new columns to exits table
ALTER TABLE exits ADD COLUMN exchange_timestamp TEXT;
ALTER TABLE exits ADD COLUMN received_timestamp TEXT;
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
        # Run migrations for existing databases
        await self._run_migrations()

    async def _run_migrations(self) -> None:
        """Run database migrations for new columns."""
        # Check existing columns in trades table
        cursor = await self._connection.execute("PRAGMA table_info(trades)")
        columns = {row[1] for row in await cursor.fetchall()}

        if "timeframe" not in columns:
            await self._connection.execute(
                "ALTER TABLE trades ADD COLUMN timeframe TEXT"
            )
        if "group_id" not in columns:
            await self._connection.execute(
                "ALTER TABLE trades ADD COLUMN group_id TEXT"
            )
        if "position_side" not in columns:
            await self._connection.execute(
                "ALTER TABLE trades ADD COLUMN position_side TEXT DEFAULT 'long'"
            )

        # Check pyramids table
        cursor = await self._connection.execute("PRAGMA table_info(pyramids)")
        columns = {row[1] for row in await cursor.fetchall()}

        if "exchange_timestamp" not in columns:
            await self._connection.execute(
                "ALTER TABLE pyramids ADD COLUMN exchange_timestamp TEXT"
            )
        if "received_timestamp" not in columns:
            await self._connection.execute(
                "ALTER TABLE pyramids ADD COLUMN received_timestamp TEXT"
            )

        # Check exits table
        cursor = await self._connection.execute("PRAGMA table_info(exits)")
        columns = {row[1] for row in await cursor.fetchall()}

        if "exchange_timestamp" not in columns:
            await self._connection.execute(
                "ALTER TABLE exits ADD COLUMN exchange_timestamp TEXT"
            )
        if "received_timestamp" not in columns:
            await self._connection.execute(
                "ALTER TABLE exits ADD COLUMN received_timestamp TEXT"
            )

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
            (alert_id, datetime.now(UTC).isoformat()),
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
            (trade_id, exchange, base, quote, datetime.now(UTC).isoformat()),
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
            (datetime.now(UTC).isoformat(), total_pnl_usdt, total_pnl_percent, trade_id),
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
        capital_usdt: float,
        fee_rate: float,
        fee_usdt: float,
        exchange_timestamp: str | None = None,
        received_timestamp: str | None = None,
    ) -> None:
        """Add a pyramid to a trade."""
        await self.connection.execute(
            """
            INSERT INTO pyramids
            (id, trade_id, pyramid_index, entry_price, position_size, capital_usdt,
             entry_time, fee_rate, fee_usdt, exchange_timestamp, received_timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                pyramid_id,
                trade_id,
                pyramid_index,
                entry_price,
                position_size,
                capital_usdt,
                datetime.utcnow().isoformat(),
                fee_rate,
                fee_usdt,
                exchange_timestamp,
                received_timestamp or datetime.utcnow().isoformat(),
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
        self,
        exit_id: str,
        trade_id: str,
        exit_price: float,
        fee_usdt: float,
        exchange_timestamp: str | None = None,
        received_timestamp: str | None = None,
    ) -> None:
        """Add an exit record for a trade."""
        await self.connection.execute(
            """
            INSERT INTO exits (id, trade_id, exit_price, exit_time, fee_usdt,
                               exchange_timestamp, received_timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                exit_id,
                trade_id,
                exit_price,
                datetime.utcnow().isoformat(),
                fee_usdt,
                exchange_timestamp,
                received_timestamp or datetime.utcnow().isoformat(),
            ),
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

    async def get_equity_curve_data(self, date: str) -> list[dict]:
        """
        Get equity curve data points for a specific date.
        Returns trades ordered by close time with their PnL.
        """
        cursor = await self.connection.execute(
            """
            SELECT closed_at, total_pnl_usdt
            FROM trades
            WHERE status = 'closed' AND DATE(closed_at) = ?
            ORDER BY closed_at ASC
            """,
            (date,),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def get_cumulative_pnl_before_date(self, date: str) -> float:
        """
        Get the cumulative realized PnL from all closed trades BEFORE the given date.
        This is used to start the equity curve from the correct previous value.
        """
        cursor = await self.connection.execute(
            """
            SELECT COALESCE(SUM(total_pnl_usdt), 0) as cumulative_pnl
            FROM trades
            WHERE status = 'closed' AND DATE(closed_at) < ?
            """,
            (date,),
        )
        row = await cursor.fetchone()
        return row["cumulative_pnl"] if row else 0.0

    async def get_trade_counts_for_date(self, date: str) -> dict:
        """
        Get trade count breakdown for a specific date.

        Returns:
            Dict with:
            - opened_today: Trades opened on this date
            - closed_today: Trades closed on this date
            - still_open: Trades opened before this date that are still open
        """
        # Trades opened today
        cursor = await self.connection.execute(
            "SELECT COUNT(*) as count FROM trades WHERE DATE(created_at) = ?",
            (date,),
        )
        row = await cursor.fetchone()
        opened_today = row["count"] if row else 0

        # Trades closed today
        cursor = await self.connection.execute(
            "SELECT COUNT(*) as count FROM trades WHERE status = 'closed' AND DATE(closed_at) = ?",
            (date,),
        )
        row = await cursor.fetchone()
        closed_today = row["count"] if row else 0

        # Trades still open (opened before today)
        cursor = await self.connection.execute(
            "SELECT COUNT(*) as count FROM trades WHERE status = 'open' AND DATE(created_at) < ?",
            (date,),
        )
        row = await cursor.fetchone()
        still_open = row["count"] if row else 0

        return {
            "opened_today": opened_today,
            "closed_today": closed_today,
            "still_open": still_open,
        }

    # =========== Period-Based Query Methods ===========

    async def get_realized_pnl_for_period(
        self, start_date: str | None, end_date: str | None
    ) -> tuple[float, int]:
        """
        Get realized PnL and trade count for a date range.

        Args:
            start_date: Start date (YYYY-MM-DD) or None for all-time
            end_date: End date (YYYY-MM-DD) or None for all-time

        Returns:
            Tuple of (total_pnl, trade_count)
        """
        if start_date and end_date:
            cursor = await self.connection.execute(
                """
                SELECT COALESCE(SUM(total_pnl_usdt), 0) as pnl, COUNT(*) as count
                FROM trades
                WHERE status = 'closed' AND DATE(closed_at) BETWEEN ? AND ?
                """,
                (start_date, end_date),
            )
        else:
            cursor = await self.connection.execute(
                """
                SELECT COALESCE(SUM(total_pnl_usdt), 0) as pnl, COUNT(*) as count
                FROM trades WHERE status = 'closed'
                """
            )
        row = await cursor.fetchone()
        return (row["pnl"] or 0.0, row["count"] or 0) if row else (0.0, 0)

    async def get_statistics_for_period(
        self, start_date: str | None, end_date: str | None
    ) -> dict:
        """
        Get trading statistics for a date range.

        Args:
            start_date: Start date (YYYY-MM-DD) or None for all-time
            end_date: End date (YYYY-MM-DD) or None for all-time

        Returns:
            Dict with statistics: total_trades, win_rate, total_pnl, etc.
        """
        if start_date and end_date:
            cursor = await self.connection.execute(
                """
                SELECT total_pnl_usdt FROM trades
                WHERE status = 'closed' AND DATE(closed_at) BETWEEN ? AND ?
                """,
                (start_date, end_date),
            )
        else:
            cursor = await self.connection.execute(
                "SELECT total_pnl_usdt FROM trades WHERE status = 'closed'"
            )

        rows = await cursor.fetchall()
        pnls = [row["total_pnl_usdt"] or 0 for row in rows]

        if not pnls:
            return {
                "total_trades": 0,
                "win_rate": 0.0,
                "total_pnl": 0.0,
                "avg_win": 0.0,
                "avg_loss": 0.0,
                "best_trade": 0.0,
                "worst_trade": 0.0,
                "profit_factor": 0.0,
                "avg_trade": 0.0,
            }

        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]
        total_wins = sum(wins) if wins else 0
        total_losses = abs(sum(losses)) if losses else 0

        return {
            "total_trades": len(pnls),
            "win_rate": (len(wins) / len(pnls) * 100) if pnls else 0,
            "total_pnl": sum(pnls),
            "avg_win": (total_wins / len(wins)) if wins else 0,
            "avg_loss": (sum(losses) / len(losses)) if losses else 0,
            "best_trade": max(pnls) if pnls else 0,
            "worst_trade": min(pnls) if pnls else 0,
            "profit_factor": (total_wins / total_losses) if total_losses > 0 else total_wins,
            "avg_trade": (sum(pnls) / len(pnls)) if pnls else 0,
        }

    async def get_best_pairs_for_period(
        self, start_date: str | None, end_date: str | None, limit: int = 5
    ) -> list[dict]:
        """Get top profitable pairs for a date range."""
        if start_date and end_date:
            cursor = await self.connection.execute(
                """
                SELECT base || '/' || quote as pair,
                       SUM(total_pnl_usdt) as pnl,
                       COUNT(*) as trades
                FROM trades
                WHERE status = 'closed' AND DATE(closed_at) BETWEEN ? AND ?
                GROUP BY base, quote
                ORDER BY pnl DESC
                LIMIT ?
                """,
                (start_date, end_date, limit),
            )
        else:
            cursor = await self.connection.execute(
                """
                SELECT base || '/' || quote as pair,
                       SUM(total_pnl_usdt) as pnl,
                       COUNT(*) as trades
                FROM trades WHERE status = 'closed'
                GROUP BY base, quote
                ORDER BY pnl DESC
                LIMIT ?
                """,
                (limit,),
            )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def get_worst_pairs_for_period(
        self, start_date: str | None, end_date: str | None, limit: int = 5
    ) -> list[dict]:
        """Get top losing pairs for a date range."""
        if start_date and end_date:
            cursor = await self.connection.execute(
                """
                SELECT base || '/' || quote as pair,
                       SUM(total_pnl_usdt) as pnl,
                       COUNT(*) as trades
                FROM trades
                WHERE status = 'closed' AND DATE(closed_at) BETWEEN ? AND ?
                GROUP BY base, quote
                ORDER BY pnl ASC
                LIMIT ?
                """,
                (start_date, end_date, limit),
            )
        else:
            cursor = await self.connection.execute(
                """
                SELECT base || '/' || quote as pair,
                       SUM(total_pnl_usdt) as pnl,
                       COUNT(*) as trades
                FROM trades WHERE status = 'closed'
                GROUP BY base, quote
                ORDER BY pnl ASC
                LIMIT ?
                """,
                (limit,),
            )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def get_trades_for_period(
        self, start_date: str | None, end_date: str | None, limit: int = 50
    ) -> list[dict]:
        """Get closed trades for a date range."""
        if start_date and end_date:
            cursor = await self.connection.execute(
                """
                SELECT * FROM trades
                WHERE status = 'closed' AND DATE(closed_at) BETWEEN ? AND ?
                ORDER BY closed_at DESC
                LIMIT ?
                """,
                (start_date, end_date, limit),
            )
        else:
            cursor = await self.connection.execute(
                """
                SELECT * FROM trades
                WHERE status = 'closed'
                ORDER BY closed_at DESC
                LIMIT ?
                """,
                (limit,),
            )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def get_drawdown_for_period(
        self, start_date: str | None, end_date: str | None
    ) -> dict:
        """
        Calculate drawdown metrics for a date range.

        Returns:
            Dict with current_equity, peak, current_drawdown, max_drawdown,
            max_drawdown_percent, trade_count
        """
        if start_date and end_date:
            cursor = await self.connection.execute(
                """
                SELECT total_pnl_usdt, closed_at FROM trades
                WHERE status = 'closed' AND DATE(closed_at) BETWEEN ? AND ?
                ORDER BY closed_at ASC
                """,
                (start_date, end_date),
            )
        else:
            cursor = await self.connection.execute(
                """
                SELECT total_pnl_usdt, closed_at FROM trades
                WHERE status = 'closed'
                ORDER BY closed_at ASC
                """
            )

        rows = await cursor.fetchall()
        if not rows:
            return {
                "current_equity": 0.0,
                "peak": 0.0,
                "current_drawdown": 0.0,
                "max_drawdown": 0.0,
                "max_drawdown_percent": 0.0,
                "trade_count": 0,
            }

        equity = 0.0
        peak = 0.0
        max_dd = 0.0

        for row in rows:
            equity += row["total_pnl_usdt"] or 0
            if equity > peak:
                peak = equity
            dd = peak - equity
            if dd > max_dd:
                max_dd = dd

        current_dd = peak - equity
        max_dd_percent = (max_dd / peak * 100) if peak > 0 else 0

        return {
            "current_equity": equity,
            "peak": peak,
            "current_drawdown": current_dd,
            "max_drawdown": max_dd,
            "max_drawdown_percent": max_dd_percent,
            "trade_count": len(rows),
        }

    async def get_streak_for_period(
        self, start_date: str | None, end_date: str | None
    ) -> dict:
        """
        Calculate win/loss streaks for a date range.

        Returns:
            Dict with current, longest_win, longest_loss
        """
        if start_date and end_date:
            cursor = await self.connection.execute(
                """
                SELECT total_pnl_usdt FROM trades
                WHERE status = 'closed' AND DATE(closed_at) BETWEEN ? AND ?
                ORDER BY closed_at DESC
                """,
                (start_date, end_date),
            )
        else:
            cursor = await self.connection.execute(
                """
                SELECT total_pnl_usdt FROM trades
                WHERE status = 'closed'
                ORDER BY closed_at DESC
                """
            )

        rows = await cursor.fetchall()
        pnls = [row["total_pnl_usdt"] or 0 for row in rows]

        if not pnls:
            return {"current": 0, "longest_win": 0, "longest_loss": 0}

        # Current streak (from most recent)
        current = 0
        if pnls:
            is_win = pnls[0] > 0
            for pnl in pnls:
                if (pnl > 0) == is_win:
                    current += 1 if is_win else -1
                else:
                    break

        # Longest streaks (chronological order)
        reversed_pnls = list(reversed(pnls))
        longest_win = 0
        longest_loss = 0
        streak = 0
        prev_win = None

        for pnl in reversed_pnls:
            is_win = pnl > 0
            if prev_win is None or is_win == prev_win:
                streak += 1
            else:
                if prev_win:
                    longest_win = max(longest_win, streak)
                else:
                    longest_loss = max(longest_loss, streak)
                streak = 1
            prev_win = is_win

        # Check final streak
        if prev_win is not None:
            if prev_win:
                longest_win = max(longest_win, streak)
            else:
                longest_loss = max(longest_loss, streak)

        return {
            "current": current,
            "longest_win": longest_win,
            "longest_loss": longest_loss,
        }

    async def get_exchange_stats_for_period(
        self, start_date: str | None, end_date: str | None
    ) -> list[dict]:
        """Get PnL breakdown by exchange for a date range."""
        if start_date and end_date:
            cursor = await self.connection.execute(
                """
                SELECT exchange,
                       SUM(total_pnl_usdt) as pnl,
                       COUNT(*) as trades
                FROM trades
                WHERE status = 'closed' AND DATE(closed_at) BETWEEN ? AND ?
                GROUP BY exchange
                ORDER BY pnl DESC
                """,
                (start_date, end_date),
            )
        else:
            cursor = await self.connection.execute(
                """
                SELECT exchange,
                       SUM(total_pnl_usdt) as pnl,
                       COUNT(*) as trades
                FROM trades WHERE status = 'closed'
                GROUP BY exchange
                ORDER BY pnl DESC
                """
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
                datetime.now(UTC).isoformat(),
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

    # Group sequence methods
    async def get_next_group_sequence(
        self, base: str, exchange: str, timeframe: str
    ) -> int:
        """Get and increment the next sequence number for a pyramid group."""
        cursor = await self.connection.execute(
            """
            SELECT next_sequence FROM pyramid_group_sequences
            WHERE base = ? AND exchange = ? AND timeframe = ?
            """,
            (base, exchange, timeframe),
        )
        row = await cursor.fetchone()

        if row:
            seq = row["next_sequence"]
            # Increment for next use
            await self.connection.execute(
                """
                UPDATE pyramid_group_sequences
                SET next_sequence = ?, updated_at = ?
                WHERE base = ? AND exchange = ? AND timeframe = ?
                """,
                (seq + 1, datetime.utcnow().isoformat(), base, exchange, timeframe),
            )
        else:
            seq = 1
            await self.connection.execute(
                """
                INSERT INTO pyramid_group_sequences
                (base, exchange, timeframe, next_sequence, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (base, exchange, timeframe, 2, datetime.utcnow().isoformat()),
            )

        await self.connection.commit()
        return seq

    async def get_open_trade_by_group(
        self, exchange: str, base: str, quote: str, timeframe: str
    ) -> dict | None:
        """Get an open trade by exchange, symbol, and timeframe."""
        cursor = await self.connection.execute(
            """
            SELECT * FROM trades
            WHERE exchange = ? AND base = ? AND quote = ? AND timeframe = ? AND status = 'open'
            ORDER BY created_at DESC LIMIT 1
            """,
            (exchange, base, quote, timeframe),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def create_trade_with_group(
        self,
        trade_id: str,
        group_id: str,
        exchange: str,
        base: str,
        quote: str,
        timeframe: str,
        position_side: str = "long",
    ) -> None:
        """Create a new trade with group ID and timeframe."""
        await self.connection.execute(
            """
            INSERT INTO trades (id, group_id, exchange, base, quote, timeframe,
                                position_side, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'open', ?)
            """,
            (
                trade_id,
                group_id,
                exchange,
                base,
                quote,
                timeframe,
                position_side,
                datetime.utcnow().isoformat(),
            ),
        )
        await self.connection.commit()

    # Capital setting methods (per exchange/pair/timeframe/pyramid)
    # Global default capital when no specific setting exists
    DEFAULT_CAPITAL_USD = 1000.0

    def _make_capital_key(
        self, exchange: str, base: str, quote: str, timeframe: str, pyramid_index: int
    ) -> str:
        """Generate composite key for capital storage."""
        return f"{exchange}:{base}/{quote}:{timeframe}:{pyramid_index}"

    async def get_pyramid_capital(
        self,
        pyramid_index: int,
        exchange: str,
        base: str,
        quote: str,
        timeframe: str,
    ) -> float:
        """
        Get capital setting for a specific pyramid.

        Returns exact match or global default (1000 USDT).
        """
        import json
        value = await self.get_setting("pyramid_capitals")

        if value:
            try:
                capitals = json.loads(value)
                key = self._make_capital_key(exchange, base, quote, timeframe, pyramid_index)
                if key in capitals:
                    return capitals[key]
            except (json.JSONDecodeError, ValueError):
                pass

        # Return global default
        return self.DEFAULT_CAPITAL_USD

    async def get_all_pyramid_capitals(self) -> dict[str, float]:
        """Get all pyramid capital settings. Returns dict of {key: capital}."""
        import json
        value = await self.get_setting("pyramid_capitals")
        if value:
            try:
                return json.loads(value)
            except (json.JSONDecodeError, ValueError):
                return {}
        return {}

    async def set_pyramid_capital(
        self,
        pyramid_index: int,
        capital: float | None,
        exchange: str,
        base: str,
        quote: str,
        timeframe: str,
    ) -> str:
        """
        Set or clear capital for a specific pyramid configuration.

        Returns the key that was set/cleared.
        Key format: exchange:pair:timeframe:index
        """
        import json

        key = self._make_capital_key(exchange, base, quote, timeframe, pyramid_index)

        value = await self.get_setting("pyramid_capitals")
        if value:
            try:
                capitals = json.loads(value)
            except json.JSONDecodeError:
                capitals = {}
        else:
            capitals = {}

        if capital is None:
            capitals.pop(key, None)
        else:
            capitals[key] = capital

        if capitals:
            await self.set_setting("pyramid_capitals", json.dumps(capitals))
        else:
            await self.connection.execute(
                "DELETE FROM settings WHERE key = 'pyramid_capitals'"
            )
            await self.connection.commit()

        return key

    async def clear_all_pyramid_capitals(self) -> None:
        """Clear all pyramid capital settings."""
        await self.connection.execute(
            "DELETE FROM settings WHERE key = 'pyramid_capitals'"
        )
        await self.connection.commit()

    # =========== Data Reset Methods ===========

    async def reset_trades(self) -> dict:
        """Clear all trade data (trades, pyramids, exits, sequences)."""
        counts = {}

        # Count before deletion
        cursor = await self.connection.execute("SELECT COUNT(*) FROM trades")
        counts["trades"] = (await cursor.fetchone())[0]

        cursor = await self.connection.execute("SELECT COUNT(*) FROM pyramids")
        counts["pyramids"] = (await cursor.fetchone())[0]

        cursor = await self.connection.execute("SELECT COUNT(*) FROM exits")
        counts["exits"] = (await cursor.fetchone())[0]

        # Delete in order (child tables first)
        await self.connection.execute("DELETE FROM pyramids")
        await self.connection.execute("DELETE FROM exits")
        await self.connection.execute("DELETE FROM trades")
        await self.connection.execute("DELETE FROM pyramid_group_sequences")
        await self.connection.execute("DELETE FROM processed_alerts")
        await self.connection.commit()

        return counts

    async def reset_settings(self) -> dict:
        """Clear all settings (capital configs, etc.)."""
        cursor = await self.connection.execute("SELECT COUNT(*) FROM settings")
        count = (await cursor.fetchone())[0]

        await self.connection.execute("DELETE FROM settings")
        await self.connection.commit()

        return {"settings": count}

    async def reset_cache(self) -> dict:
        """Clear cached data (symbol rules, daily reports)."""
        counts = {}

        cursor = await self.connection.execute("SELECT COUNT(*) FROM symbol_rules")
        counts["symbol_rules"] = (await cursor.fetchone())[0]

        cursor = await self.connection.execute("SELECT COUNT(*) FROM daily_reports")
        counts["daily_reports"] = (await cursor.fetchone())[0]

        await self.connection.execute("DELETE FROM symbol_rules")
        await self.connection.execute("DELETE FROM daily_reports")
        await self.connection.commit()

        return counts

    async def reset_all(self) -> dict:
        """Full database reset - clears everything."""
        counts = {}
        counts.update(await self.reset_trades())
        counts.update(await self.reset_settings())
        counts.update(await self.reset_cache())
        return counts


# Global database instance
db = Database()
