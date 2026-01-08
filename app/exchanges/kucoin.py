"""
Kucoin Exchange Adapter

API Documentation: https://docs.kucoin.com/
"""

import time
from .base import (
    BaseExchange,
    PriceData,
    SymbolInfo,
    SymbolNotFoundError,
    ExchangeAPIError,
)


class KucoinExchange(BaseExchange):
    """Kucoin spot exchange adapter."""

    name = "kucoin"
    base_url = "https://api.kucoin.com"

    def format_symbol(self, base: str, quote: str) -> str:
        """Kucoin format: BTC-USDT (hyphen separator)."""
        return f"{base.upper()}-{quote.upper()}"

    async def get_price(self, base: str, quote: str) -> PriceData:
        """Fetch current price from Kucoin."""
        symbol = self.format_symbol(base, quote)
        url = f"{self.base_url}/api/v1/market/orderbook/level1"

        try:
            data = await self._request("GET", url, params={"symbol": symbol})

            if data.get("code") != "200000":
                raise ExchangeAPIError(f"Kucoin error: {data.get('msg')}")

            result = data.get("data")
            if not result:
                raise SymbolNotFoundError(f"Symbol {symbol} not found on Kucoin")

            return PriceData(
                price=float(result["price"]),
                timestamp=int(result.get("time", time.time() * 1000)),
            )
        except (SymbolNotFoundError, ExchangeAPIError):
            raise
        except Exception as e:
            raise ExchangeAPIError(f"Kucoin API error: {e}")

    async def get_symbol_info(self, base: str, quote: str) -> SymbolInfo:
        """Fetch symbol trading rules from Kucoin."""
        symbol = self.format_symbol(base, quote)
        url = f"{self.base_url}/api/v2/symbols"

        try:
            data = await self._request("GET", url)

            if data.get("code") != "200000":
                raise ExchangeAPIError(f"Kucoin error: {data.get('msg')}")

            symbols = data.get("data", [])
            symbol_info = None
            for s in symbols:
                if s.get("symbol") == symbol:
                    symbol_info = s
                    break

            if not symbol_info:
                raise SymbolNotFoundError(f"Symbol {symbol} not found on Kucoin")

            # Extract values
            price_increment = float(symbol_info.get("priceIncrement", 0.00000001))
            base_increment = float(symbol_info.get("baseIncrement", 0.00000001))
            min_qty = float(symbol_info.get("baseMinSize", 0))
            min_notional = float(symbol_info.get("quoteMinSize", 0))

            # Calculate precisions
            price_precision = len(str(price_increment).rstrip("0").split(".")[-1]) if price_increment > 0 else 8
            qty_precision = len(str(base_increment).rstrip("0").split(".")[-1]) if base_increment > 0 else 8

            return SymbolInfo(
                base=base.upper(),
                quote=quote.upper(),
                price_precision=price_precision,
                qty_precision=qty_precision,
                min_qty=min_qty,
                min_notional=min_notional,
                tick_size=price_increment,
            )
        except (SymbolNotFoundError, ExchangeAPIError):
            raise
        except Exception as e:
            raise ExchangeAPIError(f"Kucoin API error: {e}")
