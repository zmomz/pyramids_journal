"""
Bybit Exchange Adapter

API Documentation: https://bybit-exchange.github.io/docs/v5/intro
"""

import time
from .base import (
    BaseExchange,
    PriceData,
    SymbolInfo,
    SymbolNotFoundError,
    ExchangeAPIError,
)


class BybitExchange(BaseExchange):
    """Bybit spot exchange adapter."""

    name = "bybit"
    base_url = "https://api.bybit.com"

    def format_symbol(self, base: str, quote: str) -> str:
        """Bybit format: BTCUSDT (no separator)."""
        return f"{base.upper()}{quote.upper()}"

    async def get_price(self, base: str, quote: str) -> PriceData:
        """Fetch current price from Bybit."""
        symbol = self.format_symbol(base, quote)
        url = f"{self.base_url}/v5/market/tickers"

        try:
            data = await self._request(
                "GET", url, params={"category": "spot", "symbol": symbol}
            )

            if data.get("retCode") != 0:
                raise ExchangeAPIError(f"Bybit error: {data.get('retMsg')}")

            result = data.get("result", {}).get("list", [])
            if not result:
                raise SymbolNotFoundError(f"Symbol {symbol} not found on Bybit")

            ticker = result[0]
            return PriceData(
                price=float(ticker["lastPrice"]),
                timestamp=int(data.get("time", time.time() * 1000)),
            )
        except (SymbolNotFoundError, ExchangeAPIError):
            raise
        except Exception as e:
            raise ExchangeAPIError(f"Bybit API error: {e}")

    async def get_symbol_info(self, base: str, quote: str) -> SymbolInfo:
        """Fetch symbol trading rules from Bybit."""
        symbol = self.format_symbol(base, quote)
        url = f"{self.base_url}/v5/market/instruments-info"

        try:
            data = await self._request(
                "GET", url, params={"category": "spot", "symbol": symbol}
            )

            if data.get("retCode") != 0:
                raise ExchangeAPIError(f"Bybit error: {data.get('retMsg')}")

            result = data.get("result", {}).get("list", [])
            if not result:
                raise SymbolNotFoundError(f"Symbol {symbol} not found on Bybit")

            info = result[0]
            lot_filter = info.get("lotSizeFilter", {})
            price_filter = info.get("priceFilter", {})

            # Extract values
            min_qty = float(lot_filter.get("minOrderQty", 0))
            qty_step = float(lot_filter.get("basePrecision", 0.00000001))
            tick_size = float(price_filter.get("tickSize", 0.00000001))

            # Calculate precisions
            qty_precision = len(str(qty_step).rstrip("0").split(".")[-1]) if qty_step > 0 else 8
            price_precision = len(str(tick_size).rstrip("0").split(".")[-1]) if tick_size > 0 else 8

            # Bybit may have minOrderAmt for notional
            min_notional = float(lot_filter.get("minOrderAmt", 0))

            return SymbolInfo(
                base=base.upper(),
                quote=quote.upper(),
                price_precision=price_precision,
                qty_precision=qty_precision,
                min_qty=min_qty,
                min_notional=min_notional,
                tick_size=tick_size,
            )
        except (SymbolNotFoundError, ExchangeAPIError):
            raise
        except Exception as e:
            raise ExchangeAPIError(f"Bybit API error: {e}")
