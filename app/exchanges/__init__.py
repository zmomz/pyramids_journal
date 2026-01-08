# Exchange adapters module
from .base import BaseExchange
from .binance import BinanceExchange
from .bybit import BybitExchange
from .okx import OKXExchange
from .gateio import GateIOExchange
from .kucoin import KucoinExchange
from .mexc import MEXCExchange

EXCHANGES = {
    "binance": BinanceExchange,
    "bybit": BybitExchange,
    "okx": OKXExchange,
    "gateio": GateIOExchange,
    "kucoin": KucoinExchange,
    "mexc": MEXCExchange,
}

__all__ = [
    "BaseExchange",
    "BinanceExchange",
    "BybitExchange",
    "OKXExchange",
    "GateIOExchange",
    "KucoinExchange",
    "MEXCExchange",
    "EXCHANGES",
]
