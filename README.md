# Pyramids Journal

TradingView Signal Platform for forward-testing trading strategies with Telegram notifications.

## Features

- Receives TradingView webhook alerts
- Captures real-time prices from 6 exchanges (Binance, Bybit, OKX, Gate.io, Kucoin, MEXC)
- Supports up to 5 pyramid entries per trade
- Calculates PnL with exchange fees
- Sends trade notifications to Telegram
- Generates daily performance reports

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

Required settings:
- `TELEGRAM_BOT_TOKEN`: Your Telegram bot token (from @BotFather)
- `TELEGRAM_CHANNEL_ID`: Channel ID to send notifications

### 3. Configure Exchange Fees

Edit `config.yaml` to set the correct fee rates for each exchange.

### 4. Run the Server

```bash
# Development
uvicorn app.main:app --reload --port 8000

# Production
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## TradingView Alert Setup

### Webhook URL
```
http://your-server:8000/webhook
```

### Pyramid Entry Alert
```json
{
  "type": "pyramid",
  "index": 1,
  "exchange": "binance",
  "symbol": "BTC/USDT",
  "size": 0.01,
  "alert_id": "{{timenow}}_{{ticker}}_pyramid1"
}
```

### Exit Alert
```json
{
  "type": "exit",
  "exchange": "binance",
  "symbol": "BTC/USDT",
  "alert_id": "{{timenow}}_{{ticker}}_exit"
}
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/webhook` | POST | Receive TradingView alerts |
| `/health` | GET | Health check |
| `/trades` | GET | List recent trades |
| `/trades/{id}` | GET | Get trade details |
| `/reports/daily` | POST | Generate daily report |
| `/reports/send` | POST | Generate and send report to Telegram |

## Project Structure

```
pyramids_journal/
├── app/
│   ├── main.py                 # FastAPI application
│   ├── config.py               # Settings loader
│   ├── database.py             # SQLite database
│   ├── models.py               # Pydantic models
│   ├── services/
│   │   ├── symbol_normalizer.py
│   │   ├── exchange_service.py
│   │   ├── trade_service.py
│   │   ├── telegram_service.py
│   │   └── report_service.py
│   └── exchanges/
│       ├── base.py
│       ├── binance.py
│       ├── bybit.py
│       ├── okx.py
│       ├── gateio.py
│       ├── kucoin.py
│       └── mexc.py
├── .env.example
├── config.yaml
└── requirements.txt
```

## Supported Symbol Formats

The system automatically normalizes symbols from any format:
- `BTC/USDT`
- `BTCUSDT`
- `BTC-USDT`
- `BTC_USDT`
- `BINANCE:BTCUSDT`

## Exchange Symbol Formats

| Exchange | Format | Example |
|----------|--------|---------|
| Binance | BASEUSDT | BTCUSDT |
| Bybit | BASEUSDT | BTCUSDT |
| OKX | BASE-USDT | BTC-USDT |
| Gate.io | BASE_USDT | BTC_USDT |
| Kucoin | BASE-USDT | BTC-USDT |
| MEXC | BASEUSDT | BTCUSDT |

## Daily Reports

Reports are automatically sent at the configured time (default: 12:00 PM in your timezone).

To manually trigger a report:
```bash
curl -X POST http://localhost:8000/reports/send
```

## Deployment

### Using systemd (Linux)

Create `/etc/systemd/system/pyramids-journal.service`:

```ini
[Unit]
Description=Pyramids Journal
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/pyramids_journal
ExecStart=/path/to/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl enable pyramids-journal
sudo systemctl start pyramids-journal
```

## Validation

The system validates all trades against exchange rules:
- Minimum quantity
- Minimum notional value
- Price precision (tick size)

In `strict` mode (default), invalid trades are rejected.
In `lenient` mode, warnings are logged but trades are recorded.

## Security

- Optional webhook secret header (`X-Webhook-Secret`)
- No API keys required (uses public price endpoints)
- SQLite database stored locally

## License

MIT
