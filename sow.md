# Scope of Work  
TradingView Signal Platform with Telegram Integration and Performance Reporting

---

## 1. Objective

Develop a backend platform that receives TradingView strategy alerts and publishes structured trade signals to a Telegram channel.

The strategy supports:
- Up to **5 pyramids (entries)**
- **1 exit** that closes all executed pyramids

The system must be **execution driven**, meaning:
- A pyramid is recorded only if its alert is triggered
= when a pyramid (entry) signal is recieved the system make a call for the exchange (take the data at that moment) record the data, and the same for the exit signal
- Pyramids that never trigger are ignored completely
- Exit closes only the pyramids that actually executed

---

## 2. Supported Exchanges

The platform must support signals for the following exchanges:
- Binance
- Bybit
- MEXC
- OKX
- Gate.io
- Kucoin

Exchange name and pair are provided by TradingView alerts and mapped internally.

---

## 3. Global Configuration (Admin Settings)

### 3.1 Telegram Configuration
A global configuration section must allow:
- Telegram Bot Token
- Telegram Channel ID or Channel Username
- Enable or disable Telegram notifications
- Default timezone for all timestamps

---

### 3.2 Exchange Fees Configuration
For each supported exchange, define:
- Maker fee percentage
- Taker fee percentage

These fees are mandatory inputs and are used in net profit calculations.

---

## 4. Strategy Logic

### 4.1 Pyramid Execution Model
- The strategy supports a maximum of 5 pyramids.
- Each pyramid is a fully independent execution.
- A pyramid either executes fully or does not execute at all.
- No partial execution per pyramid.
- Exit closes all executed pyramids in one action.

---

### 4.2 Position Sizing
- Position size is **manually defined per pyramid**.
- Each pyramid has its own forced position size.
- Sizes are provided via the TradingView alert payload.
- Only executed pyramids contribute to exposure and PnL.

---

## 5. TradingView Alert Handling

### 5.1 Alert Types
The platform must support:
- Pyramid entry alerts (Pyramid 1 to Pyramid 5)
- Exit alert (single exit closes all executed pyramids)

---

### 5.2 Execution Rules
- Each pyramid alert represents one full execution.
- If a pyramid alert is never received, that pyramid does not exist.
- Exit can occur at any time and closes only executed pyramids.
- System must correctly handle:
  - Trades with 1 executed pyramid
  - Trades with partial pyramids
  - Trades with all 5 pyramids executed

---

## 6. Telegram Message Format

### 6.1 Trade Completion Message

When an exit alert is received, send **one consolidated message** to Telegram in the following format:

```
Date: <YYYY-MM-DD>
Time: <HH:MM:SS>

Exchange: <exchange>, Pair: <symbol>

Pyramid1 price: <price>, <date/time>
Pyramid2 price: <price>, <date/time>
Pyramid3 price: <price>, <date/time>
Pyramid4 price: <price>, <date/time>
Pyramid5 price: <price>, <date/time>

Exit price: <price>, <date/time>

Total net profit: <USDT value>, <percentage>
```

Rules:
- Display **only pyramids that executed**.
- Do not show pyramids that never triggered.
- Net profit must include fees.
- Profit is calculated only from executed pyramids.

---

## 7. Profit and Fee Calculation

### 7.1 Profit Logic
- Calculate PnL per executed pyramid.
- Aggregate all executed pyramids into one trade result.
- Use:
  - Entry price
  - Exit price
  - Pyramid size
  - Exchange fees

---

### 7.2 Fee Application
- Fees are applied per execution.
- Maker or taker fee is selected based on predefined logic.
- Fees reduce gross profit to net profit.

---

## 8. Data Storage Requirements

The system must store at minimum:
- Trade ID
- Exchange
- Pair
- Pyramid index
- Entry price
- Entry timestamp
- Pyramid size
- Exit price
- Exit timestamp
- Fee value
- Net PnL per pyramid
- Total trade net PnL

---

## 9. End of Day Performance Report

At the end of each day, generate an automated report that includes:

- Total net profit (USDT and percentage)
- Total number of closed trades
- Total number of executed pyramids
- Optional but preferred:
  - Breakdown per exchange
  - Breakdown per trading pair
  - Fee summary per exchange

Delivery:
- Automatically sent to Telegram
- Optional downloadable or exportable report

---

## 10. Non Functional Requirements

- Idempotency protection to avoid duplicate alerts
- Error handling for invalid or malformed alerts
- Consistent timestamp formatting
- Clean and readable Telegram message layout
- Scalable structure for future exchange execution or automation

---

## 11. Developer Deliverables

The developer must provide:
- TradingView alert JSON schema
- Backend architecture overview
- Fee calculation logic definition
- Data storage or database schema
- Clear milestones with delivery timeline
