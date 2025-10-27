# Easter Egg Daily Limits & Spam Protection System

## Overview

This system implements robust tracking for user interactions with easter eggs, enforcing daily limits, detecting spam, and applying progressive penalties to discourage abuse.

## Features

### 1. **Daily Cookie Limits**
- Users can earn a **maximum of 5 cookies per day** from easter egg commands
- Limit applies to all easter egg interactions: `/easteregg`, `/joke`, `/catfact`, `/weather`, `/8ball`
- Resets daily at midnight UTC
- Progress shown after each cookie reward: `(3/5 daily cookies)`

### 2. **Spam Detection**
When users try to get more cookies after reaching their daily limit:
- System tracks each spam attempt
- Increases user's **aggravation level**
- Triggers escalating responses based on bot mood and aggravation

### 3. **Progressive Penalties**

#### **Cookie Removal**
- **1% base chance** to lose 1 cookie on first spam attempt
- Chance increases by **10% per additional spam attempt**
- Example: After 5 spam attempts = 41% chance to lose a cookie

#### **Auto-Mute System**
- **1% base chance** to be muted for 30 minutes on first spam
- Chance increases by **10% per spam attempt**
- Example progression:
  - 1st spam: 1% mute chance
  - 2nd spam: 11% mute chance
  - 3rd spam: 21% mute chance
  - 4th spam: 31% mute chance
  - 5th spam: 41% mute chance
  - 10th spam: 91% mute chance

#### **Mute Duration**
- Default: **30 minutes**
- Applied both in database and as Discord timeout (if bot has permissions)
- User cannot use any easter egg commands while muted

### 4. **Mood-Based Dynamic Responses**

The bot responds differently based on its current mood (`happy`, `neutral`, `grumpy`):

#### **Happy Mood - Aggravation Level 1**
> "Hey {user}! You've already gotten all your cookies for today (5/5)! 🍪✨ Come back tomorrow for more fun! 🦛💖"

#### **Happy Mood - Aggravation Level 3**
> "{user}! Stop bugging me! 😤 I said no more cookies today! You're pushing it..."

#### **Grumpy Mood - Aggravation Level 2**
> "Are you DEAF, {user}?! I said NO MORE COOKIES! 😡"

#### **Grumpy Mood - Aggravation Level 4**
> "THAT'S IT {user}! Keep it up and I'll mute you! 🚫"

### 5. **Commands**

#### User Commands
- `/easteregg` - Random easter egg (counts toward daily limit)
- `/joke` - Random joke (counts toward daily limit)
- `/catfact` - Cat fact (counts toward daily limit)
- `/weather <location>` - Weather info (counts toward daily limit)
- `/8ball <question>` - Magic 8-ball (counts toward daily limit)
- `/cookiestats` - View your cookie stats, daily progress, and warnings

#### Admin/Helper Commands
- `/mute <member> [duration] [reason]` - Timeout a user (default: 5 minutes)
- `/unmute <member>` - Remove timeout from a user

### 6. **Database Tracking**

#### New Tables

**`daily_easter_egg_stats`**
```sql
- user_id: User identifier
- date: Date (YYYY-MM-DD)
- cookies_earned: Cookies earned today (max 5)
- attempts: Total easter egg attempts today
- spam_count: Number of spam attempts
```

**`game_stats`**
```sql
- user_id: User identifier
- stat_type: Type of stat (e.g., 'pokemon_caught', 'battles_won')
- stat_value: Current value
- last_updated: Timestamp
```

**Users Table Additions**
```sql
- aggravation_level: Current spam aggravation (0-∞)
- mute_until: Timestamp when mute expires
```

### 7. **Stat Tracking**

The system now tracks comprehensive game statistics:
- `pokemon_caught` - Total Pokémon caught
- `battles_won` - Battles won
- `battles_lost` - Battles lost
- `games_played` - Total games played
- `easter_eggs_triggered` - Total easter eggs
- `trivia_correct` - Trivia answers correct
- `riddle_correct` - Riddles solved
- And more...

Access stats via `storage.increment_stat(user_id, 'stat_type')` and `storage.get_stat(user_id, 'stat_type')`

## Implementation Details

### Cookie Manager Enhancements

**New Constants:**
```python
MAX_DAILY_EASTER_EGG_COOKIES = 5
SPAM_PENALTY_COOKIE_AMOUNT = 1
BASE_MUTE_CHANCE = 0.01  # 1%
MUTE_CHANCE_INCREMENT = 0.10  # 10%
MUTE_DURATION_MINUTES = 30
```

**New Methods:**
- `check_easter_egg_limit(user_id)` - Check if user can earn more cookies today
- `try_award_easter_egg_cookies(user_id, bot_mood)` - Award cookies with limit checking
- `handle_easter_egg_spam(user_id)` - Handle spam detection and penalties
- `get_easter_egg_stats(user_id)` - Get formatted stats for display

