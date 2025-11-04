# Message Cleanup System - Complete Guide

## Overview

HippoBot includes an intelligent message cleanup system that automatically removes old bot messages from previous sessions while preserving important content. This keeps Discord channels clean and prevents message clutter from bot restarts.

---

## Architecture

### Components

1. **Session Manager** (`core/engines/session_manager.py`)
   - Tracks bot restart timestamps
   - Persists session data to `data/session_state.json`
   - Provides session ID and timing information

2. **Cleanup Engine** (`core/engines/cleanup_engine.py`)
   - Performs safe message deletion
   - Implements context-aware filtering
   - Respects rate limits and permissions

3. **Integration Layer** (`integrations/integration_loader.py`)
   - Triggers cleanup on bot startup (`on_ready` event)
   - Manages configuration from environment

4. **Admin Commands** (`cogs/admin_cog.py`)
   - `/admin cleanup` - Manual cleanup trigger
   - Admin/helper role restricted

---

## How It Works

### Automatic Cleanup (on startup)

1. **Bot starts up** → Loads previous session timestamp from `data/session_state.json`
2. **If previous session exists**:
   - Iterates through all guilds and channels
   - Fetches bot's own messages created after previous session start
   - Applies safety filters (see below)
   - Deletes eligible messages with rate limiting
3. **Saves new session timestamp** for next restart

### Session Tracking

```json
{
  "last_session_start": "2025-11-04T09:30:00.123456Z",
  "last_session_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "updated_at": "2025-11-04T09:30:00.123456Z"
}
```

- Each bot restart creates a new UUID session
- Previous session timestamp becomes cleanup cutoff
- File automatically created in `data/` directory

---

## Safety Filters

Messages are **PRESERVED** (not deleted) if:

1. **Pinned** - Any pinned message
2. **Contains preserve keywords**:
   - "DO NOT DELETE"
   - "SYSTEM NOTICE"
   - "IMPORTANT"
3. **Has reactions** - Likely indicates user engagement
4. **Too recent** - Within last 30 minutes (configurable)

Channels are **SKIPPED** if:

1. **In blocklist** - Default: `bot-logs`, `announcements`, `mod-log`
2. **Missing permissions** - No `read_message_history` or `manage_messages`

---

## Configuration

### Environment Variables (.env)

```bash
# Enable/disable automatic cleanup
CLEANUP_ENABLED=true

# Don't delete messages newer than this (minutes)
CLEANUP_SKIP_RECENT_MINUTES=30

# Maximum messages to check per channel
CLEANUP_LIMIT_PER_CHANNEL=200

# Delay between deletions (seconds) for rate limiting
CLEANUP_RATE_DELAY=0.5
```

### Runtime Configuration

Can be overridden programmatically:

```python
from discord_bot.core.engines.cleanup_engine import cleanup_old_messages

config = {
    "enabled": True,
    "skip_recent_minutes": 60,  # 1 hour
    "skip_channels": ["bot-logs", "announcements", "important"],
    "delete_limit_per_channel": 500,
    "rate_limit_delay": 0.3,
    "preserve_keywords": ["DO NOT DELETE", "KEEP THIS", "IMPORTANT"],
}

stats = await cleanup_old_messages(bot, config=config)
```

---

## Manual Cleanup Command

### Usage

```
/admin cleanup [limit]
```

- **Requires**: Admin or Helper role
- **Scope**: Current channel only
- **Limit**: 1-500 messages to check (default: 100)
- **Response**: Ephemeral (only visible to you)

### Example

```
/admin cleanup limit:150

✅ Deleted 42 message(s).
⏭️ Skipped 3 (pinned/important).
```

---

## Logging & Monitoring

### Startup Logs

```
[INFO] 🧹 Starting cleanup of messages since 2025-11-04T08:00:00Z
[INFO] Starting cleanup in guild: My Discord Server
[DEBUG] Skipping channel bot-logs: blocklist:bot-logs
[DEBUG] Deleted message 123456789 from general
[INFO] Deleted 15 messages from general
[INFO] 🧹 Cleanup complete: deleted 45 messages across 3 channels (took 23.50s)
[INFO] Session started: f47ac10b-58cc-4372-a567-0e02b2c3d479
```

### Statistics

Cleanup engine returns detailed stats:

```python
{
    "messages_deleted": 45,
    "channels_cleaned": 3,
    "channels_skipped": 2,
    "errors": 0,
    "start_time": datetime(...),
    "end_time": datetime(...),
    "duration_seconds": 23.5,
    "guild_results": [
        {
            "guild_id": 123456789,
            "guild_name": "My Server",
            "channels_cleaned": 3,
            "channels_skipped": 2,
            "messages_deleted": 45
        }
    ]
}
```

