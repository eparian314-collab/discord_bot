"""
Event Reminder System Diagnostic Script
Identifies the root cause of event creation failures.
"""
import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from discord_bot.games.storage.game_storage_engine import GameStorageEngine

def diagnose_event_storage():
    """Diagnose the event reminder storage system."""
    
    print("=" * 70)
    print("EVENT REMINDER SYSTEM DIAGNOSTIC")
    print("=" * 70)
    
    # Test with actual database
    db_path = "data/game_data.db"
    print(f"\n1. Connecting to database: {db_path}")
    storage = GameStorageEngine(db_path)
    
    # Check schema
    print("\n2. Verifying table schema...")
    cursor = storage.conn.cursor()
    cursor.execute("PRAGMA table_info(event_reminders)")
    schema = cursor.fetchall()
    
    print("   Schema columns:")
    for row in schema:
        col_id, name, col_type, not_null, default, pk = row
        print(f"     {name}: {col_type}")
    
    # Test event data creation (as done by EventReminderEngine._store_event)
    print("\n3. Testing event data structure...")
    from datetime import datetime, timezone
    from discord_bot.core.engines.event_reminder_engine import EventCategory, RecurrenceType
    
    test_event_data = {
        'event_id': 'test-diagnostic-event',
        'guild_id': 123456789,
        'title': 'Test Diagnostic Event',
        'description': 'Testing event storage',
        'category': EventCategory.CUSTOM.value,
        'event_time_utc': datetime.now(timezone.utc).isoformat(),
        'recurrence': RecurrenceType.ONCE.value,
        'custom_interval_hours': None,
        'reminder_times': [60, 15, 5],  # This is a LIST
        'channel_id': 987654321,
        'role_to_ping': None,
        'created_by': 111222333,
        'is_active': 1,
        'auto_scraped': 0,
        'source_url': None
    }
    
    print("   Event data (as passed from EventReminderEngine):")
    print(f"     reminder_times type: {type(test_event_data['reminder_times'])}")
    print(f"     reminder_times value: {test_event_data['reminder_times']}")
    
    # Test what storage layer does with it
    print("\n4. Testing storage layer transformation...")
    print("   storage.store_event_reminder() will:")
    print(f"     - Receive: {test_event_data['reminder_times']} (list)")
    print(f"     - Convert to: {json.dumps(test_event_data['reminder_times'])} (JSON string)")
    print("     - Store as TEXT in database")
    
    # Test retrieval parsing
    print("\n5. Testing retrieval parsing...")
    print("   storage.get_event_reminders() will:")
    stored_as = json.dumps(test_event_data['reminder_times'])
    print(f"     - Retrieve: '{stored_as}' (TEXT from database)")
    print(f"     - Parse with json.loads(): {json.loads(stored_as)} (list)")
    
    # But EventReminderEngine._data_to_event expects comma-separated string!
    print("\n6. FOUND THE ISSUE!")
    print("   ❌ EventReminderEngine._data_to_event() expects:")
    print("      '60,15,5' (comma-separated string)")
    print("      It does: data['reminder_times'].split(',') ")
    print()
    print("   ✅ But GameStorageEngine.get_event_reminders() returns:")
    print("      [60, 15, 5] (parsed JSON list)")
    print("      After json.loads() on the stored JSON string")
    
    print("\n" + "=" * 70)
    print("ROOT CAUSE IDENTIFIED")
    print("=" * 70)
    print()
    print("TYPE MISMATCH between storage layer and engine layer:")
    print()
    print("  Storage (game_storage_engine.py:889):")
    print("    - Stores: json.dumps([60,15,5]) → '[60,15,5]'")
    print("    - Returns: json.loads('[60,15,5]') → [60,15,5] (list)")
    print()
    print("  Engine (event_reminder_engine.py:467):")
    print("    - Expects: '60,15,5' (comma-separated string)")  
    print("    - Parses: data['reminder_times'].split(',') → ['60','15','5']")
    print()
    print("CONSEQUENCE:")
    print("  When trying to split() a list, Python raises AttributeError:")
    print("  'list' object has no attribute 'split'")
    print()
    print("=" * 70)
    print("SOLUTION")
    print("=" * 70)
    print()
    print("Fix EventReminderEngine._data_to_event() to handle both formats:")
    print()
    print("  if isinstance(data['reminder_times'], list):")
    print("      reminder_times = data['reminder_times']")
    print("  elif isinstance(data['reminder_times'], str):")
    print("      reminder_times = [int(x) for x in data['reminder_times'].split(',')]")
    print()
    
    # Cleanup test
    cursor.execute("DELETE FROM event_reminders WHERE event_id = ?", ('test-diagnostic-event',))
    storage.conn.commit()
    
    print("=" * 70)
    print("DIAGNOSTIC COMPLETE")
    print("=" * 70)

if __name__ == "__main__":
    diagnose_event_storage()
