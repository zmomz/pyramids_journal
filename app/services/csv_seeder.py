"""
CSV Seeder Service

Parses TradingView alert CSV exports and seeds missing trades into the database.
Handles two scenarios:
1. Exit signals for stuck open trades
2. Full trade reconstruction for completely missing signals
"""

import csv
import json
import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, UTC, timezone
from io import StringIO
from pathlib import Path

from ..config import exchange_config
from ..database import db
from .symbol_normalizer import normalize_exchange, parse_symbol
from .trade_service import generate_group_id

logger = logging.getLogger(__name__)


@dataclass
class ParsedSignal:
    """Represents a parsed signal from CSV."""
    alert_id: str
    timestamp: datetime
    exchange: str
    symbol: str
    base: str
    quote: str
    timeframe: str
    action: str  # "buy" or "sell"
    order_id: str
    contracts: float
    close_price: float
    position_side: str  # "long" or "flat"
    position_qty: float

    def is_entry(self) -> bool:
        """Check if this is an entry signal."""
        return self.action == "buy" and self.position_side == "long"

    def is_exit(self) -> bool:
        """Check if this is an exit signal."""
        return self.action == "sell" and self.position_side == "flat"


@dataclass
class SeedResult:
    """Results of a seeding operation."""
    total_signals: int = 0
    entries_found: int = 0
    exits_found: int = 0
    exits_processed: int = 0
    entries_reconstructed: int = 0
    trades_created: int = 0
    skipped_no_match: int = 0
    skipped_already_closed: int = 0
    skipped_already_exists: int = 0
    errors: list = field(default_factory=list)


