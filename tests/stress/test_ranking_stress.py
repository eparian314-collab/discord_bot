"""
Stress tests for the ranking submission system.
Tests mass screenshot uploads, rapid database operations, and OCR throughput.
"""
import asyncio
import pytest
from pathlib import Path
from unittest.mock import Mock, AsyncMock
import time


@pytest.fixture
def mock_screenshot_processor():
    """Mock screenshot processor for testing."""
    processor = Mock()
    processor.process_screenshot = AsyncMock(return_value={
        "user_id": 123456789,
        "power": 1000000,
        "kills": 500,
        "confidence": 0.95,
        "phase": 1,
        "day": 1
    })
    return processor


@pytest.fixture
def mock_storage_engine():
    """Mock storage engine for testing."""
    storage = Mock()
    storage.store_ranking = AsyncMock(return_value=True)
    storage.get_rankings = AsyncMock(return_value=[])
    return storage


@pytest.mark.asyncio
async def test_rapid_submission_stress(mock_screenshot_processor, mock_storage_engine):
    """Test handling of rapid screenshot submissions."""
    num_submissions = 100
    start_time = time.time()
    
    tasks = []
    for i in range(num_submissions):
        task = mock_screenshot_processor.process_screenshot(f"fake_image_{i}.png")
        tasks.append(task)
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    elapsed = time.time() - start_time
    successful = sum(1 for r in results if isinstance(r, dict))
    
    print(f"\n--- Rapid Submission Stress Test ---")
    print(f"Submissions: {num_submissions}")
    print(f"Successful: {successful}")
    print(f"Failed: {num_submissions - successful}")
    print(f"Time: {elapsed:.2f}s")
    print(f"Throughput: {num_submissions / elapsed:.2f} submissions/sec")
    
    assert successful == num_submissions
    assert elapsed < 30  # Should complete in under 30 seconds


@pytest.mark.asyncio
async def test_database_bulk_insert_stress(mock_storage_engine):
    """Test database performance under bulk insert operations."""
    num_inserts = 1000
    start_time = time.time()
    
    tasks = []
    for i in range(num_inserts):
        task = mock_storage_engine.store_ranking({
            "user_id": i,
            "guild_id": 12345,
            "power": 1000000 + i,
            "kills": 500 + i,
            "event_week": 1,
            "stage_type": "kvk",
            "day_number": 1
        })
        tasks.append(task)
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    elapsed = time.time() - start_time
    successful = sum(1 for r in results if r is True)
    
    print(f"\n--- Database Bulk Insert Stress Test ---")
    print(f"Inserts: {num_inserts}")
    print(f"Successful: {successful}")
    print(f"Failed: {num_inserts - successful}")
    print(f"Time: {elapsed:.2f}s")
    print(f"Throughput: {num_inserts / elapsed:.2f} inserts/sec")
    
    assert successful == num_inserts
    assert elapsed < 60  # Should complete in under 60 seconds


@pytest.mark.asyncio
async def test_concurrent_read_write_stress(mock_storage_engine):
    """Test concurrent read and write operations on the database."""
    num_writes = 50
    num_reads = 100
    
    start_time = time.time()
    
    write_tasks = [
        mock_storage_engine.store_ranking({
            "user_id": i,
            "guild_id": 12345,
            "power": 1000000 + i,
            "event_week": 1
        })
        for i in range(num_writes)
    ]
    
    read_tasks = [
        mock_storage_engine.get_rankings(12345)
        for _ in range(num_reads)
    ]
    
    all_tasks = write_tasks + read_tasks
    results = await asyncio.gather(*all_tasks, return_exceptions=True)
    
    elapsed = time.time() - start_time
    successful = sum(1 for r in results if not isinstance(r, Exception))
    
    print(f"\n--- Concurrent Read/Write Stress Test ---")
    print(f"Total operations: {num_writes + num_reads}")
    print(f"Writes: {num_writes}, Reads: {num_reads}")
    print(f"Successful: {successful}")
    print(f"Failed: {len(results) - successful}")
    print(f"Time: {elapsed:.2f}s")
    print(f"Throughput: {len(results) / elapsed:.2f} ops/sec")
    
    assert successful == len(results)
    assert elapsed < 30


@pytest.mark.asyncio
async def test_ocr_batch_processing_stress(mock_screenshot_processor):
    """Test OCR engine performance with batch image processing."""
    num_images = 50
    start_time = time.time()
    
    # Simulate batch processing
    batch_size = 10
    batches = [num_images // batch_size] * batch_size
    
    all_results = []
    for batch_num, batch_count in enumerate(batches):
        tasks = [
            mock_screenshot_processor.process_screenshot(f"image_{batch_num}_{i}.png")
            for i in range(batch_count)
        ]
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)
        all_results.extend(batch_results)
    
    elapsed = time.time() - start_time
    successful = sum(1 for r in all_results if isinstance(r, dict))
    
    print(f"\n--- OCR Batch Processing Stress Test ---")
    print(f"Images processed: {num_images}")
    print(f"Batch size: {batch_size}")
    print(f"Successful: {successful}")
    print(f"Failed: {num_images - successful}")
    print(f"Time: {elapsed:.2f}s")
    print(f"Throughput: {num_images / elapsed:.2f} images/sec")
    
    assert successful == num_images
    assert elapsed < 60


@pytest.mark.asyncio
async def test_event_bus_stress(mock_screenshot_processor):
    """Test event bus under high message volume."""
    from discord_bot.core.event_bus import EventBus
    
    bus = EventBus()
    events_emitted = 0
    events_received = 0
    
    async def handler(**kwargs):
        nonlocal events_received
        events_received += 1
    
    bus.subscribe("stress.test", handler)
    
    num_events = 1000
    start_time = time.time()
    
    tasks = []
    for i in range(num_events):
        task = bus.emit("stress.test", index=i)
        tasks.append(task)
        events_emitted += 1
    
    await asyncio.gather(*tasks)
    
    elapsed = time.time() - start_time
    
    print(f"\n--- Event Bus Stress Test ---")
    print(f"Events emitted: {events_emitted}")
    print(f"Events received: {events_received}")
    print(f"Time: {elapsed:.2f}s")
    print(f"Throughput: {events_emitted / elapsed:.2f} events/sec")
    
    assert events_received == events_emitted
    assert elapsed < 10


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
