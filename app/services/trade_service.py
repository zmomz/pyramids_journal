"""
Trade Service

Core business logic for handling pyramid entries and exits.
"""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
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
        received_timestamp = datetime.utcnow()

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
            return await cls._process_entry(
                alert, exchange, parsed, received_timestamp
            )
        elif alert.is_exit():
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

        # Fetch actual price from exchange
        try:
            price_data = await exchange_service.get_price(exchange, parsed.base, parsed.quote)
            current_price = price_data.price
            logger.info(f"Fetched price from {exchange}: ${current_price}")
        except Exception as e:
            logger.error(f"Failed to fetch price from {exchange}: {e}")
            return TradeResult(
                success=False,
                message=f"Failed to fetch price from {exchange}: {e}",
                error="PRICE_FETCH_FAILED",
            ), None

        # Get or create trade with timeframe-aware grouping (need pyramid_index first)
        trade = await db.get_open_trade_by_group(
            exchange, parsed.base, parsed.quote, alert.timeframe
        )

        if trade:
            trade_id = trade["id"]
            group_id = trade["group_id"]
            # Get existing pyramids to determine index (0-based)
            existing_pyramids = await db.get_pyramids_for_trade(trade_id)
            pyramid_index = len(existing_pyramids)
        else:
            # Create new trade with new group ID
            sequence = await db.get_next_group_sequence(
                parsed.base, exchange, alert.timeframe
            )
            group_id = generate_group_id(
                parsed.base, exchange, alert.timeframe, sequence
            )
            trade_id = str(uuid.uuid4())

            await db.create_trade_with_group(
                trade_id=trade_id,
                group_id=group_id,
                exchange=exchange,
                base=parsed.base,
                quote=parsed.quote,
                timeframe=alert.timeframe,
                position_side=alert.position_side,
            )
            pyramid_index = 0
            logger.info(
                f"Created new trade {trade_id} with group {group_id}"
            )

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

        # Validate order if strict mode
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

        # Fetch actual price from exchange
        try:
            price_data = await exchange_service.get_price(exchange, parsed.base, parsed.quote)
            exit_price = price_data.price
            logger.info(f"Fetched exit price from {exchange}: ${exit_price}")
        except Exception as e:
            logger.error(f"Failed to fetch exit price from {exchange}: {e}")
            return TradeResult(
                success=False,
                message=f"Failed to fetch price from {exchange}: {e}",
                error="PRICE_FETCH_FAILED",
            ), None

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

        # Add exit record with timestamps
        exit_id = str(uuid.uuid4())
        await db.add_exit(
            exit_id,
            trade_id,
            exit_price,
            total_exit_fees,
            exchange_timestamp=alert.timestamp,
            received_timestamp=received_timestamp.isoformat(),
        )

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
