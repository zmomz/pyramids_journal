"""
Gate.io Exchange Adapter

API Documentation: https://www.gate.io/docs/developers/apiv4/
"""

import time
from .base import (
    BaseExchange,
    PriceData,
    SymbolInfo,
    SymbolNotFoundError,
    ExchangeAPIError,
)


class GateIOExchange(BaseExchange):
    """Gate.io spot exchange adapter."""

    name = "gateio"
    base_url = "https://api.gateio.ws/api/v4"

    def format_symbol(self, base: str, quote: str) -> str:
        """Gate.io format: BTC_USDT (underscore separator)."""
        return f"{base.upper()}_{quote.upper()}"

    async def get_price(self, base: str, quote: str) -> PriceData:
        """Fetch current price from Gate.io."""
        symbol = self.format_symbol(base, quote)
        url = f"{self.base_url}/spot/tickers"

        try:
            data = await self._request("GET", url, params={"currency_pair": symbol})

            if not data or not isinstance(data, list) or len(data) == 0:
                raise SymbolNotFoundError(f"Symbol {symbol} not found on Gate.io")

            ticker = data[0]
            return PriceData(
                price=float(ticker["last"]),
                timestamp=int(time.time() * 1000),
            )
        except SymbolNotFoundError:
            raise
        except Exception as e:
            if "INVALID_CURRENCY_PAIR" in str(e):
                raise SymbolNotFoundError(f"Symbol {symbol} not found on Gate.io")
            raise ExchangeAPIError(f"Gate.io API error: {e}")

    async def get_symbol_info(self, base: str, quote: str) -> SymbolInfo:
        """Fetch symbol trading rules from Gate.io."""
        symbol = self.format_symbol(base, quote)
        url = f"{self.base_url}/spot/currency_pairs/{symbol}"

        try:
            data = await self._request("GET", url)

            if not data:
                raise SymbolNotFoundError(f"Symbol {symbol} not found on Gate.io")

            # Extract values
            precision = int(data.get("precision", 8))
            amount_precision = int(data.get("amount_precision", 8))
            min_qty = float(data.get("min_base_amount", 0))
            min_notional = float(data.get("min_quote_amount", 0))

            # Gate.io uses precision directly
            tick_size = 10 ** (-precision)

            return SymbolInfo(
                base=base.upper(),
                quote=quote.upper(),
                price_precision=precision,
                qty_precision=amount_precision,
                min_qty=min_qty,
                min_notional=min_notional,
                tick_size=tick_size,
            )
        except SymbolNotFoundError:
            raise
        except Exception as e:
            if "INVALID_CURRENCY_PAIR" in str(e) or "404" in str(e):
                raise SymbolNotFoundError(f"Symbol {symbol} not found on Gate.io")
            raise ExchangeAPIError(f"Gate.io API error: {e}")
