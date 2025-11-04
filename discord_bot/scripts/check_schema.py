import sqlite3

conn = sqlite3.connect('data/game_data.db')
cursor = conn.cursor()

# Get pokemon table schema
cursor.execute("PRAGMA table_info(pokemon)")
columns = cursor.fetchall()

print("=== CURRENT POKEMON TABLE SCHEMA ===")
for col in columns:
    print(f"{col[1]} ({col[2]})")

conn.close()


