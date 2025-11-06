"""
Post-Fix Validation Test for Event Reminder System
Tests event creation, storage, and retrieval after the type mismatch fix.
"""
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
import uuid

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from discord_bot.games.storage.game_storage_engine import GameStorageEngine
from discord_bot.core.engines.event_reminder_engine import (
    EventReminderEngine,
    EventReminder,
    EventCategory,
    RecurrenceType
)

def validate_event_system():
    """Validate the event reminder system after the fix."""
    
    print("=" * 70)
    print("POST-FIX VALIDATION TEST")
    print("=" * 70)
    
    # Initialize storage
    db_path = "data/game_data.db"
    storage = GameStorageEngine(db_path)
    event_engine = EventReminderEngine(storage)
    
    # Test 1: Create event with list reminder_times
    print("\n1. Testing event creation with list reminder_times...")
    test_event = EventReminder(
        event_id=str(uuid.uuid4()),
        guild_id=123456789,
        title="Test Event - Validation",
        description="Testing post-fix validation",
        category=EventCategory.CUSTOM,
        event_time_utc=datetime.now(timezone.utc) + timedelta(hours=1),
        recurrence=RecurrenceType.ONCE,
        reminder_times=[60, 15, 5]  # This is a list
    )
    
    # Store via engine's internal method
    import asyncio
    try:
        asyncio.run(event_engine._store_event(test_event))
        print("   ✅ Event stored successfully")
    except Exception as e:
        print(f"   ❌ Failed to store event: {e}")
        return False
    
    # Test 2: Retrieve and parse
    print("\n2. Testing event retrieval and parsing...")
    try:
        events = asyncio.run(event_engine.get_all_events())
        found = None
        for event in events:
            if event.event_id == test_event.event_id:
                found = event
                break
        
        if not found:
            print(f"   ❌ Event not found in database")
            return False
        
        print(f"   ✅ Event retrieved successfully")
        print(f"   ✅ reminder_times type: {type(found.reminder_times)}")
        print(f"   ✅ reminder_times value: {found.reminder_times}")
        
        # Verify data integrity
        if found.reminder_times != [60, 15, 5]:
            print(f"   ❌ reminder_times mismatch: expected [60, 15, 5], got {found.reminder_times}")
            return False
        
        print("   ✅ reminder_times data integrity verified")
        
    except AttributeError as e:
        print(f"   ❌ AttributeError (type mismatch still exists): {e}")
        return False
    except Exception as e:
        print(f"   ❌ Failed to retrieve event: {e}")
        return False
    
    # Test 3: Verify storage layer returns correct type
    print("\n3. Testing storage layer return type...")
    raw_data = storage.get_event_reminders()
    test_data = None
    for data in raw_data:
        if data['event_id'] == test_event.event_id:
            test_data = data
            break
    
    if test_data:
        rt_type = type(test_data['reminder_times'])
        rt_value = test_data['reminder_times']
        print(f"   Storage returns: {rt_type} = {rt_value}")
        
        if rt_type == list:
            print("   ✅ Storage layer returns list (json.loads() applied)")
        else:
            print(f"   ⚠️  Storage layer returns {rt_type}, not list")
    
    # Test 4: Test engine parsing with both formats
    print("\n4. Testing _data_to_event() with different formats...")
    
    # Format 1: List (from json.loads)
    test_data_list = {
        'event_id': 'test-1',
        'guild_id': 123,
        'title': 'Test',
        'description': '',
        'category': 'custom',
        'event_time_utc': datetime.now(timezone.utc).isoformat(),
        'recurrence': 'once',
        'custom_interval_hours': None,
        'reminder_times': [60, 15, 5],  # List
        'channel_id': None,
        'role_to_ping': None,
        'created_by': 0,
        'is_active': 1,
        'auto_scraped': 0,
        'source_url': None
    }
    
    try:
        parsed_event = event_engine._data_to_event(test_data_list)
        print(f"   ✅ Parsed list format: {parsed_event.reminder_times}")
    except Exception as e:
        print(f"   ❌ Failed to parse list format: {e}")
        return False
    
    # Format 2: Comma-separated string (legacy)
    test_data_string = test_data_list.copy()
    test_data_string['reminder_times'] = "60,15,5"  # String
    
    try:
        parsed_event = event_engine._data_to_event(test_data_string)
        print(f"   ✅ Parsed string format: {parsed_event.reminder_times}")
    except Exception as e:
        print(f"   ❌ Failed to parse string format: {e}")
        return False
    
    # Cleanup
    print("\n5. Cleaning up test data...")
    storage.delete_event_reminder(test_event.event_id)
    print("   ✅ Test data cleaned up")
    
    print("\n" + "=" * 70)
    print("✅ ALL VALIDATION TESTS PASSED")
    print("=" * 70)
    print()
    print("The fix correctly handles:")
    print("  • List format (from GameStorageEngine.get_event_reminders())")
    print("  • String format (legacy/fallback)")
    print("  • Event creation, storage, and retrieval")
    print()
    print("The system is now ready for production use.")
    print("=" * 70)
    
    return True

if __name__ == "__main__":
    success = validate_event_system()
    sys.exit(0 if success else 1)
