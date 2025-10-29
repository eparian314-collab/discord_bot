"""
Event Reminder System for Top Heroes game coordination.

Features:
- UTC-based scheduling for international guilds
- Recurring events (daily, weekly, monthly)
- Role-based event management (server owners, helpers)
- Automatic reminders with configurable timing
- Event categories (raids, guild wars, tournaments, etc.)
- Optional API scraping for automated event detection
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Set, Any, TYPE_CHECKING
from dataclasses import dataclass, field
from enum import Enum

if TYPE_CHECKING:
    import discord
    from discord.ext import commands

logger = logging.getLogger("hippo_bot.event_reminder")


class EventCategory(Enum):
    """Categories of Top Heroes events."""
    RAID = "raid"
    GUILD_WAR = "guild_war"
    TOURNAMENT = "tournament"
    ALLIANCE_EVENT = "alliance_event"
    DAILY_RESET = "daily_reset"
    WEEKLY_RESET = "weekly_reset"
    SPECIAL_EVENT = "special_event"
    CUSTOM = "custom"


class RecurrenceType(Enum):
    """How often an event repeats."""
    ONCE = "once"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    CUSTOM_INTERVAL = "custom"


@dataclass
class EventReminder:
    """Represents a Top Heroes event reminder."""
    event_id: str
    guild_id: int
    title: str
    description: str
    category: EventCategory
    
    # Timing
    event_time_utc: datetime
    recurrence: RecurrenceType
    custom_interval_hours: Optional[int] = None
    
    # Reminders (minutes before event)
    reminder_times: List[int] = field(default_factory=lambda: [60, 15, 5])
    
    # Settings
    channel_id: Optional[int] = None
    role_to_ping: Optional[int] = None
    created_by: int = 0
    is_active: bool = True
    
    # Auto-scraping
    auto_scraped: bool = False
    source_url: Optional[str] = None
    
    def __post_init__(self):
        """Ensure UTC timezone."""
        if self.event_time_utc.tzinfo is None:
            self.event_time_utc = self.event_time_utc.replace(tzinfo=timezone.utc)
    
    def get_next_occurrence(self, after: Optional[datetime] = None) -> Optional[datetime]:
        """Calculate the next occurrence of this event."""
        if after is None:
            after = datetime.now(timezone.utc)
        
        if self.recurrence == RecurrenceType.ONCE:
            return self.event_time_utc if self.event_time_utc > after else None
        
        current = self.event_time_utc
        
        # Find next occurrence
        while current <= after:
            if self.recurrence == RecurrenceType.DAILY:
                current += timedelta(days=1)
            elif self.recurrence == RecurrenceType.WEEKLY:
                current += timedelta(weeks=1)
            elif self.recurrence == RecurrenceType.MONTHLY:
                # Add approximately one month
                current += timedelta(days=30)
            elif self.recurrence == RecurrenceType.CUSTOM_INTERVAL and self.custom_interval_hours:
                current += timedelta(hours=self.custom_interval_hours)
            else:
                return None
        
        return current
    
    def get_reminder_times(self, event_time: datetime) -> List[datetime]:
        """Get all reminder times for a specific event occurrence."""
        reminders = []
        for minutes_before in self.reminder_times:
            reminder_time = event_time - timedelta(minutes=minutes_before)
            if reminder_time > datetime.now(timezone.utc):
                reminders.append(reminder_time)
        return sorted(reminders)


class EventReminderEngine:
    """Engine for managing Top Heroes event reminders."""
    
    def __init__(self, storage_engine: Any) -> None:
        self.storage = storage_engine
        self.scheduled_tasks: Dict[str, asyncio.Task] = {}
        self.bot: Optional[commands.Bot] = None
        self.is_running = False
    
    def plugin_name(self) -> str:
        return "event_reminder_engine"
    
    def required_dependencies(self) -> Set[str]:
        return {"storage_engine"}
    
    async def on_dependencies_ready(self) -> None:
        """Called when all dependencies are injected."""
        await self.start_scheduler()
    
    def set_bot(self, bot: commands.Bot) -> None:
        """Set the Discord bot instance."""
        self.bot = bot
    
    async def start_scheduler(self) -> None:
        """Start the event reminder scheduler."""
        if self.is_running:
            return
        
        self.is_running = True
        asyncio.create_task(self._scheduler_loop())
        logger.info("🔔 Event reminder scheduler started")
    
    async def stop_scheduler(self) -> None:
        """Stop the scheduler and cancel all tasks."""
        self.is_running = False
        for task in self.scheduled_tasks.values():
            task.cancel()
        self.scheduled_tasks.clear()
        logger.info("🔔 Event reminder scheduler stopped")
    
    async def _scheduler_loop(self) -> None:
        """Main scheduler loop that checks for upcoming reminders."""
        while self.is_running:
            try:
                await self._check_and_schedule_reminders()
                await asyncio.sleep(60)  # Check every minute
            except Exception as exc:
                logger.exception("Error in scheduler loop: %s", exc)
                await asyncio.sleep(300)  # Wait 5 minutes on error
    
    async def _check_and_schedule_reminders(self) -> None:
        """Check for upcoming events and schedule reminders."""
        if not self.bot:
            return
        
        # Get all active events
        events = await self.get_all_events()
        now = datetime.now(timezone.utc)
        
        for event in events:
            if not event.is_active:
                continue
            
            # Get next occurrence
            next_time = event.get_next_occurrence(now)
            if not next_time:
                continue
            
            # Check if we need to schedule reminders
            reminder_times = event.get_reminder_times(next_time)
            
            for reminder_time in reminder_times:
                task_id = f"{event.event_id}_{int(reminder_time.timestamp())}"
                
                # Skip if already scheduled
                if task_id in self.scheduled_tasks:
                    continue
                
                # Schedule the reminder
                delay = (reminder_time - now).total_seconds()
                if delay > 0:
                    task = asyncio.create_task(
                        self._send_reminder_after_delay(delay, event, next_time, reminder_time)
                    )
                    self.scheduled_tasks[task_id] = task
    
    async def _send_reminder_after_delay(
        self, 
        delay: float, 
        event: EventReminder, 
        event_time: datetime,
        reminder_time: datetime
    ) -> None:
        """Send a reminder after a delay."""
        try:
            await asyncio.sleep(delay)
            await self._send_reminder(event, event_time, reminder_time)
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.exception("Error sending reminder for event %s: %s", event.event_id, exc)
    
    async def _send_reminder(
        self, 
        event: EventReminder, 
        event_time: datetime,
        reminder_time: datetime
    ) -> None:
        """Send the actual reminder message."""
        if not self.bot:
            return
        
        guild = self.bot.get_guild(event.guild_id)
        if not guild:
            return
        
        channel = None
        if event.channel_id:
            channel = guild.get_channel(event.channel_id)
        
        if not channel:
            # Try to find a general or announcements channel
            for ch in guild.text_channels:
                if ch.name.lower() in ['general', 'announcements', 'events', 'reminders']:
                    channel = ch
                    break
        
        if not channel:
            logger.warning("No suitable channel found for reminder in guild %s", guild.id)
            return
        
        # Calculate time until event
        time_until = event_time - datetime.now(timezone.utc)
        minutes_until = int(time_until.total_seconds() / 60)
        
        # Create reminder message
        embed = discord.Embed(
            title=f"🔔 {event.category.value.replace('_', ' ').title()} Reminder",
            description=event.title,
            color=self._get_category_color(event.category),
            timestamp=event_time
        )
        
        if event.description:
            embed.add_field(name="Details", value=event.description, inline=False)
        
        # Time formatting
        if minutes_until >= 60:
            time_str = f"{minutes_until // 60}h {minutes_until % 60}m"
        else:
            time_str = f"{minutes_until}m"
        
        embed.add_field(
            name="⏰ Starting In",
            value=time_str,
            inline=True
        )
        
        embed.add_field(
            name="🌍 Event Time (UTC)",
            value=event_time.strftime("%H:%M UTC"),
            inline=True
        )
        
        # Add role ping if specified
        content = None
        if event.role_to_ping:
            role = guild.get_role(event.role_to_ping)
            if role:
                content = f"{role.mention}"
        
        try:
            await channel.send(content=content, embed=embed)
            logger.debug("Sent reminder for event %s", event.event_id)
        except Exception as exc:
            logger.error("Failed to send reminder for event %s: %s", event.event_id, exc)
    
    def _get_category_color(self, category: EventCategory) -> int:
        """Get color for event category."""
        colors = {
            EventCategory.RAID: 0xFF4444,           # Red
            EventCategory.GUILD_WAR: 0xFF8800,      # Orange  
            EventCategory.TOURNAMENT: 0x8844FF,     # Purple
            EventCategory.ALLIANCE_EVENT: 0x4488FF, # Blue
            EventCategory.DAILY_RESET: 0x44FF44,    # Green
            EventCategory.WEEKLY_RESET: 0x44FFFF,   # Cyan
            EventCategory.SPECIAL_EVENT: 0xFFFF44,  # Yellow
            EventCategory.CUSTOM: 0x888888,         # Gray
        }
        return colors.get(category, 0x888888)
    
    # Event management methods
    async def create_event(self, event: EventReminder) -> bool:
        """Create a new event reminder."""
        try:
            # Store in database
            await self._store_event(event)
            logger.info("Created event reminder: %s", event.title)
            return True
        except Exception as exc:
            logger.exception("Failed to create event %s: %s", event.event_id, exc)
            return False
    
    async def update_event(self, event_id: str, **updates) -> bool:
        """Update an existing event."""
        try:
            # Update in database
            await self._update_event(event_id, updates)
            # Cancel and reschedule reminders
            await self._reschedule_event_reminders(event_id)
            return True
        except Exception as exc:
            logger.exception("Failed to update event %s: %s", event_id, exc)
            return False
    
    async def delete_event(self, event_id: str) -> bool:
        """Delete an event and cancel its reminders."""
        try:
            # Cancel scheduled tasks
            tasks_to_cancel = [
                task_id for task_id in self.scheduled_tasks 
                if task_id.startswith(event_id)
            ]
            
            for task_id in tasks_to_cancel:
                task = self.scheduled_tasks.pop(task_id, None)
                if task:
                    task.cancel()
            
            # Remove from database
            await self._delete_event(event_id)
            logger.info("Deleted event reminder: %s", event_id)
            return True
        except Exception as exc:
            logger.exception("Failed to delete event %s: %s", event_id, exc)
            return False
    
    async def get_events_for_guild(self, guild_id: int) -> List[EventReminder]:
        """Get all events for a guild."""
        # Implementation depends on storage backend
        return []
    
    async def get_all_events(self) -> List[EventReminder]:
        """Get all active events across all guilds."""
        # Implementation depends on storage backend
        return []
    
    # Storage interface methods 
    async def _store_event(self, event: EventReminder) -> None:
        """Store event in database."""
        event_data = {
            'event_id': event.event_id,
            'guild_id': event.guild_id,
            'title': event.title,
            'description': event.description,
            'category': event.category.value,
            'event_time_utc': event.event_time_utc.isoformat(),
            'recurrence': event.recurrence.value,
            'custom_interval_hours': event.custom_interval_hours,
            'reminder_times': ','.join(map(str, event.reminder_times)),
            'channel_id': event.channel_id,
            'role_to_ping': event.role_to_ping,
            'created_by': event.created_by,
            'is_active': 1 if event.is_active else 0,
            'auto_scraped': 1 if event.auto_scraped else 0,
            'source_url': event.source_url
        }
        
        success = self.storage.store_event_reminder(event_data)
        if not success:
            raise RuntimeError("Failed to store event in database")
    
    async def _update_event(self, event_id: str, updates: Dict) -> None:
        """Update event in database."""
        # Convert enum values to strings if needed
        processed_updates = {}
        for key, value in updates.items():
            if hasattr(value, 'value'):  # Enum
                processed_updates[key] = value.value
            elif isinstance(value, datetime):
                processed_updates[key] = value.isoformat()
            elif isinstance(value, list) and key == 'reminder_times':
                processed_updates[key] = ','.join(map(str, value))
            else:
                processed_updates[key] = value
        
        success = self.storage.update_event_reminder(event_id, processed_updates)
        if not success:
            raise RuntimeError("Failed to update event in database")
    
    async def _delete_event(self, event_id: str) -> None:
        """Delete event from database."""
        success = self.storage.delete_event_reminder(event_id)
        if not success:
            raise RuntimeError("Failed to delete event from database")
    
    async def get_events_for_guild(self, guild_id: int) -> List[EventReminder]:
        """Get all events for a guild."""
        event_data = self.storage.get_event_reminders(guild_id)
        return [self._data_to_event(data) for data in event_data]
    
    async def get_all_events(self) -> List[EventReminder]:
        """Get all active events across all guilds."""
        event_data = self.storage.get_event_reminders()
        return [self._data_to_event(data) for data in event_data]
    
    def _data_to_event(self, data: Dict[str, Any]) -> EventReminder:
        """Convert database row to EventReminder object."""
        from datetime import datetime, timezone
        
        # Parse reminder times
        reminder_times = []
        if data['reminder_times']:
            reminder_times = [int(x.strip()) for x in data['reminder_times'].split(',') if x.strip()]
        
        return EventReminder(
            event_id=data['event_id'],
            guild_id=data['guild_id'],
            title=data['title'],
            description=data['description'] or '',
            category=EventCategory(data['category']),
            event_time_utc=datetime.fromisoformat(data['event_time_utc']).replace(tzinfo=timezone.utc),
            recurrence=RecurrenceType(data['recurrence']),
            custom_interval_hours=data['custom_interval_hours'],
            reminder_times=reminder_times,
            channel_id=data['channel_id'],
            role_to_ping=data['role_to_ping'],
            created_by=data['created_by'],
            is_active=bool(data['is_active']),
            auto_scraped=bool(data['auto_scraped']),
            source_url=data['source_url']
        )
    
    async def _reschedule_event_reminders(self, event_id: str) -> None:
        """Reschedule reminders for an updated event."""
        # Cancel existing tasks for this event
        tasks_to_cancel = [
            task_id for task_id in self.scheduled_tasks 
            if task_id.startswith(event_id)
        ]
        
        for task_id in tasks_to_cancel:
            task = self.scheduled_tasks.pop(task_id, None)
            if task:
                task.cancel()