### Personality Engine Enhancements

**New Message Templates:**
- `EASTER_EGG_LIMIT_MESSAGES` - 4 escalation levels per mood
- `COOKIE_PENALTY_MESSAGES` - Penalty notifications per mood
- `MUTE_WARNING_MESSAGES` - High risk warnings per mood

**New Methods:**
- `get_easter_egg_limit_message(user_name, aggravation_level)` - Dynamic limit messages
- `get_cookie_penalty_message(user_name, amount)` - Penalty messages
- `get_mute_warning_message(user_name, chance)` - Warning messages

### Game Storage Engine Enhancements

**Easter Egg Tracking:**
- `get_daily_easter_egg_stats(user_id)` - Get today's stats
- `record_easter_egg_attempt(user_id, cookies_earned, is_spam)` - Record attempt
- `reset_daily_easter_egg_stats(user_id)` - Reset daily stats

**Aggravation & Mute:**
- `get_aggravation_level(user_id)` - Get current aggravation
- `increase_aggravation(user_id, amount)` - Increase aggravation
- `reset_aggravation(user_id)` - Reset to 0
- `set_mute_until(user_id, until_time)` - Set mute expiration
- `clear_mute(user_id)` - Clear mute
- `is_muted(user_id)` - Check if currently muted
- `get_mute_until(user_id)` - Get mute expiration time

**Game Stats:**
- `increment_stat(user_id, stat_type, amount)` - Increment a stat
- `get_stat(user_id, stat_type)` - Get a specific stat
- `get_all_stats(user_id)` - Get all stats

## User Flow Examples

### Normal Usage (Within Limit)
1. User: `/easteregg`
2. Bot: Displays random easter egg
3. Bot: "🍪 You earned 2 cookies! (2/5 daily cookies)" *(ephemeral)*
4. Aggravation: 0

### Hitting the Limit
1. User: `/easteregg` *(already has 5 cookies today)*
2. Bot: "Hey {user}! You've already gotten all your cookies for today (5/5)! 🍪✨ Come back tomorrow for more fun! 🦛💖" *(ephemeral)*
3. Aggravation: 1

### Continued Spam (Progressive)
1. User: `/easteregg` *(6th attempt, aggravation: 2)*
2. Bot: "Stop spamming, {user}. You've had your 5 cookies. That's it."
3. Aggravation: 3

4. User: `/easteregg` *(7th attempt)*
5. Bot: "Seriously {user}? Stop spamming me. No more cookies today!"
6. 11% chance of cookie removal
7. 11% chance of mute
8. Aggravation: 4

### Getting Muted
1. User: `/easteregg` *(10th spam attempt)*
2. Bot applies penalties and checks mute chance (91%)
3. If mute triggered:
   - Bot: "THAT'S IT {user}! **MUTED for 30 minutes!** That's what happens when you don't listen! 😤"
   - Discord timeout applied (if permissions allow)
   - Database mute recorded
4. Future attempts show: "🚫 You're currently muted! Time remaining: 27 minutes."

## Configuration

### Required Permissions
For auto-mute to work with Discord timeouts:
- Bot needs `Moderate Members` permission
- Bot role must be higher than target user's role

### Environment Variables
```
HELPER_ROLE_ID=<role_id>  # Optional: Role that can use /mute and /unmute
OWNER_IDS=<comma_separated>  # Bot owners
```

## Testing

Test the system with:
```python
# Test daily limit
for i in range(7):
    await user.send_command("/easteregg")

# Test aggravation tracking
stats = storage.get_daily_easter_egg_stats(user_id)
print(f"Spam count: {stats['spam_count']}")

# Test mute status
is_muted = storage.is_muted(user_id)
```

## Maintenance

### Reset Daily Stats
Stats automatically reset at midnight UTC. Manual reset:
```python
storage.reset_daily_easter_egg_stats(user_id)
```

### Reset Aggravation
```python
storage.reset_aggravation(user_id)
```

### Clear Mute
```python
storage.clear_mute(user_id)
# Or use the /unmute command
```

## Future Enhancements

Potential improvements:
- [ ] Configurable daily limits per server
- [ ] Different limits for different roles
- [ ] Streak bonuses for daily usage without spam
- [ ] Admin dashboard for monitoring spam
- [ ] Leaderboards for cookie collection
- [ ] Weekly/monthly statistics

## Notes

- Aggravation resets when user successfully gets cookies (legitimate interaction)
- Mute duration is fixed at 30 minutes but can be customized via constant
- All easter egg commands share the same daily limit pool
- System is fault-tolerant: missing storage engine gracefully degrades functionality
