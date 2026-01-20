# Consistency Plan - Full App Overhaul

## Part 1: Command Consistency

### Current State - ALL Commands

| Command | Scope | Date Filter | Needs Update |
|---------|-------|-------------|--------------|
| `/pnl` | All-time | No | Yes - add date filter |
| `/stats` | All-time | No | Yes - add date filter |
| `/report` | Daily | Yes | OK |
| `/best` | All-time | No | Yes - add date filter |
| `/worst` | All-time | No | Yes - add date filter |
| `/drawdown` | All-time | No | Yes - add date filter |
| `/streak` | All-time | No | Yes - add date filter |
| `/trades` | Recent N | No | Yes - add date filter |
| `/history` | Per pair | No | OK (pair-specific) |
| `/exchange` | All-time | No | Yes - add date filter |

### Unified Date Parameter Format

ALL analytical commands will support:
```
/command           → All-time (default)
/command today     → Today only
/command yesterday → Yesterday only
/command 2026-01-20 → Specific date
/command week      → Last 7 days
/command month     → Last 30 days
```

### Commands to Update

| Command | New Usage |
|---------|-----------|
| `/pnl` | `/pnl`, `/pnl today`, `/pnl week` |
| `/stats` | `/stats`, `/stats today`, `/stats week` |
| `/best` | `/best`, `/best today`, `/best week` |
| `/worst` | `/worst`, `/worst today`, `/worst week` |
| `/drawdown` | `/drawdown`, `/drawdown today`, `/drawdown week` |
| `/streak` | `/streak`, `/streak today`, `/streak week` |
| `/trades` | `/trades`, `/trades today`, `/trades 2026-01-20` |
| `/exchange` | `/exchange`, `/exchange today` |

---

## Part 2: Interactive Menu System

### Current Problem
- Flat list of 24 commands in Telegram menu
- Hard to discover features
- No visual organization

### Solution: Interactive Inline Keyboard Menu

#### Main Menu (`/menu`)
```
📊 AlgoMakers Trading Bot
━━━━━━━━━━━━━━━━━━━━━━━

[📈 Performance]  [💰 PnL]
[📋 Trades]       [⚙️ Settings]
[📤 Export]       [❓ Help]
```

#### Performance Submenu
```
📈 Performance Analytics
━━━━━━━━━━━━━━━━━━━━━━━

📅 Time Period:
[Today] [Yesterday] [Week] [Month] [All-Time]

📊 Reports:
[Daily Report]  [Stats]
[Best Pairs]    [Worst Pairs]
[Drawdown]      [Streaks]

[← Back to Menu]
```

#### PnL Submenu
```
💰 Profit & Loss
━━━━━━━━━━━━━━━━━━━━━━━

📅 Time Period:
[Today] [Yesterday] [Week] [All-Time]

[Show PnL Summary]

[← Back to Menu]
```

#### Trades Submenu
```
📋 Trade Management
━━━━━━━━━━━━━━━━━━━━━━━

[📊 Open Positions]  [🔴 Live Prices]
[📜 Recent Trades]   [📈 Trade History]

🔍 Filter by:
[Today] [This Week] [By Pair]

[← Back to Menu]
```

#### Settings Submenu
```
⚙️ Bot Settings
━━━━━━━━━━━━━━━━━━━━━━━

💵 Capital:
[Set Capital]  [View Current]

🕐 Schedule:
[Report Time]  [Timezone]

📊 Fees:
[View Fees]  [Set Fee Rate]

🚦 Controls:
[Pause Bot]  [Resume Bot]
[Ignore Pair]  [Unignore]

[← Back to Menu]
```

---

## Part 3: Implementation Tasks

### Phase 1: Database Layer ✅ COMPLETED
- [x] Add `get_realized_pnl_for_period(start_date, end_date)` method
- [x] Add `get_statistics_for_period(start_date, end_date)` method
- [x] Add `get_best_pairs_for_period(start_date, end_date, limit)` method
- [x] Add `get_worst_pairs_for_period(start_date, end_date, limit)` method
- [x] Add `get_drawdown_for_period(start_date, end_date)` method
- [x] Add `get_streak_for_period(start_date, end_date)` method
- [x] Add `get_trades_for_period(start_date, end_date, limit)` method
- [x] Add `get_exchange_stats_for_period(start_date, end_date)` method

