"""
Pyramids Journal - TradingView Signal Platform

Main FastAPI application for receiving TradingView alerts,
capturing exchange prices, and reporting via Telegram.
"""

import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from .config import settings
from .database import db
from .models import (
    PyramidAlert,
    ExitAlert,
    WebhookPayload,
    WebhookResponse,
)
from .services.trade_service import trade_service
from .services.telegram_service import telegram_service
from .services.report_service import report_service
from .services.symbol_normalizer import parse_symbol
from .bot.bot import telegram_bot

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
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

    Accepts JSON payload with trade signals and processes them.
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

    # Determine alert type
    try:
        payload = WebhookPayload(**body)
    except ValidationError as e:
        logger.error(f"Payload validation error: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid payload: {e}")

    logger.info(f"Received {payload.type} alert for {payload.symbol} on {payload.exchange}")

    # Check if processing is paused
    if await db.is_paused():
        logger.info("Signal processing is paused, ignoring alert")
        return WebhookResponse(
            success=True,
            message="Signal processing is paused",
        )

    # Check if pair is ignored
    try:
        parsed = parse_symbol(payload.symbol)
        if await db.is_pair_ignored(parsed.base, parsed.quote):
            logger.info(f"Pair {parsed.base}/{parsed.quote} is ignored, skipping")
            return WebhookResponse(
                success=True,
                message=f"Pair {parsed.base}/{parsed.quote} is ignored",
            )
    except ValueError:
        pass  # Will be handled by trade service

    # Process based on type
    if payload.type == "pyramid":
        try:
            alert = PyramidAlert(**body)
        except ValidationError as e:
            logger.error(f"Pyramid alert validation error: {e}")
            raise HTTPException(status_code=400, detail=f"Invalid pyramid alert: {e}")

        result = await trade_service.process_pyramid(alert)

    elif payload.type == "exit":
        try:
            alert = ExitAlert(**body)
        except ValidationError as e:
            logger.error(f"Exit alert validation error: {e}")
            raise HTTPException(status_code=400, detail=f"Invalid exit alert: {e}")

        result, closed_data = await trade_service.process_exit(alert)

        # Send Telegram notification for closed trade
        if result.success and closed_data:
            try:
                await telegram_service.send_trade_closed(closed_data)
            except Exception as e:
                logger.error(f"Failed to send Telegram notification: {e}")
                # Don't fail the webhook, just log the error

    else:
        raise HTTPException(status_code=400, detail=f"Unknown alert type: {payload.type}")

    # Return response
    if not result.success:
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
