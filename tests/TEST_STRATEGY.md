# Test Strategy: Pyramids Journal

## Philosophy

Tests exist to catch bugs, not to inflate coverage numbers. Every test must answer:
**"What bug would slip into production if this test didn't exist?"**

## Test Boundaries

### Unit Tests (No Mocking Required)
Pure functions with deterministic inputs/outputs:
- `symbol_normalizer.py` - Symbol parsing, exchange normalization
- `models.py` - Pydantic validators, `is_entry()`/`is_exit()` logic
- `config.py` - Fee rate calculations
- PnL calculations (extracted from trade_service)
- `generate_group_id()` formatting

### Integration Tests (Real SQLite)
Database operations using in-memory SQLite:
- `database.py` - All async database methods
- Statistics calculations (win rate, drawdown, streaks)
- Timezone-aware date boundary conversions
- Race condition handling (unique constraints)

### Service Tests (Selective Mocking)
Only mock what crosses process boundaries:
- `trade_service.py` - Mock: exchange API calls. Don't mock: database, calculations
- `exchange_service.py` - Mock: httpx. Don't mock: rounding logic, validation
- `telegram_service.py` - Mock: telegram.Bot. Don't mock: message formatting

## Anti-Patterns to Avoid

1. **Never assert on mock calls** - Assert on outcomes instead
2. **Never use substring assertions** - Parse and validate actual values
3. **Never test implementation details** - Test observable behavior
4. **Never mock the database** - Use in-memory SQLite
5. **Never create tests just for coverage** - Every test prevents a specific bug

## Test Structure

```python
def test_<behavior>_<scenario>():
    """
    Bug prevented: <What would break without this test?>
    """
    # Arrange - Set up preconditions

    # Act - Execute the behavior

    # Assert - Verify observable outcomes
```

## Coverage Rules

1. Coverage is a **side effect**, not a goal
2. 100% coverage with bad assertions = worthless tests
3. A single good test > ten coverage-padding tests
4. Untested code should raise questions, not be blindly covered

## File Organization

```
tests/
  conftest.py           # Shared fixtures (db, factories)
  test_symbol_normalizer.py  # Pure function tests
  test_models.py        # Pydantic validation tests
  test_pnl_calculations.py   # Financial math (extracted for clarity)
  test_database.py      # Integration tests with real SQLite
  test_trade_service.py # Entry/exit behavior tests
  test_config.py        # Fee calculation tests
```

## Behavior-to-Test Mapping

| Production Behavior | Test File | Bug Prevented |
|---------------------|-----------|---------------|
| Symbol parsing (BTC/USDT, BTCUSDT, BTC-USDT) | test_symbol_normalizer | Wrong pair extracted |
| Exchange normalization (okex -> okx) | test_symbol_normalizer | Unknown exchange errors |
| Entry signal detection | test_models | Entry treated as exit |
| Exit signal detection | test_models | Exit treated as entry |
| Pydantic field validation | test_models | Invalid data accepted |
| PnL calculation: gross | test_pnl_calculations | Wrong profit reported |
| PnL calculation: fees | test_pnl_calculations | Fees not deducted |
| PnL calculation: percentage | test_pnl_calculations | Wrong ROI displayed |
| Trade creation | test_database | Trades not persisted |
| Pyramid addition | test_database | Pyramids orphaned |
| Trade closure | test_database | Trades stuck open |
| Drawdown calculation | test_database | Wrong risk metrics |
| Win rate calculation | test_database | Misleading statistics |
| Fee rate lookup | test_config | Wrong fees charged |
| Duplicate trade prevention | test_trade_service | Double entries |
| Duplicate exit prevention | test_trade_service | Double exits |
