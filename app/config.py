import os
from pathlib import Path
from typing import Literal

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings


class ExchangeFees:
    """Exchange fee configuration."""

    def __init__(self, maker_fee: float, taker_fee: float):
        self.maker_fee = maker_fee / 100  # Convert percentage to decimal
        self.taker_fee = taker_fee / 100

    def get_fee(self, fee_type: str) -> float:
        """Get fee rate based on type."""
        if fee_type == "maker":
            return self.maker_fee
        return self.taker_fee


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Telegram
    telegram_bot_token: str = Field(default="")
    telegram_channel_id: str = Field(default="")
    telegram_signals_channel_id: str = Field(default="")  # Signals-only channel (no controls)
    telegram_enabled: bool = Field(default=True)

    # Timezone
    timezone: str = Field(default="Asia/Riyadh")

    # Daily Report
    daily_report_time: str = Field(default="12:00")

    # Webhook Security
    webhook_secret: str = Field(default="")

    # Database
    database_path: str = Field(default="./data/trades.db")

    # Validation
    validation_mode: Literal["strict", "lenient"] = Field(default="strict")

    # Logging
    log_level: str = Field(default="INFO")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


class ExchangeConfig:
    """Exchange configuration loaded from config.yaml."""

    def __init__(self, config_path: str = "config.yaml"):
        self.exchanges: dict[str, ExchangeFees] = {}
        self.default_fee_type: str = "taker"
        self._load_config(config_path)

    def _load_config(self, config_path: str) -> None:
        """Load exchange configuration from YAML file."""
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        with open(path, "r") as f:
            config = yaml.safe_load(f)

        self.default_fee_type = config.get("default_fee_type", "taker")

        for exchange_name, fees in config.get("exchanges", {}).items():
            self.exchanges[exchange_name.lower()] = ExchangeFees(
                maker_fee=fees.get("maker_fee", 0.1),
                taker_fee=fees.get("taker_fee", 0.1),
            )

    def get_exchange_fees(self, exchange: str) -> ExchangeFees | None:
        """Get fee configuration for an exchange."""
        return self.exchanges.get(exchange.lower())

    def get_fee_rate(self, exchange: str, fee_type: str | None = None) -> float:
        """Get fee rate for an exchange."""
        fees = self.get_exchange_fees(exchange)
        if not fees:
            return 0.001  # Default 0.1% if exchange not found

        return fees.get_fee(fee_type or self.default_fee_type)


# Global instances
settings = Settings()
exchange_config = ExchangeConfig()


def ensure_data_directory() -> None:
    """Ensure the data directory exists."""
    db_path = Path(settings.database_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
