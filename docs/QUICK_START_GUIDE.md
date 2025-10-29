# Quick Start Guide: Cookie Tracking & Easter Egg Limits

## 🚀 Quick Setup

### 1. Database Migration
The new tables will be created automatically on first run. If you need to manually trigger:
```python
from games.storage.game_storage_engine import GameStorageEngine
storage = GameStorageEngine("game_data.db")
storage.create_tables()  # Creates all new tables
```

### 2. Required Bot Permissions
Add to your bot in Discord Developer Portal:
- ✅ Send Messages
- ✅ Embed Links  
- ✅ **Moderate Members** (for auto-mute feature)

### 3. Environment Variables (Optional)
```env
HELPER_ROLE_ID=123456789  # Role that can use /mute and /unmute
```

---

## 📝 User Commands

### Check Cookie Stats
```
/cookiestats
```
Shows:
- Current cookie balance
- Total earned/spent
- Daily easter egg progress (X/5)
- Aggravation warnings
- Mute status

### Easter Egg Commands (All count toward daily limit)
```
/easteregg    - Random easter egg surprise
/joke         - Random joke
/catfact      - Cat fact
/weather      - Weather lookup
/8ball        - Magic 8-ball
```

**Daily Limit:** 5 cookies per day from all easter egg commands combined

---

## 🛡️ Admin/Helper Commands

### Mute User
```
/mute @user [duration] [reason]
```
- `duration`: Minutes (default: 5)
- `reason`: Optional reason for mute

**Examples:**
```
/mute @Alice
/mute @Bob 30
/mute @Charlie 15 "Spamming commands"
```

### Unmute User
```
/unmute @user
```
Removes timeout and resets aggravation level.

---

## 🎮 Behavior Examples

### Normal Usage (Under Limit)
```
User: /easteregg
Bot: 🎱 The magic 8-ball says: Yes, definitely! 🎱
Bot: 🍪 You earned 2 cookies! (2/5 daily cookies)
```

### At Limit (5/5 cookies)
```
User: /easteregg
Bot: Hey Alice! You've already gotten all your cookies for today (5/5)! 
     🍪✨ Come back tomorrow for more fun! 🦛💖
```

### Spamming After Limit
```
User: /easteregg  (attempts 6-10)

Attempt 6: "Stop spamming, Alice. You've had your 5 cookies. That's it."
Attempt 8: "Seriously Alice? Stop spamming me. No more cookies today!"
Attempt 10: "THAT'S IT Alice! 
             HAH! I took 1 cookie from you! 😒
             🚫 MUTED for 30 minutes!"
```

### While Muted
```
User: /easteregg
Bot: 🚫 You're currently muted for spamming! Time remaining: 25 minutes.
```

---

## 🔧 Developer Usage

### Track Game Statistics
```python
# In your game cog
storage.increment_stat(user_id, 'pokemon_caught', 1)
storage.increment_stat(user_id, 'battles_won', 1)
storage.increment_stat(user_id, 'games_played', 1)

# Get stats
pokemon_count = storage.get_stat(user_id, 'pokemon_caught')
all_stats = storage.get_all_stats(user_id)
```

### Check Easter Egg Status
```python
# Check if user can earn more cookies
can_earn, cookies_today = cookie_manager.check_easter_egg_limit(user_id)

if not can_earn:
    # User hit limit - handle spam
    spam_result = cookie_manager.handle_easter_egg_spam(user_id)
    # Returns: aggravation_level, cookie_penalty, mute_chance, should_mute
```

### Award Easter Egg Cookies
```python
# Use this instead of try_award_cookies for easter egg commands
cookies = cookie_manager.try_award_easter_egg_cookies(user_id, bot_mood)

if cookies:
    # Cookies were awarded
    storage.reset_aggravation(user_id)  # Reset spam tracking
else:
    # Either no drop or limit reached
    pass
```

### Check Mute Status
```python
if storage.is_muted(user_id):
    mute_until = storage.get_mute_until(user_id)
    # Show mute message
    return
```

### Manual Aggravation Management
```python
# Get current level
level = storage.get_aggravation_level(user_id)

# Increase (auto-increments on spam)
new_level = storage.increase_aggravation(user_id, 1)

# Reset (do this on legitimate interactions)
storage.reset_aggravation(user_id)
```

### Manual Mute Management
```python
from datetime import datetime, timedelta

# Mute for 30 minutes
mute_until = datetime.utcnow() + timedelta(minutes=30)
storage.set_mute_until(user_id, mute_until)

# Clear mute
storage.clear_mute(user_id)

# Check status
is_muted = storage.is_muted(user_id)
```

---

## 🎨 Personality Messages

### Get Dynamic Messages
```python
# Easter egg limit message (escalates with aggravation)
msg = personality_engine.get_easter_egg_limit_message(
    user_name="Alice",
    aggravation_level=3  # 1-4
)

# Cookie penalty message
msg = personality_engine.get_cookie_penalty_message(
    user_name="Alice",
    amount=1
)

# Mute warning message
msg = personality_engine.get_mute_warning_message(
    user_name="Alice",
    chance=51.0  # Percentage
)
```

