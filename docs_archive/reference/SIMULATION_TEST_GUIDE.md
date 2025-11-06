# Simulation Test System

## Overview

The simulation test system provides pre-launch validation by passing pseudo-data through all major bot systems to verify functionality before deployment.

## Location

- **Script**: `scripts/simulation_test.py`
- **Integration**: `scripts/deploy_update.sh` (runs after pytest)

## What It Tests

### 1. Time Parsing & Date Handling
- Datetime parsing with various formats
- UTC timezone handling
- Future date calculations
- **Why**: Ensures event scheduling works with different time inputs

### 2. Event Scheduling System
- Event creation with future timestamps
- Multiple recurrence patterns (once, daily, weekly)
- Next occurrence calculations
- **Why**: Validates Top Heroes event reminder system

### 3. Relationship Progression
- User interaction tracking
- Relationship index calculations
- Relationship tier assignments
- Luck modifiers
- **Why**: Ensures user relationship system tracks correctly

### 4. Spam Penalty & Cooldown
- Aggravation level tracking
- User interaction limits
- **Why**: Validates anti-spam protections

### 5. Personality & Mood System
- Personality engine initialization
- Mood states (happy, neutral, grumpy)
- Context-based responses
- **Why**: Ensures bot personality adapts to interactions

### 6. Pokemon Game Mechanics
- Encounter generation (catch, fish, explore)
- Species and level validation
- Catch system integration
- **Why**: Validates core Pokemon game features

### 7. Data Manager Caching
- Pokemon base stats caching
- Cache file management
- API fallback handling
- **Why**: Ensures Pokemon data loads efficiently

### 8. Database Operations
- User data CRUD operations
- Cookie tracking
- Event reminder storage
- Guild-based queries
- **Why**: Validates all database interactions

## Usage

### Standalone Execution
```bash
python scripts/simulation_test.py
```

### As Part of Deployment
```bash
./scripts/deploy_update.sh
```
The deploy script automatically runs:
1. pytest (unit & integration tests)
2. simulation_test.py (pseudo-data validation)
3. Launches bot only if both pass

## Exit Codes

- **0**: All simulations passed, safe to launch
- **1**: One or more simulations failed, do not launch

## Output Format

```
[HH:MM:SS] [INFO] Starting pre-launch simulation tests...
[HH:MM:SS] [INFO] Testing time parsing functions...
[HH:MM:SS] [PASS] ✓ Time parsing with various formats
...
[HH:MM:SS] [INFO] ============================================================
[HH:MM:SS] [INFO] SIMULATION TEST SUMMARY
[HH:MM:SS] [INFO] ============================================================
[HH:MM:SS] [INFO] Total tests: 8
[HH:MM:SS] [PASS] Passed: 8 ✓
[HH:MM:SS] [PASS] All simulation tests passed! Bot is ready for launch. 🚀
```

## Adding New Tests

To add a new simulation test:

1. Add a method to `SimulationTest` class:
   ```python
   async def test_new_feature(self):
       """Test description."""
       self.log("Testing new feature...")
       try:
           # Your test logic with pseudo-data
           result = await some_function(pseudo_data)
           assert result is not None
           self.record_pass("New feature test")
       except Exception as e:
           self.record_fail("New feature test", str(e))
   ```

2. Call it in `run_all()`:
   ```python
   async def run_all(self):
       # ... existing tests
       await self.test_new_feature()
   ```

## Best Practices

### Use Pseudo-Data
- Use fictional user IDs (e.g., "sim_user_12345")
- Use in-memory databases (`:memory:`)
- Use future dates for time-based tests
- Clean up test data automatically

### Test Isolation
- Each test should be independent
- Don't rely on test execution order
- Use unique identifiers per test

### Meaningful Assertions
- Check return values, not just "doesn't crash"
- Validate data types and ranges
- Test edge cases (empty, zero, negative)

### Clear Logging
- Log what you're testing
- Include context in failure messages
- Use descriptive test names

## Differences from pytest

| Aspect | pytest | Simulation Tests |
|--------|--------|------------------|
| **Purpose** | Unit/integration tests | End-to-end validation |
| **Data** | Mocked/fixture data | Pseudo-realistic data |
| **Scope** | Individual components | Full system flow |
| **Timing** | Development/CI | Pre-deployment only |
| **Focus** | Code correctness | System readiness |

## When to Run

### Always Run
- Before production deployment
- After major refactors
- After database schema changes
- After dependency updates

### Optional
- During development (use pytest instead)
- For quick fixes (unless touching core systems)

## Troubleshooting

### "Import could not be resolved"
- These are lint warnings, not runtime errors
- Script runs correctly despite them
- Caused by dynamic path manipulation

### "Simulation tests failed"
- Check the specific failure in output
- Verify all dependencies are installed
- Ensure database schema is up-to-date
- Check for breaking API changes

### "Test passes alone, fails in suite"
- Check for test isolation issues
- Look for shared state between tests
- Verify cleanup in `__init__`

## Related Documentation

- `docs/OPERATIONS.md` - Deployment procedures
- `docs/ARCHITECTURE.md` - System architecture
- `docs/TOP_HEROES_EVENT_SYSTEM.md` - Event scheduling
- `pytest.ini` - Unit test configuration
