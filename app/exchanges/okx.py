"""
OKX Exchange Adapter

API Documentation: https://www.okx.com/docs-v5/en/
"""

import time
from .base import (
    BaseExchange,
    PriceData,
    SymbolInfo,
    SymbolNotFoundError,
    ExchangeAPIError,
)


class OKXExchange(BaseExchange):
    """OKX spot exchange adapter."""

    name = "okx"
    base_url = "https://www.okx.com"

    def format_symbol(self, base: str, quote: str) -> str:
        """OKX format: BTC-USDT (hyphen separator)."""
        return f"{base.upper()}-{quote.upper()}"

    async def get_price(self, base: str, quote: str) -> PriceData:
        """Fetch current price from OKX."""
        symbol = self.format_symbol(base, quote)
        url = f"{self.base_url}/api/v5/market/ticker"

        try:
            data = await self._request("GET", url, params={"instId": symbol})

            if data.get("code") != "0":
                raise ExchangeAPIError(f"OKX error: {data.get('msg')}")

            result = data.get("data", [])
            if not result:
                raise SymbolNotFoundError(f"Symbol {symbol} not found on OKX")

            ticker = result[0]
            return PriceData(
                price=float(ticker["last"]),
                timestamp=int(ticker.get("ts", time.time() * 1000)),
            )
        except (SymbolNotFoundError, ExchangeAPIError):
            raise
        except Exception as e:
            raise ExchangeAPIError(f"OKX API error: {e}")

    async def get_symbol_info(self, base: str, quote: str) -> SymbolInfo:
        """Fetch symbol trading rules from OKX."""
        symbol = self.format_symbol(base, quote)
        url = f"{self.base_url}/api/v5/public/instruments"

        try:
            data = await self._request(
                "GET", url, params={"instType": "SPOT", "instId": symbol}
            )

            if data.get("code") != "0":
                raise ExchangeAPIError(f"OKX error: {data.get('msg')}")

            result = data.get("data", [])
            if not result:
                raise SymbolNotFoundError(f"Symbol {symbol} not found on OKX")

            info = result[0]

            # Extract values
            tick_size = float(info.get("tickSz", 0.00000001))
            lot_size = float(info.get("lotSz", 0.00000001))
            min_qty = float(info.get("minSz", 0))

            # Calculate precisions
            price_precision = len(str(tick_size).rstrip("0").split(".")[-1]) if tick_size > 0 else 8
            qty_precision = len(str(lot_size).rstrip("0").split(".")[-1]) if lot_size > 0 else 8

            # OKX doesn't have explicit min notional, use 0
            min_notional = 0.0

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
            raise ExchangeAPIError(f"OKX API error: {e}")