class CSVSeeder:
    """Service for seeding trades from TradingView CSV exports."""

    def __init__(self, cutoff_date: datetime | None = None):
        """
        Args:
            cutoff_date: Only process signals after this date (for filtering)
        """
        self.cutoff_date = cutoff_date

    def parse_csv(self, csv_path: str) -> list[ParsedSignal]:
        """Parse CSV file and extract all signals."""
        signals = []
        path = Path(csv_path)

        if not path.exists():
            raise FileNotFoundError(f"CSV file not found: {csv_path}")

        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Parse using custom logic due to multiline JSON in Description
        signals = self._parse_csv_content(content)

        # Filter by cutoff date if specified
        if self.cutoff_date:
            cutoff = self.cutoff_date
            if cutoff.tzinfo is None:
                cutoff = cutoff.replace(tzinfo=timezone.utc)
            signals = [s for s in signals if s.timestamp >= cutoff]

        # Sort by timestamp (chronological order for processing)
        signals.sort(key=lambda s: s.timestamp)

        return signals

    def _parse_csv_content(self, content: str) -> list[ParsedSignal]:
        """Parse CSV content handling multiline JSON in Description."""
        signals = []

        # Split content by lines first, then reconstruct rows
        lines = content.split('\n')

        # Skip header
        if lines and 'Alert ID' in lines[0]:
            lines = lines[1:]

        # Accumulate lines until we have a complete JSON object
        current_row = []
        json_depth = 0
        in_json = False

        for line in lines:
            if not line.strip():
                continue

            # Check if this is a new row (starts with a number - Alert ID)
            if re.match(r'^\d{10},', line) and not in_json:
                # Process previous row if exists
                if current_row:
                    signal = self._parse_row('\n'.join(current_row))
                    if signal:
                        signals.append(signal)
                current_row = [line]
                json_depth = line.count('{') - line.count('}')
                in_json = json_depth > 0
            else:
                current_row.append(line)
                json_depth += line.count('{') - line.count('}')
                in_json = json_depth > 0

        # Process last row
        if current_row:
            signal = self._parse_row('\n'.join(current_row))
            if signal:
                signals.append(signal)

        return signals

    def _parse_row(self, row_content: str) -> ParsedSignal | None:
        """Parse a single CSV row into a ParsedSignal."""
        try:
            # Extract Alert ID (first field)
            alert_match = re.match(r'^(\d+),', row_content)
            if not alert_match:
                return None
            alert_id = alert_match.group(1)

            # Extract JSON from the row (between first { and last })
            json_start = row_content.find('{')
            json_end = row_content.rfind('}')
            if json_start == -1 or json_end == -1:
                return None

            json_str = row_content[json_start:json_end + 1]

            # Clean up CSV escaping (double quotes become single)
            json_str = json_str.replace('""', '"')

            # Remove any surrounding quotes if present
            json_str = json_str.strip('"')

            # Parse JSON
            data = json.loads(json_str)

            # Normalize exchange
            exchange = normalize_exchange(data.get('exchange', ''))
            if not exchange:
                logger.debug(f"Unknown exchange in alert {alert_id}: {data.get('exchange')}")
                return None

            # Parse symbol
            try:
                parsed = parse_symbol(data.get('symbol', ''))
            except ValueError as e:
                logger.debug(f"Invalid symbol in alert {alert_id}: {e}")
                return None

            # Parse timestamp
            timestamp_str = data.get('timestamp', '')
            if timestamp_str.endswith('Z'):
                timestamp_str = timestamp_str[:-1] + '+00:00'
            timestamp = datetime.fromisoformat(timestamp_str)

            return ParsedSignal(
                alert_id=alert_id,
                timestamp=timestamp,
                exchange=exchange,
                symbol=data.get('symbol', ''),
                base=parsed.base,
                quote=parsed.quote,
                timeframe=data.get('timeframe', ''),
                action=data.get('action', '').lower(),
                order_id=data.get('order_id', ''),
                contracts=float(data.get('contracts', 0)),
                close_price=float(data.get('close', 0)),
                position_side=data.get('position_side', ''),
                position_qty=float(data.get('position_qty', 0))
            )

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"Failed to parse row: {e}")
            return None

    async def seed(
        self,
        csv_path: str,
        dry_run: bool = True,
        process_exits: bool = True,
        process_entries: bool = True
    ) -> SeedResult:
        """
        Seed missing trades from CSV.

        Args:
            csv_path: Path to the TradingView CSV export
            dry_run: If True, only report what would be done
            process_exits: Process exit signals for stuck open trades
            process_entries: Reconstruct missing entry signals

        Returns:
            SeedResult with counts and any errors
        """
        result = SeedResult()

        # Parse all signals
        signals = self.parse_csv(csv_path)
        result.total_signals = len(signals)
        logger.info(f"Parsed {len(signals)} signals from CSV")

        # Separate entries and exits
        entries = [s for s in signals if s.is_entry()]
        exits = [s for s in signals if s.is_exit()]

        result.entries_found = len(entries)
        result.exits_found = len(exits)
        logger.info(f"Found {len(entries)} entry signals, {len(exits)} exit signals")

        # Phase 1: Process exits for stuck open trades
        if process_exits:
            logger.info("Phase 1: Processing exit signals for stuck open trades...")
            for exit_signal in exits:
                try:
                    status = await self._process_exit_signal(exit_signal, dry_run)
                    if status == "processed":
                        result.exits_processed += 1
                    elif status == "no_match":
                        result.skipped_no_match += 1
                    elif status == "already_closed":
                        result.skipped_already_closed += 1
                except Exception as e:
                    error_msg = f"Exit {exit_signal.alert_id} ({exit_signal.base}/{exit_signal.quote}): {e}"
                    result.errors.append(error_msg)
                    logger.error(error_msg)

        # Phase 2: Reconstruct missing trades
        if process_entries:
            logger.info("Phase 2: Reconstructing missing trades...")
            # Group entries by trade key (exchange, base, quote, timeframe)
            trade_groups = self._group_signals_by_trade(entries, exits)

            for trade_key, trade_signals in trade_groups.items():
                try:
                    status = await self._reconstruct_trade(
                        trade_key, trade_signals, dry_run
                    )
                    if status == "created":
                        result.trades_created += 1
                        result.entries_reconstructed += len(trade_signals['entries'])
                    elif status == "exists":
                        result.skipped_already_exists += 1
                except Exception as e:
                    error_msg = f"Trade {trade_key}: {e}"
                    result.errors.append(error_msg)
                    logger.error(error_msg)

        return result

    async def _process_exit_signal(
        self,
        signal: ParsedSignal,
        dry_run: bool
    ) -> str:
        """
        Process an exit signal for a stuck open trade.

        Returns:
            "processed" if exit was added
            "no_match" if no matching open trade
            "already_closed" if trade already has exit
        """
        # Find matching open trade
        trade = await db.get_open_trade_by_group(
            signal.exchange, signal.base, signal.quote, signal.timeframe
        )

        if not trade:
            logger.debug(
                f"No open trade for {signal.base}/{signal.quote} "
                f"({signal.timeframe}) on {signal.exchange}"
            )
            return "no_match"

        trade_id = trade['id']
        group_id = trade.get('group_id', trade_id[:8])

        # Check if exit already exists
        if await db.has_exit(trade_id):
            logger.debug(f"Trade {group_id} already has exit record")
            return "already_closed"

        # Get pyramids for PnL calculation
        pyramids = await db.get_pyramids_for_trade(trade_id)
        if not pyramids:
            logger.warning(f"Trade {group_id} has no pyramids")
            return "no_match"

        # Use close price from CSV as exit price
        exit_price = signal.close_price

        if dry_run:
            logger.info(
                f"[DRY RUN] Would close trade {group_id} at ${exit_price:.6f} "
                f"({len(pyramids)} pyramids)"
            )
            return "processed"

        # Calculate PnL for each pyramid
        fee_rate = exchange_config.get_fee_rate(signal.exchange)
        total_gross_pnl = 0.0
        total_entry_fees = 0.0
        total_exit_fees = 0.0
        total_capital = 0.0

        for pyramid in pyramids:
            entry_price = pyramid['entry_price']
            size = pyramid['position_size']
            capital = pyramid['capital_usdt']

            # PnL calculation (LONG only)
            gross_pnl = (exit_price - entry_price) * size
            entry_fee = pyramid['fee_usdt']
            exit_fee = exit_price * size * fee_rate
            net_pnl = gross_pnl - entry_fee - exit_fee
            pnl_percent = (net_pnl / capital) * 100 if capital > 0 else 0

            # Update pyramid PnL
            await db.update_pyramid_pnl(pyramid['id'], net_pnl, pnl_percent)

            total_gross_pnl += gross_pnl
            total_entry_fees += entry_fee
            total_exit_fees += exit_fee
            total_capital += capital

        # Calculate totals
        total_fees = total_entry_fees + total_exit_fees
        total_net_pnl = total_gross_pnl - total_fees
        total_pnl_percent = (total_net_pnl / total_capital) * 100 if total_capital > 0 else 0

        # Add exit record
        exit_id = str(uuid.uuid4())
        await db.add_exit(
            exit_id=exit_id,
            trade_id=trade_id,
            exit_price=exit_price,
            fee_usdt=total_exit_fees,
            exchange_timestamp=signal.timestamp.isoformat(),
            received_timestamp=datetime.now(UTC).isoformat(),
        )

        # Close trade
        await db.close_trade(trade_id, total_net_pnl, total_pnl_percent)

        logger.info(
            f"Closed trade {group_id}: {len(pyramids)} pyramids, "
            f"exit @ ${exit_price:.6f}, net PnL: ${total_net_pnl:.2f}"
        )

        return "processed"

    def _group_signals_by_trade(
        self,
        entries: list[ParsedSignal],
        exits: list[ParsedSignal]
    ) -> dict:
        """Group signals by trade key for reconstruction."""
        groups = {}

        # Build trade key -> signals mapping
        for signal in entries + exits:
            key = (signal.exchange, signal.base, signal.quote, signal.timeframe)
            if key not in groups:
                groups[key] = {'entries': [], 'exits': []}

            if signal.is_entry():
                groups[key]['entries'].append(signal)
            else:
                groups[key]['exits'].append(signal)

        return groups

    async def _reconstruct_trade(
        self,
        trade_key: tuple,
        signals: dict,
        dry_run: bool
    ) -> str:
        """
        Reconstruct a completely missing trade from CSV signals.

        Returns:
            "created" if trade was created
            "exists" if trade already exists
        """
        exchange, base, quote, timeframe = trade_key
        entries = signals['entries']
        exits = signals['exits']

        if not entries:
            return "exists"

        # Check if any open trade exists for this combination
        existing = await db.get_open_trade_by_group(exchange, base, quote, timeframe)
        if existing:
            logger.debug(
                f"Open trade for {base}/{quote} ({timeframe}) already exists, skipping"
            )
            return "exists"

        # Check if a closed trade exists with similar timing (within 1 hour)
        first_entry = entries[0]
        existing_closed = await self._find_existing_closed_trade(
            exchange, base, quote, timeframe, first_entry.timestamp
        )
        if existing_closed:
            logger.debug(
                f"Closed trade for {base}/{quote} ({timeframe}) already exists near {first_entry.timestamp}, skipping"
            )
            return "exists"

        if dry_run:
            pnl_estimate = 0.0
            if exits:
                exit_price = exits[0].close_price
                for entry in entries:
                    entry_price = entry.close_price
                    # Rough estimate using $1000 capital
                    size = 1000 / entry_price
                    pnl_estimate += (exit_price - entry_price) * size

            logger.info(
                f"[DRY RUN] Would create trade for {base}/{quote} ({timeframe}) "
                f"with {len(entries)} pyramid(s), estimated PnL: ${pnl_estimate:.2f}"
            )
            return "created"

        # Create trade
        trade_id = str(uuid.uuid4())
        sequence = await db.get_next_group_sequence(base, exchange, timeframe)
        group_id = generate_group_id(base, exchange, timeframe, sequence)

        await db.create_trade_with_group(
            trade_id=trade_id,
            group_id=group_id,
            exchange=exchange,
            base=base,
            quote=quote,
            timeframe=timeframe,
            position_side="long"
        )

        # Add pyramids (entries)
        fee_rate = exchange_config.get_fee_rate(exchange)

        for idx, entry in enumerate(entries):
            # Use close price as entry price (historical price unavailable)
            entry_price = entry.close_price

            # Get capital for this pyramid
            capital_usdt = await db.get_pyramid_capital(
                idx, exchange=exchange, base=base, quote=quote, timeframe=timeframe
            )
            position_size = capital_usdt / entry_price
            fee_usdt = capital_usdt * fee_rate

            pyramid_id = str(uuid.uuid4())
            await db.add_pyramid(
                pyramid_id=pyramid_id,
                trade_id=trade_id,
                pyramid_index=idx,
                entry_price=entry_price,
                position_size=position_size,
                capital_usdt=capital_usdt,
                fee_rate=fee_rate,
                fee_usdt=fee_usdt,
                exchange_timestamp=entry.timestamp.isoformat(),
                received_timestamp=datetime.now(UTC).isoformat(),
            )

        logger.info(
            f"Created trade {group_id} with {len(entries)} pyramid(s) [SEEDED FROM CSV]"
        )

        # Process exit if available
        if exits:
            exit_signal = exits[0]  # Use first exit
            # Create a temporary signal with the trade's timeframe to ensure match
            await self._close_trade_directly(
                trade_id, group_id, exit_signal, fee_rate
            )

        return "created"

    async def _find_existing_closed_trade(
        self,
        exchange: str,
        base: str,
        quote: str,
        timeframe: str,
        timestamp: datetime
    ) -> dict | None:
        """Find existing closed trade near the given timestamp."""
        # Query closed trades for this symbol/timeframe within 2 hours of timestamp
        from datetime import timedelta

        start_time = (timestamp - timedelta(hours=2)).isoformat()
        end_time = (timestamp + timedelta(hours=2)).isoformat()

        cursor = await db.connection.execute(
            """
            SELECT * FROM trades
            WHERE exchange = ? AND base = ? AND quote = ? AND timeframe = ?
              AND status = 'closed'
              AND created_at BETWEEN ? AND ?
            LIMIT 1
            """,
            (exchange, base, quote, timeframe, start_time, end_time)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def _close_trade_directly(
        self,
        trade_id: str,
        group_id: str,
        exit_signal: ParsedSignal,
        fee_rate: float
    ) -> None:
        """Close a trade directly (used after reconstruction)."""
        pyramids = await db.get_pyramids_for_trade(trade_id)
        exit_price = exit_signal.close_price

        total_gross_pnl = 0.0
        total_entry_fees = 0.0
        total_exit_fees = 0.0
        total_capital = 0.0

        for pyramid in pyramids:
            entry_price = pyramid['entry_price']
            size = pyramid['position_size']
            capital = pyramid['capital_usdt']

            gross_pnl = (exit_price - entry_price) * size
            entry_fee = pyramid['fee_usdt']
            exit_fee = exit_price * size * fee_rate
            net_pnl = gross_pnl - entry_fee - exit_fee
            pnl_percent = (net_pnl / capital) * 100 if capital > 0 else 0

            await db.update_pyramid_pnl(pyramid['id'], net_pnl, pnl_percent)

            total_gross_pnl += gross_pnl
            total_entry_fees += entry_fee
            total_exit_fees += exit_fee
            total_capital += capital

        total_fees = total_entry_fees + total_exit_fees
        total_net_pnl = total_gross_pnl - total_fees
        total_pnl_percent = (total_net_pnl / total_capital) * 100 if total_capital > 0 else 0

        exit_id = str(uuid.uuid4())
        await db.add_exit(
            exit_id=exit_id,
            trade_id=trade_id,
            exit_price=exit_price,
            fee_usdt=total_exit_fees,
            exchange_timestamp=exit_signal.timestamp.isoformat(),
            received_timestamp=datetime.now(UTC).isoformat(),
        )

        await db.close_trade(trade_id, total_net_pnl, total_pnl_percent)

        logger.info(
            f"Closed seeded trade {group_id}: exit @ ${exit_price:.6f}, "
            f"net PnL: ${total_net_pnl:.2f}"
        )


# Singleton instance
csv_seeder = CSVSeeder()
