# Routing Logic & Channel ID Documentation

## Game/Fun Commands
- Only allowed in bot channel(s).
- Channel IDs are set via `BOT_CHANNEL_ID` in `.env`.
- Helper: `is_allowed_channel(channel_id)` checks if a command is allowed in the channel.
- Helper: `find_bot_channel(guild)` locates the bot channel by ID, name, or fallback.

## SOS Alerts
- Sent to dedicated SOS channel(s).
- Channel IDs are set via `SOS_CHANNEL_ID` in `.env` (comma-separated for multiple).
- Helper: `find_sos_channel(guild)` locates the SOS channel by ID, name, or falls back to bot channel.

## Translation
- No channel restrictions; works in all channels.

## Configuration Example (.env)
```
BOT_CHANNEL_ID=123456789012345678
SOS_CHANNEL_ID=234567890123456789
ALLOWED_CHANNELS=123456789012345678
```

## Fallback/Edge Case Handling
- If no channel ID is set, bot searches for preferred channel names.
- If no preferred channel is found, bot uses system channel or first available channel with send permissions.
- SOS alerts fallback to bot channel if no dedicated SOS channel is found.

## Monitoring & Maintenance
- Periodically review channel IDs and permissions after server changes.
- Update `.env` and config files as needed for new channels.
- Centralize channel logic in `core/utils/channel_utils.py` for easy updates.

## Audit Confidence
- Game/fun command routing: 90% (robust, but review after major changes)
- SOS channel routing: 85% (dedicated, but monitor for naming/ID changes)
- Translation: 100% (no restrictions)

---
This file documents the current routing logic and channel configuration for HippoBot. Update as needed for future changes or audits.
