import sqlite3

conn = sqlite3.connect('game_data.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

cursor.execute('SELECT user_id, total_cookies, cookies_left, game_unlocked FROM users')
rows = cursor.fetchall()

print("=== ALL USERS IN DATABASE ===")
for row in rows:
    print(f"User: {row['user_id']}")
    print(f"  Total Cookies: {row['total_cookies']}")
    print(f"  Current Cookies: {row['cookies_left']}")
    print(f"  Game Unlocked: {row['game_unlocked']}")
    print()

conn.close()