Messages automatically adapt to bot's current mood (happy/neutral/grumpy).

---

## 📊 Statistics Dashboard Example

Create a leaderboard or stats display:
```python
from discord import Embed

# Get user stats
balance = cookie_manager.get_cookie_balance(user_id)
ee_stats = cookie_manager.get_easter_egg_stats(user_id)
game_stats = storage.get_all_stats(user_id)

embed = Embed(title="User Statistics", color=0xFFD700)
embed.add_field(
    name="Cookies",
    value=f"Balance: {balance['current_balance']}\n"
          f"Earned: {balance['total_earned']}\n"
          f"Spent: {balance['spent']}",
    inline=True
)
embed.add_field(
    name="Easter Eggs",
    value=f"Today: {ee_stats['cookies_today']}/5\n"
          f"Attempts: {ee_stats['attempts']}",
    inline=True
)
embed.add_field(
    name="Game Stats",
    value=f"Pokémon: {game_stats.get('pokemon_caught', 0)}\n"
          f"Battles Won: {game_stats.get('battles_won', 0)}\n"
          f"Games Played: {game_stats.get('games_played', 0)}",
    inline=True
)
```

---

## 🔄 Daily Reset

Stats reset automatically at midnight UTC. To manually trigger:
```python
# Reset daily easter egg stats
storage.reset_daily_easter_egg_stats(user_id)

# This removes old records and clears today's counts
```

---

## 🐛 Troubleshooting

### User Can't Use Commands (Not Muted)
Check aggravation level:
```python
level = storage.get_aggravation_level(user_id)
print(f"Aggravation: {level}")

# Reset if needed
storage.reset_aggravation(user_id)
```

### Mute Not Applying
1. Check bot has `Moderate Members` permission
2. Check bot role is higher than target user
3. Check in guild (not DMs)

### Stats Not Tracking
Ensure storage is passed to cogs:
```python
# In main.py or integration loader
await bot.add_cog(EasterEggCog(
    bot=bot,
    relationship_manager=relationship_manager,
    cookie_manager=cookie_manager,
    personality_engine=personality_engine,
    storage=storage  # ← Must pass storage
))
```

---

## 📈 Monitoring

### Check Daily Activity
```python
# Get today's stats for a user
stats = storage.get_daily_easter_egg_stats(user_id)
print(f"Cookies: {stats['cookies_earned']}/5")
print(f"Attempts: {stats['attempts']}")
print(f"Spam: {stats['spam_count']}")
```

### Check All Muted Users
```python
# Query database directly
cursor = storage.conn.cursor()
cursor.execute("""
    SELECT user_id, mute_until 
    FROM users 
    WHERE mute_until IS NOT NULL 
    AND mute_until > datetime('now')
""")
muted_users = cursor.fetchall()
```

---

## 🎯 Best Practices

1. **Always Reset Aggravation on Success**
   ```python
   if cookies_awarded:
       storage.reset_aggravation(user_id)
   ```

2. **Check Mute Before Command Execution**
   ```python
   if storage and storage.is_muted(user_id):
       # Show mute message and return
       return
   ```

3. **Use Easter Egg Specific Methods**
   ```python
   # ❌ Don't use for easter eggs
   cookies = cookie_manager.try_award_cookies(user_id, 'easter_egg', mood)
   
   # ✅ Use this for easter eggs
   cookies = cookie_manager.try_award_easter_egg_cookies(user_id, mood)
   ```

4. **Track All Game Actions**
   ```python
   # Track everything!
   storage.increment_stat(user_id, 'pokemon_caught', 1)
   storage.increment_stat(user_id, 'items_found', 1)
   storage.increment_stat(user_id, 'commands_used', 1)
   ```

---

## 🎉 Quick Test

Test the system end-to-end:
```python
user_id = "test_user_123"

# Award cookies until limit
for i in range(6):
    cookies = cookie_manager.try_award_easter_egg_cookies(user_id, 'neutral')
    print(f"Attempt {i+1}: {cookies} cookies")

# Try spamming
for i in range(5):
    spam_result = cookie_manager.handle_easter_egg_spam(user_id)
    print(f"Spam {i+1}: Aggravation={spam_result['aggravation_level']}, "
          f"Penalty={spam_result['cookie_penalty']}, "
          f"Mute={spam_result['should_mute']}")

# Check stats
stats = storage.get_daily_easter_egg_stats(user_id)
print(f"Stats: {stats}")
```

---

## 📚 See Also

- `EASTER_EGG_LIMITS_GUIDE.md` - Complete system documentation
- `COOKIE_TRACKING_IMPLEMENTATION.md` - Implementation details
- `core/engines/cookie_manager.py` - Source code with inline docs
- `games/storage/game_storage_engine.py` - Database methods

---

**Need Help?** Check the implementation files or ask! 🦛💖
