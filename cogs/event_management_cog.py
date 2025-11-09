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
import inspect
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

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

    EVENT_ID_PREFIX = 8
    EVENT_ID_DELIMITER = ":"
    CATEGORY_TYPE_CODES: Dict[EventCategory, str] = {
        EventCategory.GUILD_WAR: "1",
        EventCategory.RAID: "2",
        EventCategory.TOURNAMENT: "3",
        EventCategory.ALLIANCE_EVENT: "4",
        EventCategory.DAILY_RESET: "5",
        EventCategory.WEEKLY_RESET: "6",
        EventCategory.SPECIAL_EVENT: "7",
        EventCategory.CUSTOM: "8",
    }

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

    async def _safe_send_response(
        self,
        interaction: discord.Interaction,
        *,
        content: str | None = None,
        embed: discord.Embed | None = None,
        ephemeral: bool = True
    ) -> bool:
        """Attempt to respond to an interaction without double-acknowledging."""
        if content is None and embed is None:
            return False

        payload: dict[str, Any] = {"ephemeral": ephemeral}
        if content is not None:
            payload["content"] = content
        if embed is not None:
            payload["embed"] = embed

        if interaction.response.is_done():
            try:
                await interaction.followup.send(**payload)
                return True
            except discord.NotFound:
                logger.warning("Interaction follow-up not found while sending reply.")
                return False
            except discord.HTTPException as exc:
                if exc.code == 40060:
                    logger.warning("Interaction already acknowledged; skipping follow-up.")
                    return False
                raise

        try:
            await interaction.response.send_message(**payload)
            return True
        except discord.NotFound:
            logger.warning("Interaction response not found while sending reply.")
        except discord.HTTPException as exc:
            if exc.code == 40060:
                logger.warning("Interaction already acknowledged; skipping response.")
            else:
                raise
        return False
    
    async def _close_kvk_run_for_event(self, event_id: str) -> None:
        """Close a KVK run that was tied to the given event, if any."""
        if not self.kvk_tracker:
            return
        try:
            closed_run = await self.kvk_tracker.close_run_for_event(event_id, reason="event deleted")
            if closed_run:
                logger.info("Closed KVK run %s linked to deleted event %s", closed_run.id, event_id)
        except Exception as exc:
            await self._log_error(exc, context="event.kvk-close")

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

    def _compose_event_storage_id(self, guild_id: int, display_id: str) -> str:
        return f"{guild_id}{self.EVENT_ID_DELIMITER}{display_id}"

    def _parse_display_id_from_raw(self, event_id: str) -> Optional[str]:
        if not event_id:
            return None
        if self.EVENT_ID_DELIMITER in event_id:
            _, suffix = event_id.split(self.EVENT_ID_DELIMITER, 1)
            if suffix:
                return suffix
        return None

    def _get_display_id(self, event: EventReminder) -> str:
        existing = getattr(event, "display_id", None)
        if existing:
            return existing
        computed = self._parse_display_id_from_raw(event.event_id) or (event.event_id or "")[-self.EVENT_ID_PREFIX:]
        event.display_id = computed  # cache for later use
        return computed

    def _letters_to_index(self, letters: str) -> int:
        value = 0
        for ch in letters.upper():
            if not ch.isalpha():
                continue
            value = value * 26 + (ord(ch) - ord("A") + 1)
        return value

    def _index_to_letters(self, index: int) -> str:
        if index <= 0:
            return "A"
        result = ""
        while index > 0:
            index, rem = divmod(index - 1, 26)
            result = chr(ord("A") + rem) + result
        return result or "A"

    async def _allocate_display_id(
        self,
        guild_id: int,
        category: EventCategory,
    ) -> str:
        type_code = self.CATEGORY_TYPE_CODES.get(category, "9")
        allocator = getattr(self.event_engine, "allocate_display_index", None) if self.event_engine else None
        if allocator:
            try:
                next_index = allocator(guild_id, category)
                if inspect.isawaitable(next_index):
                    next_index = await next_index
                if isinstance(next_index, int) and next_index > 0:
                    return f"{type_code}{self._index_to_letters(next_index)}"
            except Exception as exc:
                logger.warning(
                    "event.display_id.sequence_fallback guild=%s category=%s reason=%s",
                    guild_id,
                    category.value,
                    exc,
                )

        existing_events = []
        if self.event_engine:
            existing_events = await self.event_engine.get_events_for_guild(guild_id)
        max_index = 0
        for event in existing_events:
            if event.guild_id != guild_id:
                continue
            display_id = self._get_display_id(event)
            if not display_id.upper().startswith(type_code):
                continue
            suffix = display_id[len(type_code):] or "A"
            index = self._letters_to_index(suffix)
            max_index = max(max_index, index)
        next_index = max_index + 1
        return f"{type_code}{self._index_to_letters(next_index)}"

    def _match_events_by_identifier(
        self,
        events: List[EventReminder],
        token: str,
        *,
        exact: bool = False,
        active_only: bool = True,
    ) -> List[EventReminder]:
        normalized = token.strip().lower()
        if not normalized:
            return []
        matches: List[EventReminder] = []
        for event in events:
            if active_only and not event.is_active:
                continue
            display_id = self._get_display_id(event).lower()
            event_id_lower = (event.event_id or "").lower()
            if exact:
                if display_id == normalized or event_id_lower == normalized:
                    matches.append(event)
            else:
                if display_id.startswith(normalized) or event_id_lower.startswith(normalized):
                    matches.append(event)
        return matches

    def _format_event_label(self, event: EventReminder) -> str:
        """Return a short label for an event with ID prefix."""
        display_id = self._get_display_id(event)
        return f"{event.title} (`{display_id}`)"

    def _match_events_by_id_prefix(self, events: List[EventReminder], token: str) -> List[EventReminder]:
        """Return events whose IDs (storage or display) start with the provided token (case-insensitive)."""
        return self._match_events_by_identifier(events, token, exact=False)

    def _match_events_by_title(self, events: List[EventReminder], fragment: str) -> List[EventReminder]:
        """Return events whose titles contain the fragment."""
        normalized = fragment.strip().lower()
        if not normalized:
            return []
        return [
            event
            for event in events
            if normalized in event.title.lower()
        ]

    async def _cleanup_test_kvk_events(self, guild_id: int) -> List[EventReminder]:
        """Remove any lingering 'test kvk' events so new ones do not stack up."""
        if not self.event_engine:
            return []
        existing = await self.event_engine.get_events_for_guild(guild_id)
        stale = [
            event
            for event in existing
            if event.is_active and "test kvk" in event.title.lower()
        ]
        removed: List[EventReminder] = []
        for event in stale:
            success = await self.event_engine.delete_event(event.event_id)
            if success:
                removed.append(event)
        return removed
    
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
        if is_test_kvk:
            already_test_active = await self.event_engine.has_active_test_kvk(interaction.guild.id)
            if already_test_active:
                await self._safe_send_response(
                    interaction,
                    content="A TEST KVK cycle is already scheduled on this server. Delete or await its completion before creating another.",
                    ephemeral=True,
                )
                return
        
        try:
            removed_test_events: List[EventReminder] = []
            if is_test_kvk:
                removed_test_events = await self._cleanup_test_kvk_events(interaction.guild.id)

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

            display_id = await self._allocate_display_id(interaction.guild.id, category_enum)
            storage_event_id = self._compose_event_storage_id(interaction.guild.id, display_id)

            # Create event
            event = EventReminder(
                event_id=storage_event_id,
                guild_id=interaction.guild.id,
                title=title,
                description=description,
                category=category_enum,
                event_time_utc=event_time,
                recurrence=recurrence_enum,
                custom_interval_hours=custom_interval_hours,
                reminder_times=reminder_times,
                channel_id=interaction.channel_id,
                created_by=interaction.user.id,
                display_id=display_id,
                is_test_kvk=is_test_kvk
            )
            
            success = await self.event_engine.create_event(event)
            
            if success:
                logger.info(
                    "event.create.success guild=%s event_id=%s display=%s title=%s",
                    interaction.guild.id,
                    event.event_id,
                    display_id,
                    title,
                )
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
                embed.add_field(
                    name="Event ID",
                    value=f"`{self._get_display_id(event)}` (use with `/event_edit` or `/event_delete`)",
                    inline=False,
                )

                if is_kvk_event and self.kvk_tracker:
                    try:
                        run, is_new = await self.kvk_tracker.ensure_run(
                            guild_id=interaction.guild.id,
                            title=title,
                            initiated_by=interaction.user.id,
                            is_test=is_test_kvk,
                            channel_id=self.rankings_channel_id or interaction.channel_id,
                            event_id=event.event_id,
                        )
                        if is_new:
                            logger.info("Started new KVK run #%d for guild %d", run.id, interaction.guild.id)
                            status_line = f"Started new KVK tracking window (Run #{run.run_number})"
                        else:
                            status_line = f"Reusing active KVK tracking window (Run #{run.run_number})"
                        closes = run.ends_at.strftime("%Y-%m-%d %H:%M UTC") if hasattr(run.ends_at, 'strftime') else str(run.ends_at)
                        embed.add_field(
                            name="KVK Tracking",
                            value=f"{status_line}\nWindow closes on **{closes}**.",
                            inline=False
                        )
                    except Exception as kvk_exc:
                        await self._log_error(kvk_exc, context="event.kvk-start")
                        embed.add_field(
                            name="KVK Tracking",
                            value=f"⚠️ Failed to initialise KVK tracking window.\n`{kvk_exc}`",
                            inline=False
                        )

                if description:
                    embed.add_field(name="Description", value=description, inline=False)

                if removed_test_events:
                    removed_lines = "\n".join(f"\u2022 {self._format_event_label(evt)}" for evt in removed_test_events[:5])
                    if len(removed_test_events) > 5:
                        removed_lines += f"\n\u2026{len(removed_test_events) - 5} more."
                    embed.add_field(
                        name="Test KVK Cleanup",
                        value=f"Removed {len(removed_test_events)} prior test KVK event(s):\n{removed_lines}",
                        inline=False,
                    )

                await self._safe_send_response(interaction, embed=embed, ephemeral=True)
            else:
                fail_msg = await self._add_personality(
                    "Failed to create event. Please try again.",
                    context="error",
                    user_name=interaction.user.display_name
                )
                await self._safe_send_response(interaction, content=fail_msg, ephemeral=True)
                
        except Exception as exc:
            await self._log_error(exc, context="event.create")
            await self._safe_send_response(
                interaction,
                content="An error occurred while creating the event.",
                ephemeral=True
            )
    
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
                
                value = f"**ID:** `{self._get_display_id(event)}`\n**Time:** {time_str}\n**Type:** {category_str}"
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
    
    @app_commands.command(name="event_delete", description="🗑️ Delete one or more Top Heroes events (Admin)")
    @app_commands.describe(
        identifier="Event ID/prefix or title fragment. Use commas to delete multiple IDs."
    )
    async def delete_event(self, interaction: discord.Interaction, identifier: str) -> None:
        """Delete events via ID prefix or title fragment."""
        
        if not interaction.guild:
            await interaction.response.send_message("This command must be used in a server.", ephemeral=True)
            return
        
        if not self._has_permission(interaction):
            await self._deny_permission(interaction)
            return
        
        if not self.event_engine:
            await self._safe_send_response(interaction, content="Event system not available.", ephemeral=True)
            return
        
        raw_identifier = identifier.strip()
        if not raw_identifier:
            await interaction.response.send_message("Provide an event ID/prefix or part of the title.", ephemeral=True)
            return
        
        try:
            events = await self.event_engine.get_events_for_guild(interaction.guild.id)
            active_events = [event for event in events if event.is_active]
            tokens = [token.strip() for token in raw_identifier.split(",") if token.strip()]
            multi_mode = len(tokens) > 1
            
            deleted: List[str] = []
            failures: List[str] = []
            
            async def delete_single(event: EventReminder) -> None:
                success = await self.event_engine.delete_event(event.event_id)
                label = self._format_event_label(event)
                if success:
                    deleted.append(label)
                else:
                    failures.append(f"{label} - delete failed")
            
            if multi_mode:
                for token in tokens:
                    matches = self._match_events_by_identifier(active_events, token, exact=True)
                    if not matches:
                        failures.append(f"`{token}` - no matching event ID")
                        continue
                    if len(matches) > 1:
                        preview = ', '.join(self._format_event_label(evt) for evt in matches[:3])
                        failures.append(f"`{token}` - matched multiple events: {preview}")
                        continue
                    await delete_single(matches[0])
            else:
                token = tokens[0] if tokens else raw_identifier
                matches = self._match_events_by_identifier(active_events, token, exact=False)
                if not matches:
                    matches = self._match_events_by_title(active_events, token)
                if not matches:
                    await interaction.response.send_message(
                        f"No active event matched `{token}`. Use `/event_list` to copy IDs.",
                        ephemeral=True
                    )
                    return
                if len(matches) > 1:
                    preview = "\n".join(f"• {self._format_event_label(evt)}" for evt in matches[:5])
                    await interaction.response.send_message(
                        f"Multiple events matched `{token}`. Specify the ID prefix:\n{preview}",
                        ephemeral=True
                    )
                    return
                await delete_single(matches[0])
            if deleted:
                message = "Deleted events:\n" + "\n".join(f"• {label}" for label in deleted)
                if failures:
                    message += "\n\nIssues:\n" + "\n".join(f"- {note}" for note in failures)
                await interaction.response.send_message(message, ephemeral=True)
            else:
                failure_text = "\n".join(f"- {note}" for note in failures) if failures else "No matching events."
                await interaction.response.send_message(f"Nothing was deleted:\n{failure_text}", ephemeral=True)
                
        except Exception as exc:
            await self._log_error(exc, context="event.delete")
            if interaction.response.is_done():
                await interaction.followup.send("An error occurred while deleting the event.", ephemeral=True)
            else:
                await interaction.response.send_message("An error occurred while deleting the event.", ephemeral=True)

    @app_commands.command(name="event_edit", description="✏️ Edit an existing Top Heroes event (Admin)")
    @app_commands.describe(
        event_id="Event ID or prefix (see /event_list)",
        title="New title",
        time_utc="New time in UTC (same formats as /event_create)",
        description="Updated description",
        remind_minutes="Comma-separated reminder minutes (e.g., 60,30,5)",
        custom_interval_days="If recurrence is 'Every 2-6 days', provide the interval",
        active="Set to False to disable the event without deleting it"
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
    async def edit_event(
        self,
        interaction: discord.Interaction,
        event_id: str,
        title: Optional[str] = None,
        time_utc: Optional[str] = None,
        description: Optional[str] = None,
        remind_minutes: Optional[str] = None,
        category: Optional[str] = None,
        recurrence: Optional[str] = None,
        custom_interval_days: app_commands.Range[int, 2, 6] | None = None,
        active: Optional[bool] = None,
    ) -> None:
        """Edit stored event metadata without recreating it."""
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
            matches = self._match_events_by_identifier(events, event_id, exact=False, active_only=False)
            if not matches:
                await interaction.response.send_message(
                    f"No event found with ID `{event_id}`. Use `/event_list` to copy IDs.",
                    ephemeral=True,
                )
                return
            if len(matches) > 1:
                preview = "\n".join(f"- {self._format_event_label(evt)}" for evt in matches[:5])
                await interaction.response.send_message(
                    f"Multiple events share that ID. Use a longer identifier:\n{preview}",
                    ephemeral=True,
                )
                return
            event = matches[0]
            
            updates: Dict[str, Any] = {}
            summary: List[str] = []
            
            if title:
                updates["title"] = title
                summary.append(f"- Title -> **{title}**")
            
            if time_utc:
                new_time = self._parse_time_utc(time_utc)
                if not new_time:
                    await interaction.response.send_message(
                        "Invalid time format. Use 'YYYY-MM-DD HH:MM' or 'HH:MM' (UTC).",
                        ephemeral=True,
                    )
                    return
                updates["event_time_utc"] = new_time
                summary.append(f"- Time -> {new_time.strftime('%Y-%m-%d %H:%M UTC')}")
            
            if description is not None:
                updates["description"] = description
                summary.append("- Description updated")
            
            if remind_minutes:
                reminder_times = self._parse_reminder_times(remind_minutes)
                updates["reminder_times"] = reminder_times
                summary.append(f"- Reminders -> {', '.join(map(str, reminder_times))} min")
            
            if category:
                try:
                    category_enum = EventCategory(category)
                except ValueError:
                    await interaction.response.send_message("Invalid category value.", ephemeral=True)
                    return
                updates["category"] = category_enum
                summary.append(f"- Category -> {category_enum.value.replace('_', ' ').title()}")
            else:
                category_enum = event.category
            
            recurrence_enum: Optional[RecurrenceType] = None
            if recurrence:
                try:
                    recurrence_enum = RecurrenceType(recurrence)
                except ValueError:
                    await interaction.response.send_message("Invalid recurrence value.", ephemeral=True)
                    return
                updates["recurrence"] = recurrence_enum
                summary.append(f"- Recurrence -> {recurrence_enum.value.replace('_', ' ').title()}")
            target_recurrence = recurrence_enum or event.recurrence
            
            if custom_interval_days is not None:
                if target_recurrence != RecurrenceType.CUSTOM_INTERVAL:
                    await interaction.response.send_message(
                        "Custom interval days can only be set when recurrence is 'Every 2-6 days'.",
                        ephemeral=True,
                    )
                    return
                updates["custom_interval_hours"] = custom_interval_days * 24
                summary.append(f"- Interval -> every {custom_interval_days} day(s)")
            
            if active is not None:
                updates["is_active"] = 1 if active else 0
                summary.append(f"- Active -> {'Yes' if active else 'No'}")
            
            if not updates:
                await interaction.response.send_message(
                    "Provide at least one field to update.",
                    ephemeral=True,
                )
                return
            
            success = await self.event_engine.update_event(event.event_id, **updates)
            if not success:
                await interaction.response.send_message("Failed to update event. Please try again.", ephemeral=True)
                return
            
            embed = discord.Embed(
                title="✨ Event updated",
                description=self._format_event_label(event),
                color=discord.Color.orange(),
            )
            if summary:
                embed.add_field(name="Changes", value="\n".join(summary), inline=False)
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as exc:
            await self._log_error(exc, context="event.edit")
            if interaction.response.is_done():
                await interaction.followup.send("An error occurred while editing the event.", ephemeral=True)
            else:
                await interaction.response.send_message("An error occurred while editing the event.", ephemeral=True)

    @app_commands.command(
        name="test_kvk_status",
        description="🧪 Show any active Test KVK cycles (Admin)"
    )
    async def test_kvk_status(self, interaction: discord.Interaction) -> None:
        """Report whether a Test KVK window is currently scheduled."""
        if not interaction.guild:
            await self._safe_send_response(interaction, content="This command must be used in a server.", ephemeral=True)
            return

        if not self._has_permission(interaction):
            await self._deny_permission(interaction)
            return

        if not self.event_engine:
            await self._safe_send_response(interaction, content="Event system not available.", ephemeral=True)
            return

        active_tests = await self.event_engine.get_active_test_kvk_events(interaction.guild.id)
        if not active_tests:
            await self._safe_send_response(
                interaction,
                content="No active Test KVK cycles are currently scheduled.",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title="🧪 Active Test KVK Cycles",
            color=discord.Color.purple(),
            description="The following test KVK windows are still scheduled."
        )

        now = datetime.now(timezone.utc)
        for event in active_tests:
            next_occurrence = event.get_next_occurrence(now)
            next_label = next_occurrence.strftime("%Y-%m-%d %H:%M UTC") if next_occurrence else "N/A"
            event_time = event.event_time_utc.strftime("%Y-%m-%d %H:%M UTC")
            channel_info = f"<#{event.channel_id}>" if event.channel_id else "Not specified"
            embed.add_field(
                name=event.title,
                value=(
                    f"Start: {event_time}\n"
                    f"Next reminder: {next_label}\n"
                    f"Channel: {channel_info}\n"
                    f"Recurrence: {event.recurrence.value.title()}"
                ),
                inline=False
            )

        await self._safe_send_response(interaction, embed=embed, ephemeral=True)
    
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
