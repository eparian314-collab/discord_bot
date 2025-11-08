# Stress Test Suite for HippoBot

This directory contains stress tests for validating bot performance under load.

## Test Categories

### 1. Ranking System (`test_ranking_stress.py`)
- Rapid screenshot submission handling
- Database bulk insert operations
- Concurrent read/write operations
- OCR batch processing throughput
- Event bus message volume

### 2. Translation System (`test_translation_stress.py`)
- Concurrent translation requests
- Multilingual burst handling
- Fallback chain performance

## Running Stress Tests

### Using pytest (Local)
```bash
# Run all stress tests
pytest tests/stress/ -v -s

# Run specific test file
pytest tests/stress/test_ranking_stress.py -v -s

# Run specific test
pytest tests/stress/test_ranking_stress.py::test_rapid_submission_stress -v -s
```

### Using Docker Compose
```bash
# Build and run stress tests in isolation
docker-compose --profile testing run --rm stress-test

# Or run specific test
docker-compose --profile testing run --rm stress-test python -m pytest tests/stress/test_ranking_stress.py -v -s
```

### Using Docker (Manual)
```bash
# Build the image
docker build -t discord-bot-stress .

# Run stress tests
docker run --rm --env-file .env -v "$(pwd)/test:/app/test" discord-bot-stress python -m pytest tests/stress/ -v -s
```

## Best Practices

1. **Always use test data** - Never run stress tests on production databases or with real user data.
2. **Monitor resources** - Watch CPU, memory, and disk I/O during tests.
3. **Backup first** - Always backup databases before running destructive tests.
4. **Isolated environment** - Use Docker or VMs for maximum safety.
5. **Review logs** - Check logs for errors, timeouts, or performance issues.

## Expected Results

### Performance Baselines
- Ranking submissions: >50 submissions/sec
- Database inserts: >500 inserts/sec
- OCR processing: >5 images/sec
- Event bus: >1000 events/sec
- Translations: >50 translations/sec

These are baseline targets. Adjust based on your hardware and requirements.

## Adding New Tests

To add new stress tests:
1. Create a new file `test_<feature>_stress.py`
2. Follow the existing test patterns
3. Use async/await for concurrent operations
4. Include performance metrics and assertions
5. Document expected behavior and thresholds
