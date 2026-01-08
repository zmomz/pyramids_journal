"""
Trade Service

Core business logic for handling pyramid entries and exits.
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime

from ..config import settings, exchange_config
from ..database import db
from ..models import PyramidAlert, ExitAlert, TradeClosedData
from .exchange_service import exchange_service
from .symbol_normalizer import normalize_exchange, parse_symbol

logger = logging.getLogger(__name__)


@dataclass
class TradeResult:
    """Result of a trade operation."""
    success: bool
    message: str
    trade_id: str | None = None
    price: float | None = None
    error: str | None = None


class TradeService:
    """Service for managing trades and pyramids."""

    @classmethod
    async def process_pyramid(cls, alert: PyramidAlert) -> TradeResult:
        """
        Process a pyramid entry alert.

        Args:
            alert: Pyramid alert from TradingView

        Returns:
            TradeResult with success status and details
        """
        # Check idempotency
        if await db.is_alert_processed(alert.alert_id):
            logger.info(f"Alert {alert.alert_id} already processed, skipping")
            return TradeResult(
                success=True,
                message="Alert already processed",
            )

        # Normalize exchange and parse symbol
        exchange = normalize_exchange(alert.exchange)
        if not exchange:
            return TradeResult(
                success=False,
                message=f"Unknown exchange: {alert.exchange}",
                error="UNKNOWN_EXCHANGE",
            )

        try:
            parsed = parse_symbol(alert.symbol)
        except ValueError as e:
            return TradeResult(
                success=False,
                message=str(e),
                error="INVALID_SYMBOL",
            )

        # Fetch current price from exchange
        try:
            price_data = await exchange_service.get_price(
                exchange, parsed.base, parsed.quote
            )
            current_price = price_data.price
        except Exception as e:
            logger.error(f"Failed to fetch price: {e}")
            return TradeResult(
                success=False,
                message=f"Failed to fetch price: {e}",
                error="PRICE_FETCH_FAILED",
            )

        # Validate order if strict mode
        if settings.validation_mode == "strict":
            is_valid, error_msg = await exchange_service.validate_order(
                exchange, parsed.base, parsed.quote, alert.size, current_price
            )
            if not is_valid:
                logger.warning(f"Order validation failed: {error_msg}")
                return TradeResult(
                    success=False,
                    message=error_msg,
                    error="VALIDATION_FAILED",
                )

        # Get or create trade
        trade = await db.get_open_trade(exchange, parsed.base, parsed.quote)

        if trade:
            trade_id = trade["id"]
        else:
            trade_id = str(uuid.uuid4())
            await db.create_trade(trade_id, exchange, parsed.base, parsed.quote)
            logger.info(f"Created new trade {trade_id} for {parsed.base}/{parsed.quote} on {exchange}")

        # Calculate fees
        fee_rate = exchange_config.get_fee_rate(exchange)
        notional = current_price * alert.size
        fee_usdt = notional * fee_rate

        # Round price to tick size if we have symbol info
        try:
            symbol_info = await exchange_service.get_symbol_info(
                exchange, parsed.base, parsed.quote
            )
            current_price = exchange_service.round_price(
                current_price, symbol_info.tick_size
            )
        except Exception:
            pass  # Use unrounded price if symbol info unavailable

        # Add pyramid
        pyramid_id = str(uuid.uuid4())
        await db.add_pyramid(
            pyramid_id=pyramid_id,
            trade_id=trade_id,
            pyramid_index=alert.index,
            entry_price=current_price,
            position_size=alert.size,
            notional_usdt=notional,
            fee_rate=fee_rate,
            fee_usdt=fee_usdt,
        )

        # Mark alert as processed
        await db.mark_alert_processed(alert.alert_id)

        logger.info(
            f"Recorded pyramid {alert.index} for trade {trade_id}: "
            f"{alert.size} {parsed.base} @ ${current_price:.2f}"
        )

        return TradeResult(
            success=True,
            message=f"Pyramid {alert.index} recorded",
            trade_id=trade_id,
            price=current_price,
        )

    @classmethod
    async def process_exit(cls, alert: ExitAlert) -> tuple[TradeResult, TradeClosedData | None]:
        """
        Process an exit alert.

        Args:
            alert: Exit alert from TradingView

        Returns:
            Tuple of (TradeResult, TradeClosedData for notification)
        """
        # Check idempotency
        if await db.is_alert_processed(alert.alert_id):
            logger.info(f"Alert {alert.alert_id} already processed, skipping")
            return TradeResult(
                success=True,
                message="Alert already processed",
            ), None

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

        # Find open trade
        trade = await db.get_open_trade(exchange, parsed.base, parsed.quote)
        if not trade:
            return TradeResult(
                success=False,
                message=f"No open trade for {parsed.base}/{parsed.quote} on {exchange}",
                error="NO_OPEN_TRADE",
            ), None

        trade_id = trade["id"]

        # Fetch exit price
        try:
            price_data = await exchange_service.get_price(
                exchange, parsed.base, parsed.quote
            )
            exit_price = price_data.price
        except Exception as e:
            logger.error(f"Failed to fetch exit price: {e}")
            return TradeResult(
                success=False,
                message=f"Failed to fetch price: {e}",
                error="PRICE_FETCH_FAILED",
            ), None

        # Round exit price
        try:
            symbol_info = await exchange_service.get_symbol_info(
                exchange, parsed.base, parsed.quote
            )
            exit_price = exchange_service.round_price(exit_price, symbol_info.tick_size)
        except Exception:
            pass

        # Get all pyramids for this trade
        pyramids = await db.get_pyramids_for_trade(trade_id)
        if not pyramids:
            return TradeResult(
                success=False,
                message="No pyramids found for trade",
                error="NO_PYRAMIDS",
            ), None

        # Calculate PnL for each pyramid
        fee_rate = exchange_config.get_fee_rate(exchange)
        total_gross_pnl = 0.0
        total_entry_fees = 0.0
        total_exit_fees = 0.0
        total_notional = 0.0
        pyramid_details = []

        for pyramid in pyramids:
            entry_price = pyramid["entry_price"]
            size = pyramid["position_size"]
            notional = pyramid["notional_usdt"]

            # Calculate PnL (LONG only)
            gross_pnl = (exit_price - entry_price) * size
            entry_fee = pyramid["fee_usdt"]
            exit_fee = exit_price * size * fee_rate
            net_pnl = gross_pnl - entry_fee - exit_fee
            pnl_percent = (net_pnl / notional) * 100 if notional > 0 else 0

            # Update pyramid PnL
            await db.update_pyramid_pnl(pyramid["id"], net_pnl, pnl_percent)

            total_gross_pnl += gross_pnl
            total_entry_fees += entry_fee
            total_exit_fees += exit_fee
            total_notional += notional

            pyramid_details.append({
                "index": pyramid["pyramid_index"],
                "entry_price": entry_price,
                "entry_time": pyramid["entry_time"],
                "size": size,
                "pnl_usdt": net_pnl,
                "pnl_percent": pnl_percent,
            })

        # Calculate total PnL
        total_fees = total_entry_fees + total_exit_fees
        total_net_pnl = total_gross_pnl - total_fees
        total_pnl_percent = (total_net_pnl / total_notional) * 100 if total_notional > 0 else 0

        # Add exit record
        exit_id = str(uuid.uuid4())
        await db.add_exit(exit_id, trade_id, exit_price, total_exit_fees)

        # Close trade
        await db.close_trade(trade_id, total_net_pnl, total_pnl_percent)

        # Mark alert as processed
        await db.mark_alert_processed(alert.alert_id)

        logger.info(
            f"Closed trade {trade_id}: {len(pyramids)} pyramids, "
            f"exit @ ${exit_price:.2f}, net PnL: ${total_net_pnl:.2f} ({total_pnl_percent:.2f}%)"
        )

        # Prepare notification data
        closed_data = TradeClosedData(
            trade_id=trade_id,
            exchange=exchange,
            base=parsed.base,
            quote=parsed.quote,
            pyramids=pyramid_details,
            exit_price=exit_price,
            exit_time=datetime.utcnow(),
            gross_pnl=total_gross_pnl,
            total_fees=total_fees,
            net_pnl=total_net_pnl,
            net_pnl_percent=total_pnl_percent,
        )

        return TradeResult(
            success=True,
            message=f"Trade closed with {len(pyramids)} pyramids",
            trade_id=trade_id,
            price=exit_price,
        ), closed_data

    @classmethod
    async def get_trade_summary(cls, trade_id: str) -> dict | None:
        """Get full trade details with all pyramids."""
        return await db.get_trade_with_pyramids(trade_id)


# Singleton instance
trade_service = TradeService()
