# Top Heroes Event Reminder System

## Overview

A comprehensive event scheduling and reminder system for Top Heroes game coordination, designed for international guilds requiring UTC-based timing and automated event management.

## Features

### 🔔 Core Functionality
- **UTC-based scheduling** for international coordination
- **Recurring events** (daily, weekly, monthly, custom intervals)
- **Multiple reminder times** (configurable minutes before events)
- **Role-based management** (server owners and helpers)
- **Automatic scraping** from Top Heroes sources (when available)

### 🎮 Event Categories
- **Raids** - Boss battles, dragon raids
- **Guild Wars** - PvP warfare, sieges
- **Tournaments** - Arena competitions
- **Alliance Events** - Cross-guild activities
- **Daily/Weekly Resets** - Recurring game mechanics
- **Special Events** - Limited-time activities
- **Custom** - User-defined events

### 🛠 Management Commands

#### Admin Commands (Server Owners & Helpers)
```
/admin event_create
    title: "Guild War Finals"
    time_utc: "2025-10-30 20:00" or "20:00" (today)
    category: guild_war
    description: "Optional details"
    recurrence: weekly
    remind_minutes: "60,15,5"

/admin event_list
    Shows all upcoming events for the server

/admin event_delete
    title: "Event name to delete"
```

#### Public Commands
```
/language events
    Shows upcoming events to all members
```

### 📊 Example Usage

**Creating a Weekly Guild War:**
```
/admin event_create 
    title: "Guild War: Storm Peaks"
    time_utc: "2025-10-30 19:00"
    category: guild_war
    description: "All members attack Storm Peaks alliance"
    recurrence: weekly
    remind_minutes: "120,60,15"
```

**Result:** Creates weekly event every Wednesday at 19:00 UTC with reminders at 2h, 1h, and 15m before.

## Architecture

### Components
1. **EventReminderEngine** - Core scheduling and reminder logic
2. **EventManagementCog** - Discord UI commands
3. **GameStorageEngine** - Database persistence
4. **TopHeroesEventScraper** - Automatic event detection

### Database Schema
```sql
CREATE TABLE event_reminders (
    event_id TEXT PRIMARY KEY,
    guild_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    category TEXT NOT NULL,
    event_time_utc TEXT NOT NULL,
    recurrence TEXT NOT NULL,
    custom_interval_hours INTEGER,
    reminder_times TEXT,
    channel_id INTEGER,
    role_to_ping INTEGER,
    created_by INTEGER NOT NULL,
    is_active INTEGER DEFAULT 1,
    auto_scraped INTEGER DEFAULT 0,
    source_url TEXT,
    created_at TEXT NOT NULL
);
```

### Event Flow
1. **Creation** - Admin creates event via `/admin event_create`
2. **Storage** - Event stored in database with UTC timing
3. **Scheduling** - Engine calculates next occurrence and reminder times
4. **Execution** - Automated reminders sent to designated channel
5. **Recurrence** - For recurring events, next occurrence calculated

## Auto-Scraping (Optional)

The system includes a scraper framework for automatically detecting Top Heroes events from:

### Potential Sources
- **Official API** (if Top Heroes provides one)
- **RSS Feeds** (game announcements)
- **Website Parsing** (event calendars)
- **Discord Announcements** (official channels)

### Implementation Notes
The scraper template (`top_heroes_scraper.py`) needs customization based on available Top Heroes data sources. Common integration points:

```python
# Example API integration
api_events = await scraper.scrape_from_api()

# Example website parsing  
web_events = await scraper.scrape_from_website()

# Auto-create events
for event in scraped_events:
    await event_engine.create_event(event)
```

## Setup Instructions

### 1. Database Migration
Events table is automatically created when the bot starts. No manual migration needed.

### 2. Permissions
Ensure your bot has these Discord permissions:
- ✅ Send Messages
- ✅ Embed Links
- ✅ Mention Roles (for role pings)

### 3. Environment Variables
```env
# Optional: Helper role that can manage events
HELPER_ROLE_ID=123456789

# Optional: Auto-scraping interval (hours)
EVENT_SCRAPE_INTERVAL=6
```

### 4. Usage Workflow
1. **Admin creates events** using `/admin event_create`
2. **Bot schedules reminders** automatically
3. **Members see upcoming events** via `/language events`
4. **Automatic reminders** sent before events
5. **Recurring events** automatically reschedule

## Integration with Existing Architecture

### Event-Driven Design
- Uses existing `EventBus` for error handling
- Follows `EngineRegistry` dependency injection pattern
- Integrates with `GuardianErrorEngine` for safe mode

### UI Organization
- Admin commands under `/admin` group
- Public commands under `/language` group
- Follows established permission patterns

### Storage Integration
- Uses existing `GameStorageEngine` for persistence
- Leverages SQLite with `sqlite3.Row` factory
- Auto-migration on bot startup

## Customization Options

### Time Zones
All events stored in UTC, but display can be customized:
```python
# Convert to user's timezone for display
local_time = event_time_utc.astimezone(user_timezone)
```

### Reminder Channels
Events can specify target channels, with fallback logic:
1. Event-specific channel
2. Server "events" or "announcements" channel  
3. "general" channel

### Role Pings
Optional role mentions for important events:
```python
role_to_ping = guild.get_role(event.role_to_ping)
await channel.send(f"{role.mention}", embed=event_embed)
```

### Custom Categories
Easily add new event types by extending `EventCategory` enum:
```python
class EventCategory(Enum):
    CUSTOM_EVENT = "custom_event"
    MAINTENANCE = "maintenance"
    # ... existing categories
```

## Benefits for Top Heroes Coordination

1. **International Timing** - UTC prevents timezone confusion
2. **Automated Reminders** - No manual coordination needed
3. **Role-Based Access** - Only admins/helpers can manage events
4. **Recurring Events** - Set up once, runs automatically
5. **Multiple Reminders** - Ensures no one misses events
6. **Centralized Management** - All events in one place
7. **Future-Proof** - Can integrate with Top Heroes APIs when available

## Future Enhancements

- **User Timezone Preferences** - Display times in user's local timezone
- **Event RSVP System** - Track attendance for events  
- **Event Templates** - Quick creation for common event types
- **Calendar Integration** - Export to Google Calendar/Outlook
- **Event Statistics** - Track participation and success rates
- **Advanced Scraping** - More sophisticated Top Heroes integration