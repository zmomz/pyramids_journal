"""
MEXC Exchange Adapter

API Documentation: https://mexcdevelop.github.io/apidocs/spot_v3_en/
"""

import time
from .base import (
    BaseExchange,
    PriceData,
    SymbolInfo,
    SymbolNotFoundError,
    ExchangeAPIError,
)


class MEXCExchange(BaseExchange):
    """MEXC spot exchange adapter."""

    name = "mexc"
    base_url = "https://api.mexc.com"

    def format_symbol(self, base: str, quote: str) -> str:
        """MEXC format: BTCUSDT (no separator)."""
        return f"{base.upper()}{quote.upper()}"

    async def get_price(self, base: str, quote: str) -> PriceData:
        """Fetch current price from MEXC."""
        symbol = self.format_symbol(base, quote)
        url = f"{self.base_url}/api/v3/ticker/price"

        try:
            data = await self._request("GET", url, params={"symbol": symbol})

            if not data or "price" not in data:
                raise SymbolNotFoundError(f"Symbol {symbol} not found on MEXC")

            return PriceData(
                price=float(data["price"]),
                timestamp=int(time.time() * 1000),
            )
        except SymbolNotFoundError:
            raise
        except Exception as e:
            if "Invalid symbol" in str(e) or "400" in str(e):
                raise SymbolNotFoundError(f"Symbol {symbol} not found on MEXC")
            raise ExchangeAPIError(f"MEXC API error: {e}")

    async def get_symbol_info(self, base: str, quote: str) -> SymbolInfo:
        """Fetch symbol trading rules from MEXC."""
        symbol = self.format_symbol(base, quote)
        url = f"{self.base_url}/api/v3/exchangeInfo"

        try:
            data = await self._request("GET", url, params={"symbol": symbol})

            if not data.get("symbols"):
                raise SymbolNotFoundError(f"Symbol {symbol} not found on MEXC")

            symbol_data = data["symbols"][0]

            # MEXC returns precision differently - may be int or string
            def parse_precision(value, default=8):
                """Parse precision from int or step size string."""
                if value is None:
                    return default
                try:
                    # Try as integer first
                    return int(value)
                except (ValueError, TypeError):
                    # If it's a step size string like "0.000001", calculate precision
                    try:
                        step = float(value)
                        if step > 0:
                            return len(str(step).rstrip("0").split(".")[-1])
                    except (ValueError, TypeError):
                        pass
                return default

            price_precision = parse_precision(symbol_data.get("quotePrecision"), 8)
            qty_precision = parse_precision(symbol_data.get("baseSizePrecision"), 8)

            # Extract from filters if available
            filters = {f.get("filterType"): f for f in symbol_data.get("filters", [])}

            # LOT_SIZE filter
            lot_size = filters.get("LOT_SIZE", {})
            min_qty = float(lot_size.get("minQty", 0))
            step_size = float(lot_size.get("stepSize", 0.00000001))

            if step_size > 0:
                qty_precision = len(str(step_size).rstrip("0").split(".")[-1])

            # MIN_NOTIONAL filter
            notional = filters.get("MIN_NOTIONAL", {})
            min_notional = float(notional.get("minNotional", 0))

            # PRICE_FILTER for tick size
            price_filter = filters.get("PRICE_FILTER", {})
            tick_size = float(price_filter.get("tickSize", 0.00000001))

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
            raise ExchangeAPIError(f"MEXC API error: {e}")
