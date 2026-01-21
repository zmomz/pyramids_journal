"""
Pyramids Journal - TradingView Signal Platform

Main FastAPI application for receiving TradingView alerts,
capturing exchange prices, and reporting via Telegram.
"""

import logging
from logging.handlers import RotatingFileHandler
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from .config import settings
from .database import db
from .models import TradingViewAlert, WebhookResponse, TradeClosedData, PyramidEntryData
from .services.trade_service import trade_service
from .services.telegram_service import telegram_service
from .services.report_service import report_service
from .services.symbol_normalizer import parse_symbol
from .bot.bot import telegram_bot


def setup_logging() -> None:
    """Configure logging with console and persistent file handlers."""
    log_level = getattr(logging, settings.log_level.upper())
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    formatter = logging.Formatter(log_format)

    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Console handler (for docker logs)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File handler - persisted in same volume as database
    log_dir = Path(settings.database_path).parent / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(
        log_dir / "pyramids.log",
        maxBytes=10 * 1024 * 1024,  # 10MB per file
        backupCount=5,  # Keep 5 backups (50MB total)
        encoding="utf-8",
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)


setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting Pyramids Journal...")
    await db.connect()
    logger.info("Database connected")

    # Start report scheduler
    report_service.start_scheduler()

    # Start Telegram bot
    await telegram_bot.initialize()
    await telegram_bot.start()
    logger.info("Telegram bot started")

    yield

    # Shutdown
    logger.info("Shutting down...")
    await telegram_bot.stop()
    report_service.stop_scheduler()
    await db.disconnect()
    logger.info("Shutdown complete")


app = FastAPI(
    title="Pyramids Journal",
    root_path="/pyramids_journal",
    description="TradingView Signal Platform with Telegram Integration",
    version="1.0.0",
    lifespan=lifespan,
)


def verify_webhook_secret(secret: str | None) -> bool:
    """Verify webhook secret if configured."""
    if not settings.webhook_secret:
        return True  # No secret configured, allow all
    return secret == settings.webhook_secret


@app.post("/webhook", response_model=WebhookResponse)
async def webhook(
    request: Request,
    x_webhook_secret: str | None = Header(None, alias="X-Webhook-Secret"),
) -> WebhookResponse:
    """
    Main webhook endpoint for TradingView alerts.

    Accepts the new unified JSON payload structure with trade signals.
    """
    # Verify webhook secret
    if not verify_webhook_secret(x_webhook_secret):
        logger.warning("Invalid webhook secret received")
        raise HTTPException(status_code=401, detail="Invalid webhook secret")

    # Parse JSON body
    try:
        body = await request.json()
    except Exception as e:
        logger.error(f"Failed to parse JSON body: {e}")
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    # Parse the new payload structure
    try:
        alert = TradingViewAlert(**body)
    except ValidationError as e:
        logger.error(f"Payload validation error: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid payload: {e}")

    logger.info(
        f"Received signal: {alert.action} {alert.symbol} on {alert.exchange} "
        f"(timeframe={alert.timeframe}, position_side={alert.position_side})"
    )

    # Check if processing is paused
    if await db.is_paused():
        logger.info("Signal processing is paused, ignoring alert")
        return WebhookResponse(
            success=True,
            message="Signal processing is paused",
        )

    # Check if pair is ignored
    try:
        parsed = parse_symbol(alert.symbol)
        if await db.is_pair_ignored(parsed.base, parsed.quote):
            logger.info(f"Pair {parsed.base}/{parsed.quote} is ignored, skipping")
            return WebhookResponse(
                success=True,
                message=f"Pair {parsed.base}/{parsed.quote} is ignored",
            )
    except ValueError:
        pass  # Will be handled by trade service

    # Process the unified signal
    result, notification_data = await trade_service.process_signal(alert)

    # Send notifications
    if result.success and notification_data:
        try:
            if alert.is_entry() and isinstance(notification_data, PyramidEntryData):
                # Send entry notification immediately
                await telegram_service.send_pyramid_entry(notification_data)
            elif alert.is_exit() and isinstance(notification_data, TradeClosedData):
                # Send exit notification
                await telegram_service.send_trade_closed(notification_data)
        except Exception as e:
            logger.error(f"Failed to send Telegram notification: {e}")
            # Don't fail the webhook, just log the error

    # Return response
    if not result.success:
        logger.warning(f"Signal processing failed: {result.message} (error={result.error})")
        return WebhookResponse(
            success=False,
            message=result.message,
            error=result.error,
        )

    return WebhookResponse(
        success=True,
        message=result.message,
        trade_id=result.trade_id,
        price=result.price,
    )


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy", "service": "pyramids-journal"}


@app.get("/trades")
async def list_trades(limit: int = 50) -> dict[str, Any]:
    """List recent trades."""
    trades = await db.get_recent_trades(limit)
    return {
        "count": len(trades),
        "trades": trades,
    }


@app.get("/trades/{trade_id}")
async def get_trade(trade_id: str) -> dict[str, Any]:
    """Get trade details with all pyramids."""
    trade = await db.get_trade_with_pyramids(trade_id)
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    return trade


@app.post("/reports/daily")
async def generate_daily_report(date: str | None = None) -> dict[str, Any]:
    """
    Manually trigger daily report generation.

    Args:
        date: Optional date (YYYY-MM-DD). Defaults to yesterday.
    """
    report_data = await report_service.generate_daily_report(date)
    return {
        "success": True,
        "report": report_data.model_dump(),
    }


@app.post("/reports/send")
async def send_daily_report(date: str | None = None) -> dict[str, Any]:
    """
    Manually generate and send daily report to Telegram.

    Args:
        date: Optional date (YYYY-MM-DD). Defaults to yesterday.
    """
    success = await report_service.generate_and_send_daily_report(date)
    return {
        "success": success,
        "message": "Report sent" if success else "Failed to send report",
    }


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "message": "Internal server error",
            "error": str(exc),
        },
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