---

## Testing

### Unit Tests

```bash
# Run cleanup system tests
pytest tests/test_cleanup_system.py -v

# Test coverage
pytest tests/test_cleanup_system.py --cov=core.engines.cleanup_engine
```

### Manual Testing Workflow

1. **Start bot** → Sends startup message
2. **Send test messages** from bot (e.g., `/help`)
3. **Restart bot**
4. **Verify**: Previous messages deleted, startup message remains
5. **Check logs** for cleanup statistics

### Test Scenarios

- ✅ Old messages deleted on restart
- ✅ Pinned messages preserved
- ✅ Messages with "DO NOT DELETE" preserved
- ✅ Recent messages (< 30 min) preserved
- ✅ Channels in blocklist skipped
- ✅ Channels without permissions skipped
- ✅ Rate limiting respected (no HTTP 429 errors)
- ✅ Manual `/admin cleanup` works in any channel

---

## Troubleshooting

### Cleanup not running

**Check**:
1. `CLEANUP_ENABLED=true` in `.env`
2. Bot has `manage_messages` permission
3. Previous session file exists: `data/session_state.json`

**Logs to examine**:
```
[INFO] 🧹 No previous session found, skipping cleanup (first run)
```
→ Expected on first run

### Messages not being deleted

**Common causes**:
1. Messages are pinned
2. Messages contain preserve keywords
3. Messages are too recent (< 30 min)
4. Channel is in blocklist
5. Bot lacks permissions

**Debug**:
```python
# Check message preservation logic
engine = CleanupEngine()
should_preserve, reason = engine._should_preserve_message(message)
print(f"Preserve: {should_preserve}, Reason: {reason}")
```

### Rate limit errors (HTTP 429)

**Solution**:
- Increase `CLEANUP_RATE_DELAY` (default: 0.5 seconds)
- Reduce `CLEANUP_LIMIT_PER_CHANNEL`

```bash
CLEANUP_RATE_DELAY=1.0
CLEANUP_LIMIT_PER_CHANNEL=100
```

---

## Advanced Usage

### Disable cleanup for specific guilds

Modify `integration_loader.py`:

```python
# Only cleanup in test guilds
if cleanup_enabled and self.test_guild_ids:
    guild_ids = list(self.test_guild_ids)
else:
    guild_ids = None  # All guilds
```

### Custom preserve logic

Extend `CleanupEngine`:

```python
class CustomCleanupEngine(CleanupEngine):
    def _should_preserve_message(self, message):
        # Custom logic
        if message.embeds and "IMPORTANT" in message.embeds[0].title:
            return True, "important_embed"
        return super()._should_preserve_message(message)
```

### Scheduled cleanup (optional future enhancement)

```python
from discord.ext import tasks

@tasks.loop(hours=24)
async def scheduled_cleanup():
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    await cleanup_old_messages(bot, since=cutoff)
```

---

## Security Considerations

1. **Admin-only**: Manual cleanup requires admin/helper role
2. **Scope limited**: Only bot's own messages deleted
3. **Permission checks**: Respects Discord channel permissions
4. **Rate limiting**: Built-in delays prevent abuse
5. **Audit trail**: All deletions logged with timestamps

---

## Performance

### Benchmarks

- **Small guild** (5 channels, 50 messages): ~2-3 seconds
- **Medium guild** (20 channels, 200 messages): ~15-20 seconds
- **Large guild** (50 channels, 500 messages): ~45-60 seconds

### Optimization Tips

1. Reduce `CLEANUP_LIMIT_PER_CHANNEL` for faster startup
2. Add frequently-used channels to blocklist
3. Increase `CLEANUP_SKIP_RECENT_MINUTES` to skip more messages
4. Use `TEST_GUILDS` to limit scope during development

---

## Future Enhancements (Optional)

- [ ] Scheduled cleanup every 24 hours
- [ ] Cleanup statistics in analytics dashboard
- [ ] Per-channel cleanup configuration
- [ ] Cleanup summary embed sent to modlog
- [ ] Dry-run mode (preview without deleting)
- [ ] Backup messages before deletion
- [ ] Integration with audit/tracker systems

---

## Related Documentation

- `docs/ARCHITECTURE.md` - Overall bot architecture
- `docs/OPERATIONS.md` - Operational procedures
- `master_bot.instructions.md` - Master IDE reference

---

**Last Updated**: November 4, 2025  
**Version**: 1.0  
**Maintainer**: HippoBot Development Team
