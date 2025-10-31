# Routing Logic & Channel ID Documentation

## Game/Fun Commands
- Only allowed in bot channel(s).
- Channel IDs are set via `BOT_CHANNEL_ID` in `.env`.
- Helper: `is_allowed_channel(channel_id)` checks if a command is allowed in the channel.
- Helper: `find_bot_channel(guild)` locates the bot channel by ID, name, or fallback.

## SOS Alerts
- Sent to dedicated bot channel(s)
- Channel IDs are set via `BOT_CHANNEL_ID` in `.env`.
- Helper: Finds `BOT_CHANNEL_ID` in `.env`. and makes sure they are properly route
- can trigger SOS phrases if bot detects a keyword in any channel
## Translation
- No channel restrictions; works in all channels.

## Configuration Example (.env)
```
BOT_CHANNEL_ID=123456789012345678 
ALLOWED_CHANNELS=123456789012345678  --- decorator wrapper is used to dictate where / commands can be used looks for allowed channels fails gracefully if users try to post in restricted channel

ALLOWED CHANNELS MUST BE DEFINED IN .ENV PRIMARILY FOR GAMES/EASTER EGG FUNCTIONALITY TO KEEP YOUR DISCORD FREE OF CLUTTER AND DIRECT USERS WHERE TO PLAY GAMES.
```

## Fallback/Edge Case Handling
- If no channel ID is set, bot searches for preferred channel names.
- If no preferred channel is found, bot uses system channel or first available channel with send permissions.
- SOS

## Monitoring & Maintenance
- Periodically review channel IDs and permissions after server changes.
- Update `.env` and config files as needed for new channels.
- Centralize channel logic in `core/utils/channel_utils.py` for easy updates.



---
This file documents the current routing logic and channel configuration for HippoBot. Update as needed for future changes or audits.
