from __future__ import annotations

from typing import Dict

import discord
from discord import app_commands
from discord.ext import commands

from fun_bot.core.channel_utils import ensure_bot_channel
from fun_bot.core.personality_engine import PersonalityEngine
from fun_bot.core.personality_memory import PersonalityMemory
from fun_bot.games.battle_system import (
    BattleState,
    create_battle,
    list_moves,
    perform_move,
    forfeit,
)
from fun_bot.games.pokemon_data_manager import PokemonDataManager


class BattleCog(commands.Cog):
    """Turn-based battle commands for FunBot.

    Battles are 1v1, tracked per channel, and use a small set of
    predefined moves. Results update the Pokémon stats profile so wins
    and battles are persisted.
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.personality: PersonalityEngine = getattr(bot, "personality", PersonalityEngine())
        self.config = getattr(bot, "config", None)
        storage = getattr(bot, "game_storage", None)
        if storage is None:
            raise RuntimeError("BattleCog requires bot.game_storage to be initialised")
        self.pokemon_data = PokemonDataManager(storage)
        self.personality_memory: PersonalityMemory | None = getattr(bot, "personality_memory", None)

        # Active battles keyed by channel ID (one battle per channel).
        self._battles: Dict[int, BattleState] = {}

        self.battle_group = app_commands.Group(
            name="battle",
            description="Turn-based battles between members",
        )

        @self.battle_group.command(name="challenge", description="Challenge another user to a battle")
        @app_commands.describe(opponent="User you want to battle")
        async def challenge(
            interaction: discord.Interaction,
            opponent: discord.Member,
        ) -> None:  # type: ignore[unused-ignore]
            if not await ensure_bot_channel(interaction, getattr(self.config, "bot_channel_ids", set())):
                return

            channel_id = interaction.channel.id if interaction.channel else 0
            if channel_id in self._battles:
                await interaction.response.send_message(
                    "There is already an active battle in this channel.",
                    ephemeral=False,
                )
                return

            if opponent.id == interaction.user.id:
                await interaction.response.send_message(
                    "You can't battle yourself.", ephemeral=False
                )
                return

            # Prevent a user from being in multiple battles across channels.
            for existing in self._battles.values():
                if interaction.user.id in (existing.p1.user_id, existing.p2.user_id) or opponent.id in (
                    existing.p1.user_id,
                    existing.p2.user_id,
                ):
                    await interaction.response.send_message(
                        "One of you is already in another battle.",
                        ephemeral=False,
                    )
                    return

            state = create_battle(
                channel_id=channel_id,
                p1_id=interaction.user.id,
                p1_name=interaction.user.display_name,
                p2_id=opponent.id,
                p2_name=opponent.display_name,
            )
            self._battles[channel_id] = state

            first_turn = (
                interaction.user.display_name
                if state.current_turn == interaction.user.id
                else opponent.display_name
            )
            text = self.personality.format(
                "battle_start",
                p1=state.p1.display_name,
                p2=state.p2.display_name,
                first_turn=first_turn,
            )
            status = f"{state.p1.display_name}: {state.p1.hp} HP | {state.p2.display_name}: {state.p2.hp} HP"

            memory_note = ""
            if self.personality_memory is not None:
                recent = await self.personality_memory.get_last_event_with_tags(
                    interaction.user.id,
                    ["pvp_battle"],
                )
                if recent:
                    memory_note = f"\n(Last battle memory: {recent.summary})"

            await interaction.response.send_message(f"{text}\n{status}{memory_note}")

        @self.battle_group.command(name="moves", description="List available battle moves")
        async def moves(interaction: discord.Interaction) -> None:  # type: ignore[unused-ignore]
            if not await ensure_bot_channel(interaction, getattr(self.config, "bot_channel_ids", set())):
                return

            items = [f"**{mv.name}** – {mv.description}" for mv in list_moves()]
            moves_str = "\n".join(items)
            text = self.personality.format("battle_moves_list", moves=moves_str)
            await interaction.response.send_message(text, ephemeral=False)

        @self.battle_group.command(name="move", description="Use a move in your current battle")
        @app_commands.describe(move_name="Name of the move to use")
        async def move_cmd(interaction: discord.Interaction, move_name: str) -> None:  # type: ignore[unused-ignore]
            if not await ensure_bot_channel(interaction, getattr(self.config, "bot_channel_ids", set())):
                return

            channel_id = interaction.channel.id if interaction.channel else 0
            state = self._battles.get(channel_id)
            if state is None or interaction.user.id not in (
                state.p1.user_id,
                state.p2.user_id,
            ):
                await interaction.response.send_message(
                    self.personality.format("battle_not_in_battle"),
                    ephemeral=False,
                )
                return

            if interaction.user.id != state.current_turn:
                await interaction.response.send_message(
                    self.personality.format("battle_not_your_turn"),
                    ephemeral=False,
                )
                return

            try:
                state, effect, status = perform_move(state, interaction.user.id, move_name)
            except KeyError:
                await interaction.response.send_message(
                    self.personality.format("battle_invalid_move", move_name=move_name),
                    ephemeral=False,
                )
                return
            except PermissionError:
                await interaction.response.send_message(
                    self.personality.format("battle_not_your_turn"),
                    ephemeral=False,
                )
                return

            self._battles[channel_id] = state

            actor_name = interaction.user.display_name
            effect_text = effect
            status_text = status

            summary = self.personality.format(
                "battle_turn_result",
                actor=actor_name,
                move_name=move_name,
                effect=effect_text,
                status=status_text,
            )

            # If the battle finished, announce the winner and update stats.
            if state.is_finished and state.winner_id is not None:
                winner_id = state.winner_id
                loser_id = state.p1.user_id if winner_id == state.p2.user_id else state.p2.user_id
                winner_member = interaction.guild.get_member(winner_id) if interaction.guild else None
                loser_member = interaction.guild.get_member(loser_id) if interaction.guild else None

                winner_name = winner_member.display_name if winner_member else str(winner_id)
                victory_text = self.personality.format("battle_victory", winner=winner_name)
                summary = f"{summary}\n{victory_text}"

                # Persist battle outcome in Pokémon stats profile.
                await self.pokemon_data.record_battle(winner_id, won=True)
                await self.pokemon_data.record_battle(loser_id, won=False)

                if self.personality_memory is not None:
                    await self.personality_memory.add_event(
                        winner_id,
                        summary=f"Won a battle against {loser_name} in #{interaction.channel.name}",
                        tags=["battle_win", "pvp_battle"],
                    )
                    await self.personality_memory.add_event(
                        loser_id,
                        summary=f"Lost a battle against {winner_name} in #{interaction.channel.name}",
                        tags=["battle_loss", "pvp_battle"],
                    )

                # Clear the battle from active state.
                self._battles.pop(channel_id, None)

            await interaction.response.send_message(summary)

        @self.battle_group.command(name="forfeit", description="Forfeit your current battle")
        async def forfeit_cmd(interaction: discord.Interaction) -> None:  # type: ignore[unused-ignore]
            if not await ensure_bot_channel(interaction, getattr(self.config, "bot_channel_ids", set())):
                return

            channel_id = interaction.channel.id if interaction.channel else 0
            state = self._battles.get(channel_id)
            if state is None or interaction.user.id not in (
                state.p1.user_id,
                state.p2.user_id,
            ):
                await interaction.response.send_message(
                    self.personality.format("battle_not_in_battle"),
                    ephemeral=False,
                )
                return

            state, winner_id = forfeit(state, interaction.user.id)
            loser_id = interaction.user.id
            winner_member = interaction.guild.get_member(winner_id) if interaction.guild else None
            loser_member = interaction.user

            winner_name = winner_member.display_name if winner_member else str(winner_id)
            loser_name = loser_member.display_name

            text = self.personality.format(
                "battle_forfeit",
                loser=loser_name,
                winner=winner_name,
            )

            # Persist outcome
            await self.pokemon_data.record_battle(winner_id, won=True)
            await self.pokemon_data.record_battle(loser_id, won=False)

            if self.personality_memory is not None:
                await self.personality_memory.add_event(
                    winner_id,
                    summary=f"Won a battle by forfeit vs {loser_name} in #{interaction.channel.name}",
                    tags=["battle_win", "pvp_battle", "forfeit_win"],
                )
                await self.personality_memory.add_event(
                    loser_id,
                    summary=f"Forfeited a battle against {winner_name} in #{interaction.channel.name}",
                    tags=["battle_loss", "pvp_battle", "forfeit_loss"],
                )

            self._battles.pop(channel_id, None)

            await interaction.response.send_message(text)

        self.bot.tree.add_command(self.battle_group)


async def setup_battle_cog(bot: commands.Bot) -> None:
    await bot.add_cog(BattleCog(bot))


__all__ = ["BattleCog", "setup_battle_cog"]
