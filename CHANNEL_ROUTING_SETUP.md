# Channel Routing Configuration

## Overview
The bot now posts public announcements to your configured **BOT_CHANNEL** while still showing private results to users.

## What Posts to BOT_CHANNEL

### ✅ Welcome Messages
- When the bot joins a server
- When new members join

### ✅ Game Announcements
- **Pokemon Catches**: "@user just caught a Pikachu! (Lv.15)"
- **Pokemon Fishing**: "@user fished up a Squirtle! (Lv.10)"
- **Rare Discoveries**: "@user discovered a rare Dragonite! (Lv.25)"

### ✅ Battle Results
- **Victory Announcements**: "@user1's Charizard defeated @user2's Blastoise!"
- **Rewards shown**: "+50 XP, +10 🍪"

### ✅ Leaderboards
- **Cookie Leaderboard**: `/leaderboard` shows top 10 cookie earners
- Posts to both the user (ephemeral) AND the bot channel (public)

## Configuration

Your `.env` file contains:
```env
BOT_CHANNEL_ID=1426291882438426715
GENERAL_CHANNEL_ID=1423024480799817881
MEMBERSHIP_CHANNEL_ID=1426291734996062440
```

### Channel Priority
The bot finds the announcement channel in this order:
1. **BOT_CHANNEL_ID** from .env (your configured channel)
2. Channel named "bot", "bots", "bot-commands", or "commands"
3. Server system channel
4. First available text channel with send permissions

## User Experience

### Private Results (Ephemeral)
Users still see their personal results privately:
- Pokemon stats (Level, Rarity, ID)
- Cookie rewards
- Battle move selections
- Collection views

### Public Announcements (Bot Channel)
The bot channel shows:
- Who caught what Pokemon
- Battle outcomes
- Leaderboard rankings
- Server-wide achievements

## Commands Added

### `/leaderboard`
Shows the top 10 cookie earners with:
- 🥇🥈🥉 Medals for top 3
- Total cookies earned
- Current cookie balance
- Posts to both user (private) and bot channel (public)

## Files Modified

1. **`core/utils/channel_utils.py`** (NEW)
   - `get_bot_channel_id()` - Get configured channel ID
   - `find_bot_channel()` - Find bot announcement channel

2. **`cogs/game_cog.py`**
   - Added `_post_to_bot_channel()` helper
   - Updated `/catch` to post public announcements
   - Updated `/fish` to post public announcements
   - Updated `/explore` to post public announcements
   - Added `/leaderboard` command

3. **`cogs/battle_cog.py`**
   - Added `_post_to_bot_channel()` helper
   - Updated battle victories to post public announcements

4. **`cogs/help_cog.py`**
   - Updated `_load_default_channel()` to check BOT_CHANNEL_ID first

5. **`games/storage/game_storage_engine.py`**
   - Added `get_cookie_leaderboard()` method

## Testing

To test the setup:
1. Start the bot: `python -m discord_bot.main`
2. Try catching a Pokemon: `/catch`
3. Check the bot channel - you should see a public announcement
4. Check the leaderboard: `/leaderboard`
5. The leaderboard should appear both privately to you and publicly in the bot channel

## Future Enhancements

You can add more announcements for:
- Pokemon evolutions
- Training milestones
- Daily streak achievements
- Rare item finds
- Server-wide events
