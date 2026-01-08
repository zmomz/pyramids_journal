"""
Base Exchange Adapter

Abstract base class that all exchange adapters must implement.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential


@dataclass
class PriceData:
    """Current price data from exchange."""
    price: float
    timestamp: int  # Unix timestamp in milliseconds


@dataclass
class SymbolInfo:
    """Trading rules for a symbol."""
    base: str
    quote: str
    price_precision: int  # Decimal places for price
    qty_precision: int    # Decimal places for quantity
    min_qty: float        # Minimum order quantity
    min_notional: float   # Minimum order value
    tick_size: float      # Price step size


class ExchangeError(Exception):
    """Base exception for exchange errors."""
    pass


class SymbolNotFoundError(ExchangeError):
    """Raised when symbol is not found on exchange."""
    pass


class ExchangeAPIError(ExchangeError):
    """Raised when exchange API returns an error."""
    pass


class BaseExchange(ABC):
    """
    Abstract base class for exchange adapters.

    All exchange adapters must implement:
    - get_price(): Fetch current price for a symbol
    - get_symbol_info(): Fetch trading rules for a symbol
    - format_symbol(): Format base/quote to exchange-specific symbol
    """

    name: str = "base"
    base_url: str = ""

    def __init__(self):
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self):
        self._client = httpx.AsyncClient(timeout=10.0)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._client:
            await self._client.aclose()

    @property
    def client(self) -> httpx.AsyncClient:
        if not self._client:
            raise RuntimeError("Exchange client not initialized. Use 'async with'.")
        return self._client

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    async def _request(
        self, method: str, url: str, **kwargs
    ) -> dict[str, Any]:
        """Make HTTP request with retry logic."""
        response = await self.client.request(method, url, **kwargs)
        response.raise_for_status()
        return response.json()

    @abstractmethod
    async def get_price(self, base: str, quote: str) -> PriceData:
        """
        Fetch current price for a trading pair.

        Args:
            base: Base currency (e.g., "BTC")
            quote: Quote currency (e.g., "USDT")

        Returns:
            PriceData with current price and timestamp

        Raises:
            SymbolNotFoundError: If symbol doesn't exist
            ExchangeAPIError: If API returns an error
        """
        pass

    @abstractmethod
    async def get_symbol_info(self, base: str, quote: str) -> SymbolInfo:
        """
        Fetch trading rules for a symbol.

        Args:
            base: Base currency (e.g., "BTC")
            quote: Quote currency (e.g., "USDT")

        Returns:
            SymbolInfo with trading rules

        Raises:
            SymbolNotFoundError: If symbol doesn't exist
            ExchangeAPIError: If API returns an error
        """
        pass

    @abstractmethod
    def format_symbol(self, base: str, quote: str) -> str:
        """
        Format base/quote to exchange-specific symbol format.

        Args:
            base: Base currency (e.g., "BTC")
            quote: Quote currency (e.g., "USDT")

        Returns:
            Formatted symbol string (e.g., "BTCUSDT" or "BTC-USDT")
        """
        pass

    def round_price(self, price: float, tick_size: float) -> float:
        """Round price to valid tick size."""
        if tick_size <= 0:
            return price
        return round(price / tick_size) * tick_size

    def round_quantity(self, quantity: float, precision: int) -> float:
        """Round quantity to valid precision."""
        return round(quantity, precision)

    def validate_order(
        self, size: float, price: float, symbol_info: SymbolInfo
    ) -> tuple[bool, str | None]:
        """
        Validate order against symbol rules.

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check minimum quantity
        if size < symbol_info.min_qty:
            return False, f"Size {size} below minimum {symbol_info.min_qty}"

        # Check minimum notional
        notional = size * price
        if notional < symbol_info.min_notional:
            return False, f"Notional {notional} below minimum {symbol_info.min_notional}"

        return True, None
