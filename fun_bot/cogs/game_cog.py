from __future__ import annotations

import random
from typing import Sequence

import discord
from discord import app_commands
from discord.ext import commands

from fun_bot.core.channel_utils import ensure_bot_channel
from fun_bot.core.cookie_manager import CookieManager
from fun_bot.core.personality_engine import PersonalityEngine
from fun_bot.core.personality_memory import PersonalityMemory
from fun_bot.games.pokemon_data_manager import PokemonDataManager, PokemonRecord


POKEMON_NAMES: Sequence[str] = (
    "Bulbasaur",
    "Charmander",
    "Squirtle",
    "Pikachu",
    "Eevee",
    "Jigglypuff",
    "Snorlax",
    "Gengar",
    "Dragonite",
    "Mewtwo",
)

RARE_POKEMON_NAMES: Sequence[str] = (
    "Snorlax",
    "Gengar",
    "Dragonite",
    "Mewtwo",
)

FISH_POKEMON_NAMES: Sequence[str] = (
    "Squirtle",
    "Wartortle",
    "Blastoise",
    "Vaporeon",
)


class GameCog(commands.Cog):
    """Core game commands for FunBot.

    Provides simple Pokémon collection commands and a cookie balance
    viewer, all backed by the shared persistent storage engine.
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        storage = getattr(bot, "game_storage", None)
        if storage is None:
            raise RuntimeError("GameCog requires bot.game_storage to be initialised")

        self.cookies = CookieManager(storage)
        self.pokemon_data = PokemonDataManager(storage)
        self.config = getattr(bot, "config", None)
        self.personality: PersonalityEngine = getattr(bot, "personality", PersonalityEngine())
        self.personality_memory: PersonalityMemory | None = getattr(bot, "personality_memory", None)

        # Slash command group for Pokémon features.
        self.pokemon_group = app_commands.Group(
            name="pokemon",
            description="Pokémon mini-game commands",
        )

        class TradeConfirmView(discord.ui.View):
            """Confirmation view for Pokémon trades."""

            def __init__(self, initiator_id: int, *, timeout: float | None = 60) -> None:
                super().__init__(timeout=timeout)
                self.initiator_id = initiator_id
                self.confirmed: bool | None = None

            @discord.ui.button(label="Confirm trade", style=discord.ButtonStyle.green)
            async def confirm(
                self,
                button_interaction: discord.Interaction,
                button: discord.ui.Button,  # type: ignore[type-arg]
            ) -> None:
                if button_interaction.user.id != self.initiator_id:
                    await button_interaction.response.send_message(
                        "Only the trade initiator can confirm this trade.",
                        ephemeral=True,
                    )
                    return
                self.confirmed = True
                await button_interaction.response.defer()
                self.stop()

            @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
            async def cancel(
                self,
                button_interaction: discord.Interaction,
                button: discord.ui.Button,  # type: ignore[type-arg]
            ) -> None:
                if button_interaction.user.id != self.initiator_id:
                    await button_interaction.response.send_message(
                        "Only the trade initiator can cancel this trade.",
                        ephemeral=True,
                    )
                    return
                self.confirmed = False
                await button_interaction.response.defer()
                self.stop()

        class TradeOfferSelect(discord.ui.Select):
            """Dropdown for the target user to choose a Pokémon to offer."""

            def __init__(self, target_id: int, options_data: Sequence[PokemonRecord]) -> None:
                records = list(options_data)
                options: list[discord.SelectOption]
                if records:
                    options = [
                        discord.SelectOption(
                            label=f"{p.species} (L{p.level})",
                            description=f"ID {p.pokemon_id} · IVs {p.iv_percentage():.1f}%",
                            value=str(p.pokemon_id),
                        )
                        for p in records[:25]
                    ]
                else:
                    options = [
                        discord.SelectOption(
                            label="No available Pokémon",
                            description="You have no Pokémon to trade.",
                            value="none",
                        )
                    ]

                super().__init__(
                    placeholder="Choose one of your Pokémon to offer",
                    min_values=1,
                    max_values=1,
                    options=options,
                )
                self.target_id = target_id

            async def callback(self, interaction: discord.Interaction) -> None:  # type: ignore[override]
                if interaction.user.id != self.target_id:
                    await interaction.response.send_message(
                        "Only the requested user can select a Pokémon for this trade.",
                        ephemeral=True,
                    )
                    return

                view = self.view
                if isinstance(view, TradeOfferView):
                    if not self.options or self.values[0] == "none":
                        await interaction.response.send_message(
                            "You have no Pokémon available to trade.",
                            ephemeral=True,
                        )
                        view.selected_pokemon_id = None
                        view.stop()
                        return

                    view.selected_pokemon_id = int(self.values[0])

                await interaction.response.defer()
                if isinstance(view, TradeOfferView):
                    view.stop()

        class TradeOfferView(discord.ui.View):
            """View wrapping the offer select for the target user."""

            def __init__(
                self,
                target_id: int,
                options_data: Sequence[PokemonRecord],
                *,
                timeout: float | None = 60,
            ) -> None:
                super().__init__(timeout=timeout)
                self.target_id = target_id
                self.selected_pokemon_id: int | None = None
                self.add_item(TradeOfferSelect(target_id, options_data))

        @self.pokemon_group.command(name="catch", description="Catch a random Pokémon")
        async def catch(interaction: discord.Interaction) -> None:  # type: ignore[unused-ignore]
            if not await ensure_bot_channel(interaction, getattr(self.config, "bot_channel_ids", set())):
                return

            balance = await self.cookies.get_balance(interaction.user.id)
            if balance.amount < 1:
                await interaction.response.send_message(
                    "Catching a Pokémon costs **1 cookie**, but you don't have enough.\n"
                    "Play easter egg games like `/rps`, `/trivia`, `/weather`, or `/magic8` "
                    "to earn more cookies first.",
                    ephemeral=True,
                )
                return

            await self.cookies.add_cookies(interaction.user.id, -1)

            name = random.choice(list(POKEMON_NAMES))
            # Create a full Pokémon record with randomised stats, then
            # update the legacy profile counters so existing stats keep
            # working.
            record = await self.pokemon_data.create_caught_pokemon(
                interaction.user.id,
                name,
            )
            stats = await self.pokemon_data.record_catch(interaction.user.id, record.species)
            total = stats.caught

            text = self.personality.format("pokemon_catch", name=record.species, total=total)

            iv_pct = record.iv_percentage()
            quality = record.iv_quality_label()
            extra = f"\nID: `{record.pokemon_id}` · Level: {record.level} · IVs: {iv_pct:.1f}% ({quality})"

            memory_note = ""
            if self.personality_memory is not None:
                recent_rare = await self.personality_memory.get_last_event_with_tags(
                    interaction.user.id,
                    ["rare_catch"],
                )
                if recent_rare:
                    memory_note = f"\n(Last rare moment: {recent_rare.summary})"

            await interaction.response.send_message(text + extra + memory_note, ephemeral=False)
            if self.personality_memory is not None:
                await self.personality_memory.add_event(
                    interaction.user.id,
                    summary=f"Caught {record.species} (L{record.level}, {iv_pct:.1f}% IVs, {quality})",
                    tags=["pokemon_catch"],
                )

        @self.pokemon_group.command(
            name="explore",
            description="Explore for a chance to find rare Pokémon (costs 3 cookies)",
        )
        async def explore_cmd(interaction: discord.Interaction) -> None:  # type: ignore[unused-ignore]
            if not await ensure_bot_channel(interaction, getattr(self.config, "bot_channel_ids", set())):
                return

            balance = await self.cookies.get_balance(interaction.user.id)
            if balance.amount < 3:
                await interaction.response.send_message(
                    "Exploring for rare Pokémon costs **3 cookies**, but you don't have enough.\n"
                    "Play easter egg games like `/rps`, `/trivia`, `/weather`, or `/magic8` "
                    "to earn more cookies first.",
                    ephemeral=True,
                )
                return

            await self.cookies.add_cookies(interaction.user.id, -3)

            # Weighted pool: mostly common starters, with a boosted chance
            # to hit the rare set.
            common_pool = list(POKEMON_NAMES) * 2
            rare_pool = list(RARE_POKEMON_NAMES) * 4
            name = random.choice(common_pool + rare_pool)

            record = await self.pokemon_data.create_caught_pokemon(
                interaction.user.id,
                name,
            )
            stats = await self.pokemon_data.record_catch(interaction.user.id, record.species)
            total = stats.caught

            text = self.personality.format("pokemon_catch", name=record.species, total=total)
            iv_pct = record.iv_percentage()
            quality = record.iv_quality_label()
            extra = (
                f"\n(Exploration catch – 3 cookies spent)"
                f"\nID: `{record.pokemon_id}` · Level: {record.level} · IVs: {iv_pct:.1f}% ({quality})"
            )
            memory_note = ""
            if self.personality_memory is not None:
                recent_battle = await self.personality_memory.get_last_event_with_tags(
                    interaction.user.id,
                    ["battle_win"],
                )
                if recent_battle:
                    memory_note = f"\n(Still thinking about: {recent_battle.summary})"
            await interaction.response.send_message(text + extra + memory_note, ephemeral=False)
            if self.personality_memory is not None:
                tags = ["pokemon_explore"]
                if record.species in RARE_POKEMON_NAMES:
                    tags.append("rare_catch")
                await self.personality_memory.add_event(
                    interaction.user.id,
                    summary=(
                        f"Explored and caught {record.species} "
                        f"(L{record.level}, {iv_pct:.1f}% IVs, {quality})"
                    ),
                    tags=tags,
                )

        @self.pokemon_group.command(
            name="fish",
            description="Go fishing for a water-type Pokémon (costs 1 cookie)",
        )
        async def fish_cmd(interaction: discord.Interaction) -> None:  # type: ignore[unused-ignore]
            if not await ensure_bot_channel(interaction, getattr(self.config, "bot_channel_ids", set())):
                return

            balance = await self.cookies.get_balance(interaction.user.id)
            if balance.amount < 1:
                await interaction.response.send_message(
                    "Fishing for Pokémon costs **1 cookie**, but you don't have enough.\n"
                    "Play easter egg games like `/rps`, `/trivia`, `/weather`, or `/magic8` "
                    "to earn more cookies first.",
                    ephemeral=True,
                )
                return

            await self.cookies.add_cookies(interaction.user.id, -1)

            name = random.choice(list(FISH_POKEMON_NAMES))
            record = await self.pokemon_data.create_caught_pokemon(
                interaction.user.id,
                name,
            )
            stats = await self.pokemon_data.record_catch(interaction.user.id, record.species)
            total = stats.caught

            text = self.personality.format("pokemon_catch", name=record.species, total=total)
            iv_pct = record.iv_percentage()
            quality = record.iv_quality_label()
            extra = (
                f"\n(Fishing catch – 1 cookie spent)"
                f"\nID: `{record.pokemon_id}` · Level: {record.level} · IVs: {iv_pct:.1f}% ({quality})"
            )
            memory_note = ""
            if self.personality_memory is not None:
                recent_fish = await self.personality_memory.get_last_event_with_tags(
                    interaction.user.id,
                    ["pokemon_fish"],
                )
                if recent_fish:
                    memory_note = f"\n(Last fishing highlight: {recent_fish.summary})"
            await interaction.response.send_message(text + extra + memory_note, ephemeral=False)
            if self.personality_memory is not None:
                await self.personality_memory.add_event(
                    interaction.user.id,
                    summary=(
                        f"Fished up {record.species} "
                        f"(L{record.level}, {iv_pct:.1f}% IVs, {quality})"
                    ),
                    tags=["pokemon_fish"],
                )

        @self.pokemon_group.command(
            name="trade",
            description="Trade Pokémon with another user",
        )
        @app_commands.describe(
            target="User you want to trade with",
            my_pokemon_id="ID of the Pokémon you are offering",
        )
        async def trade_cmd(
            interaction: discord.Interaction,
            target: discord.User,
            my_pokemon_id: int,
        ) -> None:  # type: ignore[unused-ignore]
            if not await ensure_bot_channel(interaction, getattr(self.config, "bot_channel_ids", set())):
                return

            if target.id == interaction.user.id:
                await interaction.response.send_message(
                    "You cannot trade Pokémon with yourself.",
                    ephemeral=True,
                )
                return

            my_pokemon = await self.pokemon_data.get_pokemon(interaction.user.id, my_pokemon_id)
            if my_pokemon is None:
                await interaction.response.send_message(
                    "I couldn't find your Pokémon with that ID. "
                    "Use `/pokemon collection` to see valid IDs.",
                    ephemeral=True,
                )
                return
            target_records = await self.pokemon_data.list_pokemon(target.id)
            if not target_records:
                await interaction.response.send_message(
                    f"{target.mention} doesn't have any Pokémon available to trade.",
                    ephemeral=True,
                )
                return

            request_embed = discord.Embed(
                title="Pokémon Trade Request",
                description=(
                    f"{interaction.user.mention} wants to trade Pokémon with {target.mention}.\n\n"
                    "Select one of your Pokémon from the menu below to offer in return."
                ),
                color=discord.Color.blurple(),
            )
            request_embed.add_field(
                name="Initiator's Pokémon",
                value=(
                    f"ID: `{my_pokemon.pokemon_id}`\n"
                    f"Species: **{my_pokemon.species}**\n"
                    f"Level: **{my_pokemon.level}**\n"
                    f"IVs: {my_pokemon.iv_percentage():.1f}%"
                ),
                inline=False,
            )

            offer_view = TradeOfferView(target.id, target_records)
            await interaction.response.send_message(
                content=f"{target.mention}, choose a Pokémon to offer for this trade:",
                embed=request_embed,
                view=offer_view,
            )

            await offer_view.wait()

            if offer_view.selected_pokemon_id is None:
                await interaction.followup.send(
                    "Trade request expired or no Pokémon was selected. No Pokémon were exchanged.",
                    ephemeral=True,
                )
                return

            their_pokemon = await self.pokemon_data.get_pokemon(target.id, offer_view.selected_pokemon_id)
            if their_pokemon is None:
                await interaction.followup.send(
                    f"The selected Pokémon is no longer available for {target.mention}. Trade cancelled.",
                    ephemeral=True,
                )
                return

            confirm_embed = discord.Embed(
                title="Confirm Pokémon Trade",
                description=(
                    f"{interaction.user.mention}, review this trade with {target.mention} "
                    "and confirm or cancel."
                ),
                color=discord.Color.green(),
            )
            confirm_embed.add_field(
                name="You will give",
                value=(
                    f"ID: `{my_pokemon.pokemon_id}`\n"
                    f"Species: **{my_pokemon.species}**\n"
                    f"Level: **{my_pokemon.level}**\n"
                    f"IVs: {my_pokemon.iv_percentage():.1f}%"
                ),
                inline=True,
            )
            confirm_embed.add_field(
                name="You will receive",
                value=(
                    f"ID: `{their_pokemon.pokemon_id}`\n"
                    f"Species: **{their_pokemon.species}**\n"
                    f"Level: **{their_pokemon.level}**\n"
                    f"IVs: {their_pokemon.iv_percentage():.1f}%"
                ),
                inline=True,
            )

            confirm_view = TradeConfirmView(interaction.user.id)
            await interaction.followup.send(
                content=f"{interaction.user.mention}, confirm this trade:",
                embed=confirm_embed,
                view=confirm_view,
            )

            await confirm_view.wait()

            if confirm_view.confirmed is None:
                await interaction.followup.send(
                    "Trade confirmation timed out. No Pokémon were exchanged.",
                    ephemeral=True,
                )
                return
            if not confirm_view.confirmed:
                await interaction.followup.send(
                    "Trade cancelled. No Pokémon were exchanged.",
                    ephemeral=True,
                )
                return

            # Final ownership validation before swapping.
            my_latest = await self.pokemon_data.get_pokemon(interaction.user.id, my_pokemon_id)
            their_latest = await self.pokemon_data.get_pokemon(target.id, their_pokemon.pokemon_id)
            if my_latest is None or their_latest is None:
                await interaction.followup.send(
                    "Trade failed because one of the Pokémon is no longer available.",
                    ephemeral=True,
                )
                return

            await self.pokemon_data.update_pokemon_owner(my_latest.pokemon_id, target.id)
            await self.pokemon_data.update_pokemon_owner(their_latest.pokemon_id, interaction.user.id)

            await interaction.followup.send(
                f"✅ Trade complete! {interaction.user.mention} and {target.mention} swapped:\n"
                f"- `{my_latest.pokemon_id}` {my_latest.species} ↔ "
                f"`{their_latest.pokemon_id}` {their_latest.species}.",
                ephemeral=False,
            )

        @self.pokemon_group.command(name="stats", description="View your Pokémon stats")
        async def stats_cmd(interaction: discord.Interaction) -> None:  # type: ignore[unused-ignore]
            if not await ensure_bot_channel(interaction, getattr(self.config, "bot_channel_ids", set())):
                return

            stats = await self.pokemon_data.get_stats(interaction.user.id)
            names = stats.caught_names or []
            names_display = ", ".join(names) if names else "(none yet)"

            header = self.personality.format(
                "pokemon_stats_header",
                user_name=interaction.user.display_name,
            )
            embed = discord.Embed(title=f"{interaction.user.display_name}'s Pokémon Stats")
            embed.description = header
            embed.add_field(name="Caught", value=str(stats.caught), inline=True)
            embed.add_field(name="Battles", value=str(stats.battles), inline=True)
            embed.add_field(name="Wins", value=str(stats.wins), inline=True)
            embed.add_field(name="Losses", value=str(stats.losses), inline=True)
            embed.add_field(name="Collection", value=names_display, inline=False)

            await interaction.response.send_message(embed=embed)

        @self.pokemon_group.command(name="collection", description="View your detailed Pokémon collection")
        async def collection_cmd(interaction: discord.Interaction) -> None:  # type: ignore[unused-ignore]
            if not await ensure_bot_channel(interaction, getattr(self.config, "bot_channel_ids", set())):
                return

            records = await self.pokemon_data.list_pokemon(interaction.user.id)
            if not records:
                await interaction.response.send_message(
                    "You haven't caught any Pokémon yet. Use `/pokemon catch` to get started!",
                    ephemeral=True,
                )
                return

            # Keep the embed compact; show top N and summarise the rest.
            max_display = 10
            shown: list[PokemonRecord] = records[:max_display]
            extra_count = max(0, len(records) - len(shown))

            embed = discord.Embed(
                title=f"{interaction.user.display_name}'s Pokémon Collection",
            )

            lines = []
            for rec in shown:
                iv_pct = rec.iv_percentage()
                quality = rec.iv_quality_label()
                line = (
                    f"`#{rec.pokemon_id}` {rec.species} · L{rec.level} · "
                    f"IVs {iv_pct:.1f}% ({quality}) · Nature: {rec.nature}"
                )
                lines.append(line)

            description = "\n".join(lines)
            if extra_count > 0:
                description += f"\n…and {extra_count} more. (Oldest first.)"

            embed.description = description
            await interaction.response.send_message(embed=embed, ephemeral=True)

        @self.pokemon_group.command(name="train", description="Train a Pokémon to gain experience")
        @app_commands.describe(
            pokemon_id="ID of the Pokémon you want to train",
        )
        async def train_cmd(
            interaction: discord.Interaction,
            pokemon_id: int,
        ) -> None:  # type: ignore[unused-ignore]
            if not await ensure_bot_channel(interaction, getattr(self.config, "bot_channel_ids", set())):
                return

            result = await self.pokemon_data.train_pokemon(
                interaction.user.id,
                pokemon_id,
                xp_gain=100,
            )
            if result is None:
                await interaction.response.send_message(
                    "I couldn't find that Pokémon in your collection.",
                    ephemeral=True,
                )
                return

            updated, old_level, new_level = result
            if old_level == new_level and new_level >= 100:
                await interaction.response.send_message(
                    f"{updated.species} is already at the maximum level (100). Further training has no effect.",
                    ephemeral=True,
                )
                return

            if old_level == new_level:
                await interaction.response.send_message(
                    f"{updated.species} trained and gained experience. It remains at level {new_level} for now.",
                    ephemeral=True,
                )
                return

            await interaction.response.send_message(
                f"{updated.species} trained hard and grew from level {old_level} to level {new_level}!",
                ephemeral=True,
            )

        @self.pokemon_group.command(
            name="evolve",
            description="Evolve a Pokémon using a duplicate and cookies",
        )
        @app_commands.describe(
            pokemon_id="The Pokémon you want to evolve",
            duplicate_id="A duplicate of the same species to consume",
        )
        async def evolve_cmd(
            interaction: discord.Interaction,
            pokemon_id: int,
            duplicate_id: int,
        ) -> None:  # type: ignore[unused-ignore]
            if not await ensure_bot_channel(interaction, getattr(self.config, "bot_channel_ids", set())):
                return

            if pokemon_id == duplicate_id:
                await interaction.response.send_message(
                    "You need a separate duplicate Pokémon to evolve with.",
                    ephemeral=True,
                )
                return

            main = await self.pokemon_data.get_pokemon(interaction.user.id, pokemon_id)
            dup = await self.pokemon_data.get_pokemon(interaction.user.id, duplicate_id)
            if main is None or dup is None:
                await interaction.response.send_message(
                    "I couldn't find one or both of those Pokémon in your collection.",
                    ephemeral=True,
                )
                return

            if main.species.lower() != dup.species.lower():
                await interaction.response.send_message(
                    "Both Pokémon must be the same species to evolve.",
                    ephemeral=True,
                )
                return

            evo_info = self.pokemon_data.get_evolution_info(main.species)
            if evo_info is None:
                await interaction.response.send_message(
                    f"{main.species} cannot evolve (no evolution data configured).",
                    ephemeral=True,
                )
                return

            evolved_species, min_level, cookie_cost, _stage = evo_info
            if main.level < min_level:
                await interaction.response.send_message(
                    f"{main.species} needs to reach at least level {min_level} to evolve "
                    f"(currently level {main.level}).",
                    ephemeral=True,
                )
                return

            balance = await self.cookies.get_balance(interaction.user.id)
            if balance.amount < cookie_cost:
                await interaction.response.send_message(
                    f"Not enough cookies to evolve {main.species}. "
                    f"You need {cookie_cost} cookies but only have {balance.amount}.",
                    ephemeral=True,
                )
                return

            await self.cookies.add_cookies(interaction.user.id, -cookie_cost)

            evolved = await self.pokemon_data.evolve_pokemon(
                interaction.user.id,
                pokemon_id,
                duplicate_id,
                evolved_species=evolved_species,
            )
            if evolved is None:
                await interaction.response.send_message(
                    "Evolution failed due to an internal error. Please try again.",
                    ephemeral=True,
                )
                return

            await interaction.response.send_message(
                f"✨ Evolution success! Your {main.species} (ID #{pokemon_id}) evolved into "
                f"{evolved.species} at level {evolved.level}. "
                f"{cookie_cost} cookies were consumed, along with the duplicate Pokémon (ID #{duplicate_id}).",
                ephemeral=False,
            )

        @self.pokemon_group.command(
            name="bot_battle",
            description="Battle FunBot with one of your Pokémon (2 times per day)",
        )
        @app_commands.describe(
            pokemon_id="ID of the Pokémon you want to send into battle",
        )
        async def bot_battle_cmd(
            interaction: discord.Interaction,
            pokemon_id: int,
        ) -> None:  # type: ignore[unused-ignore]
            if not await ensure_bot_channel(interaction, getattr(self.config, "bot_channel_ids", set())):
                return

            today, count = await self.pokemon_data.get_daily_bot_battles(interaction.user.id)
            if count >= 2:
                await interaction.response.send_message(
                    f"You have already battled FunBot twice today ({today}). "
                    "Try again tomorrow for more training.",
                    ephemeral=True,
                )
                return

            pokemon = await self.pokemon_data.get_pokemon(interaction.user.id, pokemon_id)
            if pokemon is None:
                await interaction.response.send_message(
                    "I couldn't find that Pokémon in your collection. "
                    "Use `/pokemon collection` to see valid IDs.",
                    ephemeral=True,
                )
                return

            # Choose a common opponent species for the bot.
            bot_species = random.choice(list(POKEMON_NAMES))

            # Simple outcome model: higher level slightly increases win odds.
            base_win_chance = 0.55
            level_bonus = (pokemon.level - 10) * 0.01
            win_chance = max(0.3, min(0.85, base_win_chance + level_bonus))

            from random import random as _rand

            did_win = _rand() < win_chance

            # XP rewards: more on win, a little on loss.
            xp_gain = 150 if did_win else 50
            updated, old_level, new_level = await self.pokemon_data.train_pokemon(
                interaction.user.id,
                pokemon_id,
                xp_gain=xp_gain,
            ) or (pokemon, pokemon.level, pokemon.level)

            # Small chance to earn a free stat point on win.
            stat_point_awarded = False
            if did_win and _rand() < 0.15:
                after = await self.pokemon_data.add_free_stat_points(
                    interaction.user.id,
                    pokemon_id,
                    amount=1,
                )
                stat_point_awarded = after is not None

            _, new_count = await self.pokemon_data.increment_daily_bot_battles(interaction.user.id)

            result_lines = []
            result_lines.append(
                f"⚔️ {interaction.user.display_name}'s {pokemon.species} (L{pokemon.level}) "
                f"battled FunBot's {bot_species}."
            )
            if did_win:
                result_lines.append("You won the battle against FunBot!")
            else:
                result_lines.append("FunBot won this round, but your Pokémon learned from the fight.")

            if old_level != new_level:
                result_lines.append(
                    f"{pokemon.species} grew from level {old_level} to level {new_level} and gained {xp_gain} XP."
                )
            else:
                result_lines.append(
                    f"{pokemon.species} gained {xp_gain} XP and remains at level {new_level}."
                )

            if stat_point_awarded:
                result_lines.append(
                    "Your Pokémon earned 1 free stat point! "
                    "Use `/pokemon boost_stat` to apply it."
                )

            remaining = max(0, 2 - new_count)
            result_lines.append(f"Daily FunBot battles used: {new_count}/2. Remaining today: {remaining}.")

            await interaction.response.send_message("\n".join(result_lines), ephemeral=False)
            if self.personality_memory is not None:
                tags = ["bot_battle_win" if did_win else "bot_battle_loss"]
                if stat_point_awarded:
                    tags.append("stat_boost")
                await self.personality_memory.add_event(
                    interaction.user.id,
                    summary=(
                        f"Bot battle vs FunBot using {pokemon.species} "
                        f"(result: {'win' if did_win else 'loss'}, XP+{xp_gain})"
                    ),
                    tags=tags,
                )

        @self.pokemon_group.command(
            name="boost_stat",
            description="Spend a free stat point to boost one stat of a Pokémon",
        )
        @app_commands.describe(
            pokemon_id="ID of the Pokémon to boost",
            stat="Which stat to boost by 1 point",
        )
        @app_commands.choices(
            stat=[
                app_commands.Choice(name="HP", value="hp"),
                app_commands.Choice(name="Attack", value="attack"),
                app_commands.Choice(name="Defense", value="defense"),
                app_commands.Choice(name="Special Attack", value="special_attack"),
                app_commands.Choice(name="Special Defense", value="special_defense"),
                app_commands.Choice(name="Speed", value="speed"),
            ]
        )
        async def boost_stat_cmd(
            interaction: discord.Interaction,
            pokemon_id: int,
            stat: app_commands.Choice[str],
        ) -> None:  # type: ignore[unused-ignore]
            if not await ensure_bot_channel(interaction, getattr(self.config, "bot_channel_ids", set())):
                return

            pokemon = await self.pokemon_data.get_pokemon(interaction.user.id, pokemon_id)
            if pokemon is None:
                await interaction.response.send_message(
                    "I couldn't find that Pokémon in your collection.",
                    ephemeral=True,
                )
                return

            if pokemon.free_stat_points <= 0:
                await interaction.response.send_message(
                    f"{pokemon.species} has no free stat points available. "
                    "Battle FunBot with `/pokemon bot_battle` for a chance to earn more.",
                    ephemeral=True,
                )
                return

            updated = await self.pokemon_data.boost_stat_with_point(
                interaction.user.id,
                pokemon_id,
                stat_name=stat.value,
            )
            if updated is None:
                await interaction.response.send_message(
                    "Boost failed. Please try again or pick a different stat.",
                    ephemeral=True,
                )
                return

            await interaction.response.send_message(
                f"✅ Spent 1 free stat point on {updated.species}'s **{stat.name}**.\n"
                f"Remaining free stat points: {updated.free_stat_points}.",
                ephemeral=True,
            )
            if self.personality_memory is not None:
                await self.personality_memory.add_event(
                    interaction.user.id,
                    summary=(
                        f"Boosted {updated.species}'s {stat.name} "
                        f"(free points left: {updated.free_stat_points})"
                    ),
                    tags=["stat_boost"],
                )

        # Slash command group for cookie utilities.
        self.cookies_group = app_commands.Group(
            name="cookies",
            description="Check your helper cookie balance",
        )

        @self.cookies_group.command(name="balance", description="Show your cookie balance")
        async def cookies_balance(interaction: discord.Interaction) -> None:  # type: ignore[unused-ignore]
            if not await ensure_bot_channel(interaction, getattr(self.config, "bot_channel_ids", set())):
                return

            balance = await self.cookies.get_balance(interaction.user.id)
            text = self.personality.format("cookies_balance", amount=balance.amount)
            await interaction.response.send_message(text, ephemeral=True)

        @self.cookies_group.command(name="give", description="Give helper cookies to a user")
        @app_commands.describe(
            member="User to receive cookies",
            amount="Number of cookies to grant",
        )
        async def cookies_give(
            interaction: discord.Interaction,
            member: discord.Member,
            amount: int,
        ) -> None:  # type: ignore[unused-ignore]
            if not await ensure_bot_channel(interaction, getattr(self.config, "bot_channel_ids", set())):
                return

            # Owner or server admins can give cookies.
            owner_ids = getattr(self.config, "owner_ids", set()) if self.config else set()
            is_owner = interaction.user.id in owner_ids
            is_admin = isinstance(interaction.user, discord.Member) and interaction.user.guild_permissions.administrator

            if not (is_owner or is_admin):
                await interaction.response.send_message(
                    self.personality.format("cookies_no_permission"),
                    ephemeral=True,
                )
                return

            if amount <= 0:
                await interaction.response.send_message(
                    self.personality.format("cookies_invalid_amount"),
                    ephemeral=True,
                )
                return

            new_balance = await self.cookies.add_cookies(member.id, amount)
            text = self.personality.format(
                "cookies_give_success",
                amount=amount,
                target=member.mention,
                new_amount=new_balance.amount,
            )
            await interaction.response.send_message(
                text,
                allowed_mentions=discord.AllowedMentions.none(),
            )

        self.bot.tree.add_command(self.pokemon_group)
        self.bot.tree.add_command(self.cookies_group)


async def setup_game_cog(bot: commands.Bot) -> None:
    await bot.add_cog(GameCog(bot))


__all__ = ["GameCog", "setup_game_cog"]
