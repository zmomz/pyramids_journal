"""
Binance Exchange Adapter

API Documentation: https://binance-docs.github.io/apidocs/spot/en/
"""

import time
from .base import (
    BaseExchange,
    PriceData,
    SymbolInfo,
    SymbolNotFoundError,
    ExchangeAPIError,
)


class BinanceExchange(BaseExchange):
    """Binance spot exchange adapter."""

    name = "binance"
    base_url = "https://api.binance.com"

    def format_symbol(self, base: str, quote: str) -> str:
        """Binance format: BTCUSDT (no separator)."""
        return f"{base.upper()}{quote.upper()}"

    async def get_price(self, base: str, quote: str) -> PriceData:
        """Fetch current price from Binance."""
        symbol = self.format_symbol(base, quote)
        url = f"{self.base_url}/api/v3/ticker/price"

        try:
            data = await self._request("GET", url, params={"symbol": symbol})
            return PriceData(
                price=float(data["price"]),
                timestamp=int(time.time() * 1000),
            )
        except Exception as e:
            if "Invalid symbol" in str(e) or "400" in str(e):
                raise SymbolNotFoundError(f"Symbol {symbol} not found on Binance")
            raise ExchangeAPIError(f"Binance API error: {e}")

    async def get_symbol_info(self, base: str, quote: str) -> SymbolInfo:
        """Fetch symbol trading rules from Binance."""
        symbol = self.format_symbol(base, quote)
        url = f"{self.base_url}/api/v3/exchangeInfo"

        try:
            data = await self._request("GET", url, params={"symbol": symbol})

            if not data.get("symbols"):
                raise SymbolNotFoundError(f"Symbol {symbol} not found on Binance")

            symbol_data = data["symbols"][0]
            filters = {f["filterType"]: f for f in symbol_data.get("filters", [])}

            # Extract precision and limits
            price_precision = symbol_data.get("quotePrecision", 8)
            qty_precision = symbol_data.get("baseAssetPrecision", 8)

            # LOT_SIZE filter
            lot_size = filters.get("LOT_SIZE", {})
            min_qty = float(lot_size.get("minQty", 0))
            step_size = float(lot_size.get("stepSize", 0.00000001))

            # Calculate qty precision from step size
            if step_size > 0:
                qty_precision = len(str(step_size).rstrip("0").split(".")[-1])

            # NOTIONAL or MIN_NOTIONAL filter
            notional = filters.get("NOTIONAL", filters.get("MIN_NOTIONAL", {}))
            min_notional = float(notional.get("minNotional", 0))

            # PRICE_FILTER for tick size
            price_filter = filters.get("PRICE_FILTER", {})
            tick_size = float(price_filter.get("tickSize", 0.00000001))

            # Calculate price precision from tick size
            if tick_size > 0:
                price_precision = len(str(tick_size).rstrip("0").split(".")[-1])

            return SymbolInfo(
                base=base.upper(),
                quote=quote.upper(),
                price_precision=price_precision,
                qty_precision=qty_precision,
                min_qty=min_qty,
                min_notional=min_notional,
                tick_size=tick_size,
            )
        except SymbolNotFoundError:
            raise
        except Exception as e:
            raise ExchangeAPIError(f"Binance API error: {e}")