### Phase 2: Handler Updates ✅ COMPLETED
- [x] Update `/pnl` with date parameter parsing
- [x] Update `/stats` with date parameter parsing
- [x] Update `/best` with date parameter parsing
- [x] Update `/worst` with date parameter parsing
- [x] Update `/drawdown` with date parameter parsing
- [x] Update `/streak` with date parameter parsing
- [x] Update `/trades` with date parameter parsing
- [x] Update `/exchange` with date parameter parsing

### Phase 3: Interactive Menu ✅ COMPLETED
- [x] Create `/menu` command with inline keyboard
- [x] Add callback query handlers for menu navigation
- [x] Create submenu keyboards for each category
- [x] Add "Back" navigation between menus
- [x] Add time period selection buttons

### Phase 4: Formatter Updates ✅ COMPLETED
- [x] Update all formatters to show date scope in header
- [x] Add "Period: Today | Week | All-Time" indicator
- [x] Standardize terminology across all outputs

---

## Part 4: Helper Function

Create a shared date parsing utility:

```python
def parse_date_filter(args: list[str]) -> tuple[str | None, str | None, str]:
    """
    Parse date filter from command arguments.

    Returns: (start_date, end_date, period_label)

    Examples:
        [] -> (None, None, "All-Time")
        ["today"] -> ("2026-01-20", "2026-01-20", "Today")
        ["yesterday"] -> ("2026-01-19", "2026-01-19", "Yesterday")
        ["week"] -> ("2026-01-13", "2026-01-20", "Last 7 Days")
        ["month"] -> ("2025-12-21", "2026-01-20", "Last 30 Days")
        ["2026-01-15"] -> ("2026-01-15", "2026-01-15", "2026-01-15")
    """
```

---

## Part 5: Menu Structure in Code

```python
# bot/menu.py

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def get_main_menu() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("📈 Performance", callback_data="menu_performance"),
            InlineKeyboardButton("💰 PnL", callback_data="menu_pnl"),
        ],
        [
            InlineKeyboardButton("📋 Trades", callback_data="menu_trades"),
            InlineKeyboardButton("⚙️ Settings", callback_data="menu_settings"),
        ],
        [
            InlineKeyboardButton("📤 Export", callback_data="cmd_export"),
            InlineKeyboardButton("❓ Help", callback_data="cmd_help"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)

def get_performance_menu() -> InlineKeyboardMarkup:
    keyboard = [
        # Time period row
        [
            InlineKeyboardButton("Today", callback_data="period_today"),
            InlineKeyboardButton("Week", callback_data="period_week"),
            InlineKeyboardButton("Month", callback_data="period_month"),
            InlineKeyboardButton("All", callback_data="period_all"),
        ],
        # Commands row 1
        [
            InlineKeyboardButton("📊 Report", callback_data="cmd_report"),
            InlineKeyboardButton("📈 Stats", callback_data="cmd_stats"),
        ],
        # Commands row 2
        [
            InlineKeyboardButton("🏆 Best", callback_data="cmd_best"),
            InlineKeyboardButton("📉 Worst", callback_data="cmd_worst"),
        ],
        # Commands row 3
        [
            InlineKeyboardButton("📊 Drawdown", callback_data="cmd_drawdown"),
            InlineKeyboardButton("🔥 Streak", callback_data="cmd_streak"),
        ],
        # Back button
        [InlineKeyboardButton("← Back", callback_data="menu_main")],
    ]
    return InlineKeyboardMarkup(keyboard)
```

---

## Part 6: Expected Final UX

### User types `/menu`:
```
📊 AlgoMakers Trading Bot
━━━━━━━━━━━━━━━━━━━━━━━

Select a category:

[📈 Performance]  [💰 PnL]
[📋 Trades]       [⚙️ Settings]
[📤 Export]       [❓ Help]
```

### User taps "📈 Performance":
```
📈 Performance Analytics
━━━━━━━━━━━━━━━━━━━━━━━

📅 Select period:
[Today] [Week] [Month] [All-Time ✓]

📊 Select report:
[Report] [Stats] [Best] [Worst]
[Drawdown] [Streak]

[← Back to Menu]
```

### User taps "Today" then "Stats":
```
📊 Statistics - Today (2026-01-20)
━━━━━━━━━━━━━━━━━━━━━━━
Total Trades: 16
Win Rate: 75.00%
Profit Factor: 0.46
...

[← Back] [Change Period]
```
