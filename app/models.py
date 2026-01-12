from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class TradingViewAlert(BaseModel):
    """New unified webhook payload from TradingView strategy alerts."""

    timestamp: str = Field(..., description="Exchange timestamp from TradingView {{timenow}}")
    exchange: str = Field(..., min_length=1, description="Exchange name")
    symbol: str = Field(..., min_length=1, description="Trading pair symbol")
    timeframe: str = Field(..., min_length=1, description="Chart timeframe e.g., '1h', '4h', '1D'")
    action: Literal["buy", "sell"] = Field(..., description="Order action")
    order_id: str = Field(..., min_length=1, description="Unique order ID for idempotency")
    contracts: float = Field(..., ge=0, description="Number of contracts/quantity")
    close: float = Field(..., gt=0, description="Current close price")
    position_side: Literal["long", "short", "flat"] = Field(..., description="Current position side")
    position_qty: float = Field(..., ge=0, description="Current position quantity")

    @field_validator("exchange")
    @classmethod
    def normalize_exchange(cls, v: str) -> str:
        """Normalize exchange name to lowercase."""
        return v.lower().strip()

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, v: str) -> str:
        """Normalize symbol to uppercase."""
        return v.upper().strip()

    @field_validator("timeframe")
    @classmethod
    def normalize_timeframe(cls, v: str) -> str:
        """Normalize timeframe to lowercase."""
        return v.lower().strip()

    def is_entry(self) -> bool:
        """Determine if this is an entry signal (long only)."""
        return self.action == "buy" and self.position_side == "long"

    def is_exit(self) -> bool:
        """Determine if this is an exit signal."""
        return self.action == "sell" and self.position_side == "flat"


class PyramidEntryData(BaseModel):
    """Data for pyramid entry notification."""

    group_id: str
    pyramid_index: int
    exchange: str
    base: str
    quote: str
    timeframe: str
    entry_price: float
    position_size: float
    capital_usdt: float
    exchange_timestamp: str
    received_timestamp: datetime
    total_pyramids: int


class SymbolRules(BaseModel):
    """Model for exchange symbol trading rules."""

    exchange: str
    base: str
    quote: str
    price_precision: int = Field(default=8, description="Decimal places for price")
    qty_precision: int = Field(default=8, description="Decimal places for quantity")
    min_qty: float = Field(default=0.0, description="Minimum order quantity")
    min_notional: float = Field(default=0.0, description="Minimum order value")
    tick_size: float = Field(default=0.00000001, description="Price tick size")


class PyramidRecord(BaseModel):
    """Model for a recorded pyramid."""

    id: str
    trade_id: str
    pyramid_index: int
    entry_price: float
    position_size: float
    capital_usdt: float
    entry_time: datetime
    fee_rate: float
    fee_usdt: float
    pnl_usdt: float | None = None
    pnl_percent: float | None = None


class TradeRecord(BaseModel):
    """Model for a trade with all pyramids."""

    id: str
    exchange: str
    base: str
    quote: str
    status: Literal["open", "closed"]
    created_at: datetime
    closed_at: datetime | None = None
    total_pnl_usdt: float | None = None
    total_pnl_percent: float | None = None
    pyramids: list[PyramidRecord] = []


class WebhookResponse(BaseModel):
    """Response model for webhook endpoint."""

    success: bool
    message: str
    trade_id: str | None = None
    price: float | None = None
    error: str | None = None


class TradeClosedData(BaseModel):
    """Data for a closed trade notification."""

    trade_id: str
    group_id: str
    exchange: str
    base: str
    quote: str
    timeframe: str
    pyramids: list[dict]
    exit_price: float
    exit_time: datetime
    gross_pnl: float
    total_fees: float
    net_pnl: float
    net_pnl_percent: float
    exchange_timestamp: str
    received_timestamp: datetime


class TradeHistoryItem(BaseModel):
    """Single trade in daily report history."""

    group_id: str
    exchange: str
    pair: str
    timeframe: str
    pyramids_count: int
    pnl_usdt: float
    pnl_percent: float


class DailyReportData(BaseModel):
    """Data for daily report."""

    date: str
    total_trades: int
    total_pyramids: int
    total_pnl_usdt: float
    total_pnl_percent: float
    trades: list[TradeHistoryItem] = []  # Full trade history
    by_exchange: dict[str, dict]  # exchange -> {pnl, trades}
    by_timeframe: dict[str, dict]  # timeframe -> {pnl, trades}
    by_pair: dict[str, float]  # pair -> pnl


class ValidationError(BaseModel):
    """Model for validation errors."""

    field: str
    message: str
    value: str | float | None = None
