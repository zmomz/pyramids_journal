"""
Symbol Normalizer Service

Handles parsing and formatting of trading pair symbols across different exchanges.
Each exchange has its own naming convention:
- Binance: BTCUSDT (no separator)
- Bybit: BTCUSDT (no separator)
- OKX: BTC-USDT (hyphen)
- Gate.io: BTC_USDT (underscore)
- Kucoin: BTC-USDT (hyphen)
- MEXC: BTCUSDT (no separator)
"""

from dataclasses import dataclass

# Common quote currencies to detect in concatenated symbols
QUOTE_CURRENCIES = [
    "USDT", "USDC", "BUSD", "TUSD", "USDP",  # USD stablecoins
    "BTC", "ETH", "BNB",  # Major cryptos
    "EUR", "GBP", "TRY",  # Fiat
]

# Exchange name aliases for normalization
EXCHANGE_ALIASES = {
    "binance": "binance",
    "bin": "binance",
    "bybit": "bybit",
    "okx": "okx",
    "okex": "okx",
    "gate": "gateio",
    "gate.io": "gateio",
    "gateio": "gateio",
    "kucoin": "kucoin",
    "mexc": "mexc",
    "mxc": "mexc",
}

# Symbol format per exchange
EXCHANGE_FORMATS = {
    "binance": "{base}{quote}",      # BTCUSDT
    "bybit": "{base}{quote}",        # BTCUSDT
    "okx": "{base}-{quote}",         # BTC-USDT
    "gateio": "{base}_{quote}",      # BTC_USDT
    "kucoin": "{base}-{quote}",      # BTC-USDT
    "mexc": "{base}{quote}",         # BTCUSDT
}


@dataclass
class ParsedSymbol:
    """Represents a parsed trading pair."""
    base: str
    quote: str

    def format_for_exchange(self, exchange: str) -> str:
        """Format the symbol for a specific exchange."""
        exchange = normalize_exchange(exchange)
        if not exchange:
            raise ValueError(f"Unknown exchange: {exchange}")

        fmt = EXCHANGE_FORMATS.get(exchange, "{base}{quote}")
        return fmt.format(base=self.base, quote=self.quote)

    def display(self) -> str:
        """Display format for messages (BASE/QUOTE)."""
        return f"{self.base}/{self.quote}"


def normalize_exchange(name: str) -> str | None:
    """
    Normalize exchange name to standard format.

    Args:
        name: Exchange name in any format

    Returns:
        Normalized exchange name or None if unknown
    """
    if not name:
        return None
    return EXCHANGE_ALIASES.get(name.lower().strip())


def parse_symbol(symbol: str) -> ParsedSymbol:
    """
    Parse any symbol format into base/quote components.

    Supports formats:
    - BTC/USDT
    - BTCUSDT
    - BTC-USDT
    - BTC_USDT
    - BINANCE:BTCUSDT
    - BINANCE:BTC/USDT

    Args:
        symbol: Symbol string in any format

    Returns:
        ParsedSymbol with base and quote currencies

    Raises:
        ValueError: If symbol cannot be parsed
    """
    if not symbol:
        raise ValueError("Empty symbol")

    # Uppercase and strip
    symbol = symbol.upper().strip()

    # Remove exchange prefix if present (e.g., "BINANCE:BTCUSDT")
    if ":" in symbol:
        symbol = symbol.split(":", 1)[1]

    # Try to split by common separators
    for separator in ["/", "-", "_"]:
        if separator in symbol:
            parts = symbol.split(separator, 1)
            if len(parts) == 2:
                base, quote = parts
                if base and quote:
                    return ParsedSymbol(base=base, quote=quote)

    # No separator found - try to detect quote currency
    for quote in QUOTE_CURRENCIES:
        if symbol.endswith(quote):
            base = symbol[:-len(quote)]
            if base:
                return ParsedSymbol(base=base, quote=quote)

    raise ValueError(f"Cannot parse symbol: {symbol}")


def format_for_exchange(base: str, quote: str, exchange: str) -> str:
    """
    Format base/quote as symbol for specific exchange.

    Args:
        base: Base currency (e.g., "BTC")
        quote: Quote currency (e.g., "USDT")
        exchange: Exchange name

    Returns:
        Formatted symbol string
    """
    parsed = ParsedSymbol(base=base.upper(), quote=quote.upper())
    return parsed.format_for_exchange(exchange)


def is_valid_exchange(name: str) -> bool:
    """Check if exchange name is valid/supported."""
    return normalize_exchange(name) is not None


def get_supported_exchanges() -> list[str]:
    """Get list of supported exchange names."""
    return list(EXCHANGE_FORMATS.keys())
