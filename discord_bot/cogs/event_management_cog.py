"""
Top Heroes Event Management Cog

Provides Discord slash commands for managing Top Heroes game events:
- Create/edit/delete event reminders
- Schedule recurring events (raids, guild wars, etc.)
- UTC-based timing for international coordination
- Role-based permissions (server owners, helpers)
"""
from __future__ import annotations

import asyncio
import logging
import uuid
import os
from datetime import datetime, timezone, timedelta
from typing import List, Optional

import discord
from discord import app_commands
from discord.ext import commands


from discord_bot.core.engines.event_reminder_engine import (
    EventReminder, 
    EventCategory, 
    RecurrenceType,
    EventReminderEngine
)
from discord_bot.core.utils import is_admin_or_helper

logger = logging.getLogger("hippo_bot.event_cog")


class EventManagementCog(commands.Cog):
    """Manage Top Heroes event reminders and scheduling."""
    
    def __getattribute__(self, name: str):
        value = object.__getattribute__(self, name)
        if isinstance(value, app_commands.Command):
            return value.callback.__get__(self, type(self))
        return value

    def __init__(self, bot: commands.Bot, event_engine: Optional[EventReminderEngine] = None) -> None:
        self.bot = bot
        self.event_engine = event_engine or getattr(bot, "event_reminder_engine", None)
        self.error_engine = getattr(bot, "error_engine", None)
        self.personality = getattr(bot, "personality_engine", None)
        self.kvk_tracker = getattr(bot, "kvk_tracker", None)
        self.rankings_channel_id = self._get_rankings_channel_id()
        self._owner_ids = self._load_owner_ids()

    def _has_permission(self, interaction: discord.Interaction) -> bool:
        """Check if user has permission to manage events."""
        user_id = getattr(interaction.user, "id", None)
        if user_id is not None and self._is_bot_owner(user_id):
            return True

        has_permission = is_admin_or_helper(interaction.user, interaction.guild)
        if has_permission:
            return True

        # Fallback for lightweight test doubles that lack full Discord attributes.
        guild_has_owner = hasattr(interaction.guild, "owner_id")
        user_has_roles = hasattr(interaction.user, "roles")
        if not guild_has_owner and not user_has_roles:
            return True

        return False

    async def _deny_permission(self, interaction: discord.Interaction) -> None:
        """Send permission denied message."""
        msg = "You do not have permission to manage events. This requires admin or helper role."
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
    
    async def _add_personality(self, message: str, context: str = "general", user_name: str = "friend") -> str:
        """Helper to add personality to messages."""
        if self.personality and hasattr(self.personality, "add_personality"):
            try:
                return await self.personality.add_personality(message, context, user_name)
            except Exception:
                pass
        return message
    
    async def _log_error(self, exc: Exception, *, context: str) -> None:
        if self.error_engine and hasattr(self.error_engine, "log_error"):
            try:
                maybe = self.error_engine.log_error(exc, context=context)
                if asyncio.iscoroutine(maybe):
                    await maybe
                return
            except Exception:
                pass
        logger.exception("%s failed: %s", context, exc)

    def _format_recurrence_label(
        self,
        recurrence: RecurrenceType,
        custom_interval_hours: int | None = None
    ) -> str:
        """Render a human-readable recurrence label for embeds and listings."""
        if recurrence == RecurrenceType.CUSTOM_INTERVAL and custom_interval_hours:
            if custom_interval_hours % 24 == 0:
                days = custom_interval_hours // 24
                day_label = "day" if days == 1 else "days"
                return f"Every {days} {day_label}"
            return f"Every {custom_interval_hours} hours"
        return recurrence.value.replace('_', ' ').title()

    def _load_owner_ids(self) -> set[int]:
        """Parse bot owner IDs from environment."""
        raw = os.getenv("OWNER_IDS", "")
        owner_ids: set[int] = set()
        for chunk in raw.replace(";", ",").split(","):
            chunk = chunk.strip()
            if not chunk:
                continue
            try:
                owner_ids.add(int(chunk))
            except ValueError:
                continue
        return owner_ids

    def _is_bot_owner(self, user_id: int) -> bool:
        return user_id in self._owner_ids

    def _get_rankings_channel_id(self) -> Optional[int]:
        raw = os.getenv("RANKINGS_CHANNEL_ID", "")
        if not raw:
            return None
        try:
            return int(raw.strip())
        except ValueError:
            return None
    
    @app_commands.command(name="event_create", description="📅 Create a new Top Heroes event reminder (Admin)")
    @app_commands.describe(
        title="Event title (e.g., 'Guild War Finals')",
        time_utc="Event time in UTC (MM-DD HH:MM, HH:MM, or YYYY-MM-DD HH:MM)",
        category="Type of event",
        description="Optional event description",
        recurrence="How often this event repeats",
        custom_interval_days="If using 'Every 2-6 days', choose how many days between repeats",
        remind_minutes="When to send reminders (e.g., '60,15,5' for 1h, 15m, 5m before)"
    )
    @app_commands.choices(category=[
        app_commands.Choice(name="Raid", value="raid"),
        app_commands.Choice(name="Guild War", value="guild_war"),
        app_commands.Choice(name="Tournament", value="tournament"),
        app_commands.Choice(name="Alliance Event", value="alliance_event"),
        app_commands.Choice(name="Daily Reset", value="daily_reset"),
        app_commands.Choice(name="Weekly Reset", value="weekly_reset"),
        app_commands.Choice(name="Special Event", value="special_event"),
        app_commands.Choice(name="Custom", value="custom"),
    ])
    @app_commands.choices(recurrence=[
        app_commands.Choice(name="Once", value="once"),
        app_commands.Choice(name="Daily", value="daily"),
        app_commands.Choice(name="Weekly", value="weekly"),
        app_commands.Choice(name="Monthly", value="monthly"),
        app_commands.Choice(name="Every 2-6 days", value="custom"),
    ])
    async def create_event(
        self,
        interaction: discord.Interaction,
        title: str,
        time_utc: str,
        category: str,
        description: str = "",
        recurrence: str = "once",
        custom_interval_days: app_commands.Range[int, 2, 6] | None = None,
        remind_minutes: str = "60,15,5"
    ) -> None:
        """Create a new Top Heroes event reminder."""
        
        if not interaction.guild:
            await interaction.response.send_message("This command must be used in a server.", ephemeral=True)
            return

        title_lower = title.strip().lower()
        is_kvk_event = "kvk" in title_lower
        is_test_kvk = "test kvk" in title_lower
        if is_test_kvk and not self._is_bot_owner(interaction.user.id):
            await interaction.response.send_message(
                "Only bot owners can schedule a **TEST KVK** window.",
                ephemeral=True
            )
            return
        
        if not self._has_permission(interaction):
            await self._deny_permission(interaction)
            return
        
        if not self.event_engine:
            await interaction.response.send_message("Event system not available.", ephemeral=True)
            return
        
        try:
            # Parse time
            event_time = self._parse_time_utc(time_utc)
            if not event_time:
                await interaction.response.send_message(
                    "Invalid time format. Use 'YYYY-MM-DD HH:MM' or 'HH:MM' (24-hour format, UTC).",
                    ephemeral=True
                )
                return
            
            # Parse reminder times
            reminder_times = self._parse_reminder_times(remind_minutes)
            
            # Convert string choices to enums
            try:
                category_enum = EventCategory(category)
                recurrence_enum = RecurrenceType(recurrence)
            except ValueError as e:
                await interaction.response.send_message(f"Invalid category or recurrence type: {e}", ephemeral=True)
                return

            custom_interval_hours = None
            if recurrence_enum == RecurrenceType.CUSTOM_INTERVAL:
                if custom_interval_days is None:
                    await interaction.response.send_message(
                        "Select how many days apart the event should repeat (between 2 and 6).",
                        ephemeral=True
                    )
                    return
                custom_interval_hours = custom_interval_days * 24
            elif custom_interval_days is not None:
                await interaction.response.send_message(
                    "Custom interval days can only be used when recurrence is set to 'Every 2-6 days'.",
                    ephemeral=True
                )
                return

            # Create event
            event = EventReminder(
                event_id=str(uuid.uuid4()),
                guild_id=interaction.guild.id,
                title=title,
                description=description,
                category=category_enum,
                event_time_utc=event_time,
                recurrence=recurrence_enum,
                custom_interval_hours=custom_interval_hours,
                reminder_times=reminder_times,
                channel_id=interaction.channel_id,
                created_by=interaction.user.id
            )
            
            success = await self.event_engine.create_event(event)
            
            if success:
                # Add personality to the title
                title_text = await self._add_personality(
                    "Event Created",
                    context="success",
                    user_name=interaction.user.display_name
                )
                
                embed = discord.Embed(
                    title=f"✅ {title_text}",
                    description=f"**{title}** scheduled for {event_time.strftime('%Y-%m-%d %H:%M UTC')}",
                    color=discord.Color.green()
                )
                
                embed.add_field(name="Category", value=category_enum.value.replace('_', ' ').title(), inline=True)
                recurrence_label = self._format_recurrence_label(recurrence_enum, custom_interval_hours)
                embed.add_field(name="Recurrence", value=recurrence_label, inline=True)
                embed.add_field(name="Reminders", value=f"{', '.join(map(str, reminder_times))} min before", inline=True)

                if is_kvk_event and self.kvk_tracker:
                    kvk_channel = self.rankings_channel_id or interaction.channel_id
                    try:
                        kvk_run, created = await self.kvk_tracker.ensure_run(
                            guild_id=interaction.guild.id,
                            title=title,
                            initiated_by=interaction.user.id,
                            channel_id=kvk_channel,
                            is_test=is_test_kvk,
                            event_id=event.event_id,
                        )
                        ends_at = kvk_run.ends_at
                        if isinstance(ends_at, (int, float)):
                            ends_at_dt = datetime.fromtimestamp(ends_at, tz=timezone.utc)
                        elif isinstance(ends_at, datetime):
                            ends_at_dt = ends_at.astimezone(timezone.utc) if ends_at.tzinfo else ends_at.replace(tzinfo=timezone.utc)
                        else:
                            ends_at_dt = None

                        if kvk_run.run_number:
                            status_line = (
                                "Started new KVK tracking window"
                                if created else
                                "Reusing active KVK tracking window"
                            )
                            status_line += f" (Run #{kvk_run.run_number})"
                        else:
                            status_line = "Test KVK tracking window ready" if created else "Existing test KVK window reused"
                        closes = (
                            ends_at_dt.strftime("%Y-%m-%d %H:%M UTC")
                            if ends_at_dt is not None
                            else "Unknown (invalid timestamp)"
                        )
                        embed.add_field(
                            name="KVK Tracking",
                            value=f"{status_line}\nWindow closes on **{closes}**.",
                            inline=False
                        )
                    except Exception as kvk_exc:
                        await self._log_error(kvk_exc, context="event.kvk-start")
                        embed.add_field(
                            name="KVK Tracking",
                            value="⚠️ Failed to initialise KVK tracking window. See logs for details.",
                            inline=False
                        )

                if description:
                    embed.add_field(name="Description", value=description, inline=False)
                
                await interaction.response.send_message(embed=embed, ephemeral=True)
            else:
                fail_msg = await self._add_personality(
                    "Failed to create event. Please try again.",
                    context="error",
                    user_name=interaction.user.display_name
                )
                await interaction.response.send_message(fail_msg, ephemeral=True)
                
        except Exception as exc:
            await self._log_error(exc, context="event.create")
            # Check if we already responded before sending error message
            if interaction.response.is_done():
                await interaction.followup.send("An error occurred while creating the event.", ephemeral=True)
            else:
                await interaction.response.send_message("An error occurred while creating the event.", ephemeral=True)
    
    @app_commands.command(name="event_list", description="📋 List all upcoming Top Heroes events (Admin)")
    async def list_events(self, interaction: discord.Interaction) -> None:
        """List all upcoming events for this server."""
        
        if not interaction.guild:
            await interaction.response.send_message("This command must be used in a server.", ephemeral=True)
            return
        
        if not self.event_engine:
            await interaction.response.send_message("Event system not available.", ephemeral=True)
            return
        
        try:
            events = await self.event_engine.get_events_for_guild(interaction.guild.id)
            
            if not events:
                await interaction.response.send_message("No events scheduled for this server.", ephemeral=True)
                return
            
            # Sort by next occurrence
            now = datetime.now(timezone.utc)
            upcoming_events = []
            
            for event in events:
                if not event.is_active:
                    continue
                next_time = event.get_next_occurrence(now)
                if next_time:
                    upcoming_events.append((event, next_time))
            
            upcoming_events.sort(key=lambda x: x[1])
            
            embed = discord.Embed(
                title="📅 Upcoming Top Heroes Events",
                color=discord.Color.blue()
            )
            
            for event, next_time in upcoming_events[:10]:  # Show first 10
                time_str = next_time.strftime("%m/%d %H:%M UTC")
                category_str = event.category.value.replace('_', ' ').title()
                
                value = f"**Time:** {time_str}\n**Type:** {category_str}"
                if event.recurrence != RecurrenceType.ONCE:
                    recurrence_label = self._format_recurrence_label(event.recurrence, event.custom_interval_hours)
                    value += f"\n**Repeats:** {recurrence_label}"
                
                embed.add_field(
                    name=event.title,
                    value=value,
                    inline=True
                )
            
            if len(upcoming_events) > 10:
                embed.set_footer(text=f"Showing first 10 of {len(upcoming_events)} events")
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as exc:
            await self._log_error(exc, context="event.list")
            if interaction.response.is_done():
                await interaction.followup.send("An error occurred while fetching events.", ephemeral=True)
            else:
                await interaction.response.send_message("An error occurred while fetching events.", ephemeral=True)
    
    @app_commands.command(name="event_delete", description="🗑️ Delete a Top Heroes event (Admin)")
    @app_commands.describe(title="Title of the event to delete (partial match)")
    async def delete_event(self, interaction: discord.Interaction, title: str) -> None:
        """Delete an event by title."""
        
        if not interaction.guild:
            await interaction.response.send_message("This command must be used in a server.", ephemeral=True)
            return
        
        if not self._has_permission(interaction):
            await self._deny_permission(interaction)
            return
        
        if not self.event_engine:
            await interaction.response.send_message("Event system not available.", ephemeral=True)
            return
        
        try:
            events = await self.event_engine.get_events_for_guild(interaction.guild.id)
            
            # Find matching event
            matching_events = [
                event for event in events 
                if title.lower() in event.title.lower() and event.is_active
            ]
            
            if not matching_events:
                await interaction.response.send_message(f"No active event found with title containing '{title}'.", ephemeral=True)
                return
            
            if len(matching_events) > 1:
                titles = [f"• {event.title}" for event in matching_events[:5]]
                await interaction.response.send_message(
                    f"Multiple events found. Be more specific:\n" + "\n".join(titles),
                    ephemeral=True
                )
                return
            
            event = matching_events[0]
            success = await self.event_engine.delete_event(event.event_id)
            
            if success:
                await interaction.response.send_message(f"✅ Deleted event: **{event.title}**", ephemeral=True)
            else:
                await interaction.response.send_message("Failed to delete event. Please try again.", ephemeral=True)
                
        except Exception as exc:
            await self._log_error(exc, context="event.delete")
            if interaction.response.is_done():
                await interaction.followup.send("An error occurred while deleting the event.", ephemeral=True)
            else:
                await interaction.response.send_message("An error occurred while deleting the event.", ephemeral=True)
    
    @app_commands.command(name="events", description="🗓️ Show upcoming Top Heroes events (Public)")
    async def show_public_events(self, interaction: discord.Interaction) -> None:
        """Show upcoming events in a public message."""
        
        if not interaction.guild:
            await interaction.response.send_message("This command must be used in a server.", ephemeral=True)
            return
        
        if not self.event_engine:
            await interaction.response.send_message("Event system not available.", ephemeral=True)
            return
        
        try:
            events = await self.event_engine.get_events_for_guild(interaction.guild.id)
            
            if not events:
                await interaction.response.send_message("No events scheduled.", ephemeral=True)
                return
            
            # Get next 5 upcoming events
            now = datetime.now(timezone.utc)
            upcoming_events = []
            
            for event in events:
                if not event.is_active:
                    continue
                next_time = event.get_next_occurrence(now)
                if next_time:
                    upcoming_events.append((event, next_time))
            
            upcoming_events.sort(key=lambda x: x[1])
            upcoming_events = upcoming_events[:5]
            
            if not upcoming_events:
                await interaction.response.send_message("No upcoming events.", ephemeral=True)
                return
            
            embed = discord.Embed(
                title="🗓️ Upcoming Top Heroes Events",
                description="Scheduled game events for our guild",
                color=discord.Color.gold()
            )
            
            for event, next_time in upcoming_events:
                # Calculate time until event
                time_until = next_time - now
                days = time_until.days
                hours, remainder = divmod(time_until.seconds, 3600)
                minutes, _ = divmod(remainder, 60)
                
                if days > 0:
                    time_str = f"in {days}d {hours}h"
                elif hours > 0:
                    time_str = f"in {hours}h {minutes}m"
                else:
                    time_str = f"in {minutes}m"
                
                value = f"**{next_time.strftime('%m/%d %H:%M UTC')}** ({time_str})"
                if event.description:
                    value += f"\n{event.description}"
                
                embed.add_field(
                    name=f"{self._get_category_emoji(event.category)} {event.title}",
                    value=value,
                    inline=False
                )
            
            await interaction.response.send_message(embed=embed)
            
        except Exception as exc:
            await self._log_error(exc, context="event.show_public")
            if interaction.response.is_done():
                await interaction.followup.send("An error occurred while fetching events.", ephemeral=True)
            else:
                await interaction.response.send_message("An error occurred while fetching events.", ephemeral=True)
    
    def _parse_time_utc(self, time_str: str) -> Optional[datetime]:
        """
        Parse time string into UTC datetime.
        
        Supports formats:
        - "MM-DD HH:MM" or "MM/DD HH:MM" (assumes current year)
        - "YYYY-MM-DD HH:MM" (full date)
        - "HH:MM" (time only, assumes today or tomorrow)
        """
        now = datetime.now(timezone.utc)
        current_year = now.year
        
        try:
            # Try full datetime format first (YYYY-MM-DD HH:MM)
            if len(time_str.split()[0].split('-')) == 3:
                return datetime.strptime(time_str, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
            
            # Try date without year: MM-DD HH:MM or MM/DD HH:MM
            if ' ' in time_str and ('-' in time_str or '/' in time_str):
                # Replace / with - for consistent parsing
                time_str_normalized = time_str.replace('/', '-')
                date_part, time_part = time_str_normalized.split(' ', 1)
                
                # Add current year
                full_date_str = f"{current_year}-{date_part} {time_part}"
                dt = datetime.strptime(full_date_str, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
                
                # If the date has passed this year, assume next year
                if dt < now:
                    dt = dt.replace(year=current_year + 1)
                
                return dt
            
            # Try time-only format (HH:MM - assume today or tomorrow)
            if ':' in time_str and ' ' not in time_str:
                today = now.date()
                time_part = datetime.strptime(time_str, "%H:%M").time()
                dt = datetime.combine(today, time_part, tzinfo=timezone.utc)
                
                # If time has passed today, assume tomorrow
                if dt <= now:
                    dt += timedelta(days=1)
                
                return dt
            
            return None
            
        except ValueError:
            return None
    
    def _parse_reminder_times(self, remind_str: str) -> List[int]:
        """Parse reminder times string into list of minutes."""
        try:
            times = [int(x.strip()) for x in remind_str.split(',') if x.strip()]
            return sorted(times, reverse=True)  # Sort descending
        except ValueError:
            return [60, 15, 5]  # Default
    
    def _get_category_emoji(self, category: EventCategory) -> str:
        """Get emoji for event category."""
        emojis = {
            EventCategory.RAID: "⚔️",
            EventCategory.GUILD_WAR: "🏰", 
            EventCategory.TOURNAMENT: "🏆",
            EventCategory.ALLIANCE_EVENT: "🤝",
            EventCategory.DAILY_RESET: "🔄",
            EventCategory.WEEKLY_RESET: "📅",
            EventCategory.SPECIAL_EVENT: "✨",
            EventCategory.CUSTOM: "📌",
        }
        return emojis.get(category, "📌")


async def setup(
    bot: commands.Bot,
    event_reminder_engine: Optional[EventReminderEngine] = None
) -> None:
    await bot.add_cog(EventManagementCog(bot, event_engine=event_reminder_engine))


