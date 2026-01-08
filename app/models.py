from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class PyramidAlert(BaseModel):
    """Model for pyramid entry alerts from TradingView."""

    type: Literal["pyramid"] = "pyramid"
    index: int = Field(..., ge=1, le=5, description="Pyramid index (1-5)")
    exchange: str = Field(..., min_length=1, description="Exchange name")
    symbol: str = Field(..., min_length=1, description="Trading pair symbol")
    size: float = Field(..., gt=0, description="Position size in base currency")
    alert_id: str = Field(..., min_length=1, description="Unique alert ID for idempotency")

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


class ExitAlert(BaseModel):
    """Model for exit alerts from TradingView."""

    type: Literal["exit"] = "exit"
    exchange: str = Field(..., min_length=1, description="Exchange name")
    symbol: str = Field(..., min_length=1, description="Trading pair symbol")
    alert_id: str = Field(..., min_length=1, description="Unique alert ID for idempotency")

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


class WebhookPayload(BaseModel):
    """Generic webhook payload to determine alert type."""

    type: Literal["pyramid", "exit"]
    index: int | None = None
    exchange: str
    symbol: str
    size: float | None = None
    alert_id: str


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
    notional_usdt: float
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
    exchange: str
    base: str
    quote: str
    pyramids: list[dict]
    exit_price: float
    exit_time: datetime
    gross_pnl: float
    total_fees: float
    net_pnl: float
    net_pnl_percent: float


class DailyReportData(BaseModel):
    """Data for daily report."""

    date: str
    total_trades: int
    total_pyramids: int
    total_pnl_usdt: float
    total_pnl_percent: float
    by_exchange: dict[str, dict]  # exchange -> {pnl, trades}
    by_pair: dict[str, float]  # pair -> pnl


class ValidationError(BaseModel):
    """Model for validation errors."""

    field: str
    message: str
    value: str | float | None = None
