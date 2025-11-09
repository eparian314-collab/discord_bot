"""Domain models for event reminder workflows."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import List, Optional


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
    event_time_utc: datetime
    recurrence: RecurrenceType
    custom_interval_hours: Optional[int] = None
    reminder_times: List[int] = field(default_factory=lambda: [60, 15, 5])
    channel_id: Optional[int] = None
    role_to_ping: Optional[int] = None
    created_by: int = 0
    is_active: bool = True
    auto_scraped: bool = False
    source_url: Optional[str] = None
    display_id: Optional[str] = None

    def __post_init__(self) -> None:
        if self.event_time_utc.tzinfo is None:
            self.event_time_utc = self.event_time_utc.replace(tzinfo=timezone.utc)

    def get_next_occurrence(self, after: Optional[datetime] = None) -> Optional[datetime]:
        """Calculate the next occurrence of this event."""

        if after is None:
            after = datetime.now(timezone.utc)

        current = self.event_time_utc
        if self.recurrence == RecurrenceType.ONCE and current > after:
            return current
        if self.recurrence == RecurrenceType.ONCE:
            return None

        while current <= after:
            if self.recurrence == RecurrenceType.DAILY:
                current += timedelta(days=1)
            elif self.recurrence == RecurrenceType.WEEKLY:
                current += timedelta(weeks=1)
            elif self.recurrence == RecurrenceType.MONTHLY:
                current += timedelta(days=30)
            elif self.recurrence == RecurrenceType.CUSTOM_INTERVAL and self.custom_interval_hours:
                current += timedelta(hours=self.custom_interval_hours)
            else:
                return None
        return current

    def get_reminder_times(self, event_time: datetime) -> List[datetime]:
        """Get reminder timestamps for a specific occurrence."""

        reminders = []
        now = datetime.now(timezone.utc)
        for minutes_before in self.reminder_times:
            reminder_time = event_time - timedelta(minutes=minutes_before)
            if reminder_time > now:
                reminders.append(reminder_time)
        return sorted(reminders)


__all__ = ["EventCategory", "RecurrenceType", "EventReminder"]
