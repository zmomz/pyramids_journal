"""
Exchange Service

Unified interface for interacting with all supported exchanges.
Handles price fetching, symbol info caching, and validation.
"""

import logging
from datetime import datetime, timedelta, timezone

from ..database import db
from ..exchanges import EXCHANGES
from ..exchanges.base import (
    BaseExchange,
    PriceData,
    SymbolInfo,
    SymbolNotFoundError,
    ExchangeAPIError,
)
from .symbol_normalizer import normalize_exchange, parse_symbol

logger = logging.getLogger(__name__)

# Cache expiry for symbol rules (24 hours)
CACHE_EXPIRY_HOURS = 24


class ExchangeService:
    """Service for fetching prices and symbol info from exchanges."""

    @staticmethod
    def get_exchange_adapter(exchange: str) -> type[BaseExchange]:
        """
        Get the exchange adapter class for an exchange.

        Args:
            exchange: Exchange name (will be normalized)

        Returns:
            Exchange adapter class

        Raises:
            ValueError: If exchange is not supported
        """
        normalized = normalize_exchange(exchange)
        if not normalized:
            raise ValueError(f"Unknown exchange: {exchange}")

        adapter = EXCHANGES.get(normalized)
        if not adapter:
            raise ValueError(f"No adapter for exchange: {normalized}")

        return adapter

    @classmethod
    async def get_price(cls, exchange: str, base: str, quote: str) -> PriceData:
        """
        Fetch current price for a trading pair.

        Args:
            exchange: Exchange name
            base: Base currency (e.g., "BTC")
            quote: Quote currency (e.g., "USDT")

        Returns:
            PriceData with current price and timestamp

        Raises:
            ValueError: If exchange is not supported
            SymbolNotFoundError: If symbol doesn't exist
            ExchangeAPIError: If API returns an error
        """
        adapter_class = cls.get_exchange_adapter(exchange)

        async with adapter_class() as adapter:
            price_data = await adapter.get_price(base, quote)
            logger.info(
                f"Fetched price for {base}/{quote} on {exchange}: {price_data.price}"
            )
            return price_data

    @classmethod
    async def get_symbol_info(
        cls, exchange: str, base: str, quote: str, use_cache: bool = True
    ) -> SymbolInfo:
        """
        Get symbol trading rules, using cache if available.

        Args:
            exchange: Exchange name
            base: Base currency
            quote: Quote currency
            use_cache: Whether to use cached data

        Returns:
            SymbolInfo with trading rules
        """
        normalized_exchange = normalize_exchange(exchange)
        base = base.upper()
        quote = quote.upper()

        # Check cache first
        if use_cache:
            try:
                cached = await db.get_symbol_rules(normalized_exchange, base, quote)
                if cached:
                    # Check if cache is still valid
                    updated_at = datetime.fromisoformat(cached["updated_at"])
                    # Ensure timezone-aware for comparison (handle naive datetimes from old data)
                    if updated_at.tzinfo is None:
                        updated_at = updated_at.replace(tzinfo=timezone.utc)
                    if datetime.now(timezone.utc) - updated_at < timedelta(hours=CACHE_EXPIRY_HOURS):
                        logger.debug(f"Using cached symbol info for {base}/{quote} on {exchange}")
                        return SymbolInfo(
                            base=cached["base"],
                            quote=cached["quote"],
                            price_precision=cached["price_precision"],
                            qty_precision=cached["qty_precision"],
                            min_qty=cached["min_qty"],
                            min_notional=cached["min_notional"],
                            tick_size=cached["tick_size"],
                        )
            except (TypeError, ValueError, KeyError) as e:
                # Cache data is corrupt or incompatible - fetch fresh data
                logger.warning(f"Cache error for {base}/{quote} on {exchange}, refreshing: {e}")

        # Fetch from exchange
        adapter_class = cls.get_exchange_adapter(exchange)
        async with adapter_class() as adapter:
            symbol_info = await adapter.get_symbol_info(base, quote)

        # Cache the result
        await db.upsert_symbol_rules(
            exchange=normalized_exchange,
            base=symbol_info.base,
            quote=symbol_info.quote,
            price_precision=symbol_info.price_precision,
            qty_precision=symbol_info.qty_precision,
            min_qty=symbol_info.min_qty,
            min_notional=symbol_info.min_notional,
            tick_size=symbol_info.tick_size,
        )

        logger.info(f"Fetched and cached symbol info for {base}/{quote} on {exchange}")
        return symbol_info

    @classmethod
    async def validate_order(
        cls,
        exchange: str,
        base: str,
        quote: str,
        size: float,
        price: float,
    ) -> tuple[bool, str | None]:
        """
        Validate order parameters against exchange rules.

        Args:
            exchange: Exchange name
            base: Base currency
            quote: Quote currency
            size: Order size in base currency
            price: Current price

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            symbol_info = await cls.get_symbol_info(exchange, base, quote)
        except (SymbolNotFoundError, ExchangeAPIError) as e:
            return False, str(e)

        # Check minimum quantity
        if size < symbol_info.min_qty:
            return (
                False,
                f"Size {size} below minimum {symbol_info.min_qty} for {base}/{quote} on {exchange}",
            )

        # Check minimum notional
        notional = size * price
        if symbol_info.min_notional > 0 and notional < symbol_info.min_notional:
            return (
                False,
                f"Notional value ${notional:.2f} below minimum ${symbol_info.min_notional:.2f} for {base}/{quote} on {exchange}",
            )

        return True, None

    @classmethod
    def round_price(cls, price: float, tick_size: float) -> float:
        """Round price to valid tick size."""
        if tick_size <= 0:
            return price
        return round(price / tick_size) * tick_size

    @classmethod
    def round_quantity(cls, quantity: float, precision: int) -> float:
        """Round quantity to valid precision."""
        return round(quantity, precision)

    @classmethod
    async def get_price_and_info(
        cls, exchange: str, symbol: str
    ) -> tuple[PriceData, SymbolInfo]:
        """
        Convenience method to get both price and symbol info.

        Args:
            exchange: Exchange name
            symbol: Symbol in any format (will be parsed)

        Returns:
            Tuple of (PriceData, SymbolInfo)
        """
        parsed = parse_symbol(symbol)
        price_data = await cls.get_price(exchange, parsed.base, parsed.quote)
        symbol_info = await cls.get_symbol_info(exchange, parsed.base, parsed.quote)
        return price_data, symbol_info


# Singleton instance
exchange_service = ExchangeService()
