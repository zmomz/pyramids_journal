"""
Trade Service

Core business logic for handling pyramid entries and exits.
"""

import logging
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime, UTC
from typing import Any

from ..config import settings, exchange_config
from ..database import db
from ..models import TradingViewAlert, TradeClosedData, PyramidEntryData
from .exchange_service import exchange_service
from .symbol_normalizer import normalize_exchange, parse_symbol, ParsedSymbol

logger = logging.getLogger(__name__)


def generate_group_id(base: str, exchange: str, timeframe: str, sequence: int) -> str:
    """
    Generate human-readable pyramid group ID.
    Format: {BASE}_{Exchange}_{Timeframe}_{SequentialNumber}
    Example: ETH_Kucoin_1h_001
    """
    exchange_formatted = exchange.capitalize()
    seq_formatted = f"{sequence:03d}"
    return f"{base}_{exchange_formatted}_{timeframe}_{seq_formatted}"


@dataclass
class TradeResult:
    """Result of a trade operation."""
    success: bool
    message: str
    trade_id: str | None = None
    group_id: str | None = None
    price: float | None = None
    error: str | None = None
    entry_data: PyramidEntryData | None = None


class TradeService:
    """Service for managing trades and pyramids."""

    @classmethod
    async def process_signal(
        cls, alert: TradingViewAlert
    ) -> tuple[TradeResult, Any]:
        """
        Process a TradingView signal (entry or exit).

        Args:
            alert: TradingView alert with new payload structure

        Returns:
            Tuple of (TradeResult, notification_data)
            - For entry: notification_data is PyramidEntryData
            - For exit: notification_data is TradeClosedData
            - For ignored: notification_data is None
        """
        received_timestamp = datetime.now(UTC)

        # Idempotency check disabled - process all signals regardless of order_id
        # if await db.is_alert_processed(alert.order_id):
        #     logger.info(f"Alert {alert.order_id} already processed, skipping")
        #     return TradeResult(
        #         success=True,
        #         message="Alert already processed",
        #     ), None

        # Normalize exchange and parse symbol
        exchange = normalize_exchange(alert.exchange)
        if not exchange:
            return TradeResult(
                success=False,
                message=f"Unknown exchange: {alert.exchange}",
                error="UNKNOWN_EXCHANGE",
            ), None

        try:
            parsed = parse_symbol(alert.symbol)
        except ValueError as e:
            return TradeResult(
                success=False,
                message=str(e),
                error="INVALID_SYMBOL",
            ), None

        # Determine if entry or exit
        if alert.is_entry():
            logger.info(f"Processing ENTRY signal for {parsed.base}/{parsed.quote} on {exchange}")
            return await cls._process_entry(
                alert, exchange, parsed, received_timestamp
            )
        elif alert.is_exit():
            logger.info(f"Processing EXIT signal for {parsed.base}/{parsed.quote} on {exchange}")
            return await cls._process_exit(
                alert, exchange, parsed, received_timestamp
            )
        else:
            # Neither clear entry nor exit - log and skip
            logger.info(
                f"Ambiguous signal ignored: action={alert.action}, "
                f"position_side={alert.position_side}"
            )
            await db.mark_alert_processed(alert.order_id)
            return TradeResult(
                success=True,
                message="Signal ignored (not a clear entry/exit)",
            ), None

    @classmethod
    async def _process_entry(
        cls,
        alert: TradingViewAlert,
        exchange: str,
        parsed: ParsedSymbol,
        received_timestamp: datetime,
    ) -> tuple[TradeResult, PyramidEntryData | None]:
        """Process an entry signal."""

        # Use price from TradingView payload
        current_price = alert.close
        logger.info(f"Using price from payload: ${current_price}")

        # Check for existing trade (but don't create yet - validate first)
        trade = await db.get_open_trade_by_group(
            exchange, parsed.base, parsed.quote, alert.timeframe
        )

        if trade:
            trade_id = trade["id"]
            group_id = trade["group_id"]
            existing_pyramids = await db.get_pyramids_for_trade(trade_id)
            pyramid_index = len(existing_pyramids)
            is_new_trade = False

            # Enforce pyramid limit
            if pyramid_index >= settings.max_pyramids:
                logger.warning(
                    f"Max pyramids ({settings.max_pyramids}) reached for {group_id}"
                )
                # Notify via Telegram
                from .error_notifier import error_notifier

                await error_notifier.notify_pyramid_limit(
                    pair=f"{parsed.base}/{parsed.quote}",
                    exchange=exchange,
                    current_pyramids=pyramid_index,
                    max_pyramids=settings.max_pyramids,
                )
                return TradeResult(
                    success=False,
                    message=f"Maximum {settings.max_pyramids} pyramids reached for {group_id}",
                    error="MAX_PYRAMIDS_REACHED",
                ), None
        else:
            # Prepare new trade info but don't create until validation passes
            sequence = await db.get_next_group_sequence(
                parsed.base, exchange, alert.timeframe
            )
            group_id = generate_group_id(
                parsed.base, exchange, alert.timeframe, sequence
            )
            trade_id = str(uuid.uuid4())
            pyramid_index = 0
            is_new_trade = True

        # Get capital setting for this specific pyramid (exact match or default $1000)
        capital_usd = await db.get_pyramid_capital(
            pyramid_index,
            exchange=exchange,
            base=parsed.base,
            quote=parsed.quote,
            timeframe=alert.timeframe,
        )

        # Get symbol info for precision rounding
        try:
            symbol_info = await exchange_service.get_symbol_info(
                exchange, parsed.base, parsed.quote
            )
            qty_precision = symbol_info.qty_precision
        except Exception as e:
            logger.warning(f"Could not get symbol info for precision: {e}, using default 4")
            qty_precision = 4

        # Calculate position size from capital / price, rounded to exchange precision
        position_size = capital_usd / current_price
        position_size = exchange_service.round_quantity(position_size, qty_precision)
        notional = position_size * current_price  # Actual notional after rounding
        logger.info(
            f"Using capital for Pyramid #{pyramid_index}: ${capital_usd} -> "
            f"{position_size} {parsed.base} (precision: {qty_precision})"
        )

        # Validate order BEFORE creating trade (prevents orphan trades with 0 pyramids)
        if settings.validation_mode == "strict":
            is_valid, error_msg = await exchange_service.validate_order(
                exchange, parsed.base, parsed.quote, position_size, current_price
            )
            if not is_valid:
                logger.warning(f"Order validation failed: {error_msg}")
                return TradeResult(
                    success=False,
                    message=error_msg,
                    error="VALIDATION_FAILED",
                ), None

        # NOW create trade if it's new (validation passed)
        if is_new_trade:
            try:
                await db.create_trade_with_group(
                    trade_id=trade_id,
                    group_id=group_id,
                    exchange=exchange,
                    base=parsed.base,
                    quote=parsed.quote,
                    timeframe=alert.timeframe,
                    position_side=alert.position_side,
                )
                logger.info(f"Created new trade {trade_id} with group {group_id}")
            except sqlite3.IntegrityError:
                # Race condition: another request created the trade first
                # Re-fetch the existing trade and add pyramid to it
                logger.warning(
                    f"Race condition detected for {parsed.base}/{parsed.quote} "
                    f"({alert.timeframe}), adding to existing trade"
                )
                trade = await db.get_open_trade_by_group(
                    exchange, parsed.base, parsed.quote, alert.timeframe
                )
                if not trade:
                    # Extremely rare: trade was created and closed between our attempts
                    return TradeResult(
                        success=False,
                        message="Race condition: trade created and closed by another request",
                        error="RACE_CONDITION",
                    ), None
                trade_id = trade["id"]
                group_id = trade["group_id"]
                existing_pyramids = await db.get_pyramids_for_trade(trade_id)
                pyramid_index = len(existing_pyramids)

        # Calculate fees
        fee_rate = exchange_config.get_fee_rate(exchange)
        fee_usdt = notional * fee_rate

        # Add pyramid with timestamps
        pyramid_id = str(uuid.uuid4())
        await db.add_pyramid(
            pyramid_id=pyramid_id,
            trade_id=trade_id,
            pyramid_index=pyramid_index,
            entry_price=current_price,
            position_size=position_size,
            capital_usdt=notional,  # Actual capital after precision rounding
            fee_rate=fee_rate,
            fee_usdt=fee_usdt,
            exchange_timestamp=alert.timestamp,
            received_timestamp=received_timestamp.isoformat(),
        )

        # Mark alert as processed
        await db.mark_alert_processed(alert.order_id)

        # Prepare entry notification data
        entry_data = PyramidEntryData(
            group_id=group_id,
            pyramid_index=pyramid_index,
            exchange=exchange,
            base=parsed.base,
            quote=parsed.quote,
            timeframe=alert.timeframe,
            entry_price=current_price,
            position_size=position_size,
            capital_usdt=notional,  # Actual capital after precision rounding
            exchange_timestamp=alert.timestamp,
            received_timestamp=received_timestamp,
            total_pyramids=pyramid_index + 1,
        )

        logger.info(
            f"Recorded pyramid {pyramid_index} for group {group_id}: "
            f"{position_size:.6f} {parsed.base} @ ${current_price:.2f}"
        )

        return TradeResult(
            success=True,
            message=f"Pyramid {pyramid_index} recorded",
            trade_id=trade_id,
            group_id=group_id,
            price=current_price,
            entry_data=entry_data,
        ), entry_data

    @classmethod
    async def _process_exit(
        cls,
        alert: TradingViewAlert,
        exchange: str,
        parsed: ParsedSymbol,
        received_timestamp: datetime,
    ) -> tuple[TradeResult, TradeClosedData | None]:
        """Process an exit signal."""

        # Find open trade (timeframe-aware)
        trade = await db.get_open_trade_by_group(
            exchange, parsed.base, parsed.quote, alert.timeframe
        )

        if not trade:
            logger.warning(
                f"Exit signal ignored: No open trade for {parsed.base}/{parsed.quote} "
                f"({alert.timeframe}) on {exchange}"
            )
            return TradeResult(
                success=False,
                message=(
                    f"No open trade for {parsed.base}/{parsed.quote} "
                    f"({alert.timeframe}) on {exchange}"
                ),
                error="NO_OPEN_TRADE",
            ), None

        trade_id = trade["id"]
        group_id = trade.get("group_id") or trade_id[:8]
        timeframe = trade.get("timeframe") or alert.timeframe

        # Get all pyramids
        pyramids = await db.get_pyramids_for_trade(trade_id)
        if not pyramids:
            return TradeResult(
                success=False,
                message="No pyramids found for trade",
                error="NO_PYRAMIDS",
            ), None

        # Use price from TradingView payload
        exit_price = alert.close
        logger.info(f"Using exit price from payload: ${exit_price}")

        # Calculate PnL for each pyramid
        fee_rate = exchange_config.get_fee_rate(exchange)
        total_gross_pnl = 0.0
        total_entry_fees = 0.0
        total_exit_fees = 0.0
        total_capital = 0.0
        pyramid_details = []

        for pyramid in pyramids:
            entry_price = pyramid["entry_price"]
            size = pyramid["position_size"]
            capital = pyramid["capital_usdt"]

            # Calculate PnL (LONG only)
            gross_pnl = (exit_price - entry_price) * size
            entry_fee = pyramid["fee_usdt"]
            exit_fee = exit_price * size * fee_rate
            net_pnl = gross_pnl - entry_fee - exit_fee
            pnl_percent = (net_pnl / capital) * 100 if capital > 0 else 0

            # Update pyramid PnL
            await db.update_pyramid_pnl(pyramid["id"], net_pnl, pnl_percent)

            total_gross_pnl += gross_pnl
            total_entry_fees += entry_fee
            total_exit_fees += exit_fee
            total_capital += capital

            pyramid_details.append({
                "index": pyramid["pyramid_index"],
                "entry_price": entry_price,
                "entry_time": pyramid["entry_time"],
                "exchange_timestamp": pyramid.get("exchange_timestamp", ""),
                "size": size,
                "pnl_usdt": net_pnl,
                "pnl_percent": pnl_percent,
            })

        # Calculate total PnL
        total_fees = total_entry_fees + total_exit_fees
        total_net_pnl = total_gross_pnl - total_fees
        total_pnl_percent = (
            (total_net_pnl / total_capital) * 100 if total_capital > 0 else 0
        )

        # Add exit record with timestamps (returns False if race condition detected)
        exit_id = str(uuid.uuid4())
        exit_added = await db.add_exit(
            exit_id,
            trade_id,
            exit_price,
            total_exit_fees,
            exchange_timestamp=alert.timestamp,
            received_timestamp=received_timestamp.isoformat(),
        )

        if not exit_added:
            # Race condition: another request already closed this trade
            logger.warning(
                f"Race condition detected: trade {group_id} already has exit record, "
                f"skipping duplicate exit signal"
            )
            return TradeResult(
                success=True,
                message="Trade already closed by another request (duplicate signal)",
            ), None

        # Close trade
        await db.close_trade(trade_id, total_net_pnl, total_pnl_percent)

        # Mark alert as processed
        await db.mark_alert_processed(alert.order_id)

        logger.info(
            f"Closed trade {group_id}: {len(pyramids)} pyramids, "
            f"exit @ ${exit_price:.2f}, net PnL: ${total_net_pnl:.2f}"
        )

        # Prepare notification data
        closed_data = TradeClosedData(
            trade_id=trade_id,
            group_id=group_id,
            exchange=exchange,
            base=parsed.base,
            quote=parsed.quote,
            timeframe=timeframe,
            pyramids=pyramid_details,
            exit_price=exit_price,
            exit_time=received_timestamp,
            gross_pnl=total_gross_pnl,
            total_fees=total_fees,
            net_pnl=total_net_pnl,
            net_pnl_percent=total_pnl_percent,
            exchange_timestamp=alert.timestamp,
            received_timestamp=received_timestamp,
        )

        return TradeResult(
            success=True,
            message=f"Trade closed with {len(pyramids)} pyramids",
            trade_id=trade_id,
            group_id=group_id,
            price=exit_price,
        ), closed_data

    @classmethod
    async def get_trade_summary(cls, trade_id: str) -> dict | None:
        """Get full trade details with all pyramids."""
        return await db.get_trade_with_pyramids(trade_id)


# Singleton instance
trade_service = TradeService()
