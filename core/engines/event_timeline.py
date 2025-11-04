"""
Event Timeline Engine for KVK and GAR Events.

Defines the structure, phases, and timing logic for in-game events.
"""
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional

class EventPhase(Enum):
    """Defines the possible phases of a KVK event."""
    PRE_EVENT = "Pre-Event"
    PREP_STAGE = "Preparation Stage"
    WAR_STAGE = "War Stage"
    POST_EVENT = "Post-Event"
    UNKNOWN = "Unknown"

class EventTimeline:
    """
    Calculates the current phase of a KVK event based on its start date.
    
    A standard KVK event cycle is assumed to be 7 days long:
    - Day 1-2: Prep Stage (Construction, Research)
    - Day 3-5: War Stage (Resource/Mob, Hero, Troop Training)
    - Day 6-7: Cooldown/Post-Event
    """

    def __init__(self, event_start_date: datetime):
        self.start_date = event_start_date

    def get_current_phase(self, now: Optional[datetime] = None) -> EventPhase:
        """
        Determines the current phase of the event.

        Args:
            now: The current datetime to check against. Defaults to utcnow().

        Returns:
            The current EventPhase.
        """
        if not now:
            now = datetime.utcnow()

        if now < self.start_date:
            return EventPhase.PRE_EVENT

        days_since_start = (now - self.start_date).days

        if 0 <= days_since_start < 2:
            return EventPhase.PREP_STAGE
        elif 2 <= days_since_start < 5:
            return EventPhase.WAR_STAGE
        elif 5 <= days_since_start < 7:
            return EventPhase.POST_EVENT
        else:
            # If it's more than a week past, it's considered unknown or the next event
            return EventPhase.UNKNOWN

    def get_current_day_number(self, now: Optional[datetime] = None) -> Optional[int]:
        """
        Determines the current day number (1-5) of the event's active phase.

        Args:
            now: The current datetime. Defaults to utcnow().

        Returns:
            An integer from 1 to 5 if in an active phase, otherwise None.
        """
        if not now:
            now = datetime.utcnow()
            
        phase = self.get_current_phase(now)
        if phase not in [EventPhase.PREP_STAGE, EventPhase.WAR_STAGE]:
            return None

        days_since_start = (now - self.start_date).days
        
        # Day number is 1-based
        day_number = days_since_start + 1
        
        return day_number if 1 <= day_number <= 5 else None

if __name__ == '__main__':
    # Example Usage
    # Assume a KVK event started on Monday, November 3, 2025
    start_of_kvk = datetime(2025, 11, 3, 0, 0, 0)
    timeline = EventTimeline(event_start_date=start_of_kvk)

    # Check phase on different days
    test_date_prep = datetime(2025, 11, 4, 12, 0, 0) # Tuesday
    test_date_war = datetime(2025, 11, 6, 12, 0, 0)  # Thursday
    test_date_post = datetime(2025, 11, 9, 12, 0, 0) # Sunday

    phase_prep = timeline.get_current_phase(test_date_prep)
    day_prep = timeline.get_current_day_number(test_date_prep)
    print(f"On {test_date_prep.strftime('%Y-%m-%d')}, Phase: {phase_prep.value}, Day: {day_prep}")

    phase_war = timeline.get_current_phase(test_date_war)
    day_war = timeline.get_current_day_number(test_date_war)
    print(f"On {test_date_war.strftime('%Y-%m-%d')}, Phase: {phase_war.value}, Day: {day_war}")

    phase_post = timeline.get_current_phase(test_date_post)
    day_post = timeline.get_current_day_number(test_date_post)
    print(f"On {test_date_post.strftime('%Y-%m-%d')}, Phase: {phase_post.value}, Day: {day_post}")
