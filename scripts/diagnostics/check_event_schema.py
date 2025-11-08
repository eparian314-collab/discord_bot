import sqlite3

conn = sqlite3.connect('game_data.db')
cursor = conn.cursor()

# Check if table exists
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='event_reminders'")
table_exists = cursor.fetchone()

if table_exists:
    print("✅ event_reminders table EXISTS")
    print("\n📋 Current Schema:")
    cursor.execute("PRAGMA table_info(event_reminders)")
    for row in cursor.fetchall():
        col_id, name, col_type, not_null, default, pk = row
        print(f"  {name}: {col_type} (PK={pk}, NULL={not not_null}, DEFAULT={default})")
else:
    print("❌ event_reminders table DOES NOT EXIST")

conn.close()
