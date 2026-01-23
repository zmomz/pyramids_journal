# Incident Report: Signal Processing Failures & Rate Limiting

**Date:** January 17-23, 2026
**Status:** RESOLVED
**Severity:** High (blocked signal processing)

---

## Executive Summary

Multiple trading signals failed to process due to two technical issues in the system. A total of **209 datetime comparison errors** and **2 database constraint violations** were identified and resolved. Additionally, a **Telegram rate limiting issue** was discovered and fixed.

---

## Problems Identified

### 1. DateTime Comparison Error (209 occurrences)

**Error Message:**
```
TypeError: can't subtract offset-naive and offset-aware datetimes
```

**Root Cause:**
Symbol rules cached in the database had timestamps stored without timezone information (naive), e.g., `2026-01-17T23:01:16.350796`. When the system attempted to check cache validity, it compared these naive timestamps against timezone-aware current time (`datetime.now(timezone.utc)`), causing Python to raise a TypeError.

**Impact:**
- All entry signals failed when hitting this error
- Exit signals received later had no matching open trades
- 24 unique trading pairs affected

### 2. UNIQUE Constraint Violation (2 occurrences)

**Error Message:**
```
sqlite3.IntegrityError: UNIQUE constraint failed: exits.trade_id
```

**Root Cause:**
Race condition in the `add_exit` method. When duplicate exit signals arrived within milliseconds, both passed the `has_exit()` check before either completed the INSERT operation, causing the second INSERT to fail.

### 3. Telegram Rate Limiting Error (Flood Control)

**Error Message:**
```
telegram.error.RetryAfter: Flood control exceeded. Retry in 24 seconds
```

**Root Cause:**
When users rapidly clicked through menu buttons, the bot sent too many requests to Telegram's API, triggering 429 (Too Many Requests) responses. The error handler at `menu.py:518` attempted to send an error message to the user, but this also failed due to the rate limit, causing a cascading unhandled exception.

**Impact:**

- Menu interactions became unresponsive during rate limiting
- Error handler exceptions were logged with full stack traces
- Bot recovered automatically after the rate limit period expired

---

## Affected Trading Pairs

The following pairs had failed signals due to the datetime error. Subsequent exit signals were ignored because no trade was open:

| Pair | Exchange | Timeframe | Status |
|------|----------|-----------|--------|
| PARTI/USDT | Binance | 18 | Exit ignored (no open trade) |
| HBAR/USDT | Binance | 52 | Exit ignored (no open trade) |
| AAVE/USDT | Binance | 170 | Exit ignored (no open trade) |
| ADA/USDT | Binance | 33 | Exit ignored (no open trade) |

*Note: Additional pairs from the earlier incident period (Jan 17-22) were also affected. The cache was cleared to allow fresh data to be fetched.*

---

## Resolution

### Fix 1: Timezone-Aware DateTime Handling

**File:** `app/services/exchange_service.py`

Added check to convert naive timestamps to UTC before comparison:

```python
updated_at = datetime.fromisoformat(cached["updated_at"])
# Ensure timezone-aware for comparison
if updated_at.tzinfo is None:
    updated_at = updated_at.replace(tzinfo=timezone.utc)
```

Also added self-healing try/except to refresh cache on any data corruption:

```python
except (TypeError, ValueError, KeyError) as e:
    logger.warning(f"Cache error for {base}/{quote} on {exchange}, refreshing: {e}")
```

### Fix 2: Atomic INSERT for Exits

**File:** `app/database.py`

Changed from check-then-insert pattern to atomic `INSERT OR IGNORE`:

```python
cursor = await self.connection.execute(
    """
    INSERT OR IGNORE INTO exits (id, trade_id, ...)
    VALUES (?, ?, ...)
    """,
    ...
)
return cursor.rowcount > 0  # False if already existed
```

### Fix 3: Cache Cleanup

Cleared 102 stale symbol rules from the database:

```sql
DELETE FROM symbol_rules;
```

### Fix 4: Log Security Enhancement

**File:** `app/main.py`

Added `SensitiveDataFilter` to redact API tokens from all log output (including httpx HTTP request logs).

### Fix 5: Telegram Rate Limit Handling

**File:** `app/bot/menu.py`

Added specific handling for `telegram.error.RetryAfter` exceptions:

```python
from telegram.error import RetryAfter

# In menu_callback_handler:
except RetryAfter as e:
    logger.warning(f"Rate limited by Telegram, retry after {e.retry_after}s")
except Exception as e:
    logger.error(f"Error in menu callback: {e}")
    try:
        await query.message.reply_text(f"❌ Error: {e}")
    except RetryAfter:
        pass  # Don't try to send error when rate limited
```

This prevents cascading errors when the bot is rate-limited by Telegram.

---

## Timeline

| Date/Time (UTC) | Event |
|-----------------|-------|
| 2026-01-17 ~23:00 | First datetime errors appear in logs |
| 2026-01-22 | Issue reported, investigation started |
| 2026-01-22 | Fixes implemented and deployed |
| 2026-01-22 | Symbol rules cache cleared |
| 2026-01-23 | System operating normally, no new errors |
| 2026-01-23 | Logging improvements deployed |
| 2026-01-23 08:33 | Telegram rate limit errors occurred during rapid menu navigation |
| 2026-01-23 | Rate limit handling fix deployed |

---

## Verification

- All 720 unit tests passing
- No datetime errors in logs since fix deployment
- No UNIQUE constraint errors since fix deployment
- Signals processing normally

---

## Recommendations

1. **Rotate Telegram Bot Token** - Token was exposed in logs; should be rotated via @BotFather
2. **Monitor for orphan exits** - Exit signals without matching trades indicate missed entries
3. **Database backups** - Ensure regular backups of trading data

---

## Lessons Learned

1. Always use timezone-aware datetimes throughout the application
2. Use atomic database operations to prevent race conditions
3. Add self-healing mechanisms for recoverable errors
4. Filter sensitive data from logs at the handler level
