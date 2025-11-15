from __future__ import annotations

import random

import discord
from discord import app_commands
from discord.ext import commands

from fun_bot.core.channel_utils import ensure_bot_channel
from fun_bot.core.personality_engine import PersonalityEngine
from fun_bot.core.personality_memory import PersonalityMemory
from fun_bot.core.relationship_meter import RelationshipMeter
from fun_bot.core.cookie_manager import CookieManager


class EasterEggCog(commands.Cog):
    """Light-weight easter egg and fun commands.

    These commands are simple but routed through the personality engine
    and relationship meter to keep the tone consistent and rewarding.
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.personality: PersonalityEngine = getattr(bot, "personality", PersonalityEngine())
        self.config = getattr(bot, "config", None)
        self.cookie_manager: CookieManager = getattr(bot, "cookie_manager", None)
        storage = getattr(bot, "game_storage", None)
        self.relationship_meter = RelationshipMeter(storage) if storage is not None else None
        self.personality_memory: PersonalityMemory | None = getattr(bot, "personality_memory", None)
        self._pending_rps_users: set[int] = set()
        self._pending_trivia: dict[int, tuple[str, str]] = {}

    # ------------------------------------------------------------------
    # Message listener for interactive RPS (easter egg flow).
    # ------------------------------------------------------------------

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or not message.guild:
            return

        # Respect bot channel restriction if configured.
        bot_channel_ids = getattr(self.config, "bot_channel_ids", set()) or set()
        if bot_channel_ids and message.channel.id not in bot_channel_ids:
            return

        # Handle pending rock-paper-scissors first.
        if message.author.id in self._pending_rps_users:
            await self._handle_rps_reply(message)
            return

        # Handle pending trivia answers.
        if message.author.id in self._pending_trivia:
            await self._handle_trivia_reply(message)

    async def _handle_rps_reply(self, message: discord.Message) -> None:
        content = (message.content or "").strip().lower()
        moves = {"rock", "paper", "scissors"}
        if content not in moves:
            await message.reply(
                "Please reply with `rock`, `paper`, or `scissors` to play.",
                mention_author=True,
            )
            return

        # One shot: consume the pending state.
        self._pending_rps_users.discard(message.author.id)

        user_move = content
        bot_move = random.choice(list(moves))

        if self.relationship_meter is None:
            await message.reply(
                f"You played **{user_move}**. FunBot played **{bot_move}**. "
                f"Result: **{self._rps_result(user_move, bot_move).upper()}**!",
                mention_author=True,
            )
            return

        result = self._rps_result(user_move, bot_move)
        user_id = message.author.id
        meter = await self.relationship_meter.get_meter(user_id)
        cookie_reward = random.randint(1, 3)
        if meter > 5:
            cookie_reward = max(cookie_reward, 2)
        elif meter < -5:
            cookie_reward = min(cookie_reward, 1)

        if result == "win":
            await self.relationship_meter.adjust_meter(user_id, 2)
            if self.cookie_manager:
                await self.cookie_manager.add_cookies(user_id, cookie_reward)
            text = (
                f"🪨📄✂️ You played **{user_move}**. FunBot played **{bot_move}**.\n"
                f"🏆 **Result:** {result.upper()}!\n"
                f"🍪 You earned **{cookie_reward}** cookies!\n"
                f"Mood meter: {await self.relationship_meter.get_meter(user_id)}"
            )
        elif result == "tie":
            await self.relationship_meter.adjust_meter(user_id, 0)
            text = (
                f"🪨📄✂️ You played **{user_move}**. FunBot played **{bot_move}**.\n"
                f"🤝 **Result:** TIE!\n"
                f"Mood meter: {await self.relationship_meter.get_meter(user_id)}"
            )
        else:
            await self.relationship_meter.adjust_meter(user_id, -2)
            text = (
                f"🪨📄✂️ You played **{user_move}**. FunBot played **{bot_move}**.\n"
                f"😢 **Result:** {result.upper()}! No cookies this time.\n"
                f"Mood meter: {await self.relationship_meter.get_meter(user_id)}"
            )

        await message.reply(text, mention_author=True)

        if self.personality_memory is not None:
            tags = ["rps_win" if result == "win" else "rps_loss" if result == "lose" else "rps_tie"]
            mood_tag = "mood_up" if result == "win" else "mood_down" if result == "lose" else "mood_neutral"
            tags.append(mood_tag)
            await self.personality_memory.add_event(
                user_id,
                summary=(
                    f"Played rock-paper-scissors ({user_move} vs {bot_move}) "
                    f"with result: {result.upper()}."
                ),
                tags=tags,
            )

    async def _handle_trivia_reply(self, message: discord.Message) -> None:
        """Evaluate a user's trivia answer from a previous prompt."""

        user_id = message.author.id
        q, correct = self._pending_trivia.pop(user_id, (None, None))
        if not q or not correct:
            return

        answer_raw = (message.content or "").strip()
        if not answer_raw:
            await message.reply(
                "Please type an answer to the trivia question.",
                mention_author=True,
            )
            # Re-arm the question so they can try again.
            self._pending_trivia[user_id] = (q, correct)
            return

        if self.relationship_meter is None:
            await message.reply(
                f"Trivia answer recorded! The correct answer was **{correct}**.",
                mention_author=True,
            )
            return

        is_correct = answer_raw.lower() == correct.lower()
        meter_before = await self.relationship_meter.get_meter(user_id)

        if is_correct:
            cookie_reward = random.randint(1, 3)
            await self.relationship_meter.adjust_meter(user_id, 2)
            if self.cookie_manager:
                await self.cookie_manager.add_cookies(user_id, cookie_reward)
            text = (
                f"✅ Correct! The answer was **{correct}**.\n"
                f"You earned **{cookie_reward}** cookies. "
                f"Relationship meter: {await self.relationship_meter.get_meter(user_id)}"
            )
            tags = ["trivia_win", "mood_up"]
            summary = f"Answered trivia correctly ({correct}) and earned {cookie_reward} cookies."
        else:
            await self.relationship_meter.adjust_meter(user_id, -1)
            text = (
                f"❌ Not quite. You answered **{answer_raw}**, "
                f"but the correct answer was **{correct}**.\n"
                f"Relationship meter: {await self.relationship_meter.get_meter(user_id)}"
            )
            tags = ["trivia_miss", "mood_down"]
            summary = f"Missed a trivia question (correct answer: {correct})."

        await message.reply(text, mention_author=True)

        if self.personality_memory is not None:
            await self.personality_memory.add_event(
                user_id,
                summary=summary,
                tags=tags,
            )

    # ------------------------------------------------------------------
    # Internal helpers used by both direct commands and /easteregg.
    # ------------------------------------------------------------------

    async def _run_trivia(self, interaction: discord.Interaction) -> None:
        if not await ensure_bot_channel(interaction, getattr(self.config, "bot_channel_ids", set())):
            return

        questions = [
            ("What is the capital of France?", "Paris"),
            ("Who wrote 'To be, or not to be'?", "Shakespeare"),
            ("What planet is known as the Red Planet?", "Mars"),
            ("What is 2 + 2?", "4"),
            ("Which ocean is the largest?", "Pacific"),
        ]
        q, a = random.choice(questions)
        await interaction.response.send_message(
            f"🧠 **Trivia Time!**\n"
            f"❓ {q}\n"
            "Type your answer in chat! (For now, I believe in you 😄)",
            ephemeral=False,
        )
        # Arm an interactive trivia session; their next message in the bot
        # channel will be treated as the answer.
        self._pending_trivia[interaction.user.id] = (q, a)

    async def _run_weather(self, interaction: discord.Interaction) -> None:
        if not await ensure_bot_channel(interaction, getattr(self.config, "bot_channel_ids", set())):
            return

        conditions = ["sunny", "rainy", "cloudy", "stormy", "foggy", "snowy", "windy"]
        temps = ["hot", "warm", "mild", "cool", "cold", "freezing"]
        weather_text = f"🌦️ **Weather Report!**\nIt's {random.choice(conditions)} and {random.choice(temps)} today!"

        if self.relationship_meter is None:
            await interaction.response.send_message(weather_text, ephemeral=False)
            return

        user_id = interaction.user.id
        meter = await self.relationship_meter.get_meter(user_id)
        cookie_reward = random.randint(1, 3)
        if meter > 5:
            cookie_reward = max(cookie_reward, 2)
        elif meter < -5:
            cookie_reward = min(cookie_reward, 1)
        await self.relationship_meter.adjust_meter(user_id, 1)

        await interaction.response.send_message(
            f"{weather_text}\n"
            f"You earned **{cookie_reward}** cookies. "
            f"Relationship meter: {await self.relationship_meter.get_meter(user_id)}",
            ephemeral=False,
        )
        if self.personality_memory is not None:
            await self.personality_memory.add_event(
                user_id,
                summary=f"Checked the weather and earned {cookie_reward} cookies.",
                tags=["weather_check", "mood_up"],
            )

    async def _run_magic8(self, interaction: discord.Interaction, question: str | None = None) -> None:
        if not await ensure_bot_channel(interaction, getattr(self.config, "bot_channel_ids", set())):
            return

        responses = [
            "Yes!",
            "No!",
            "Maybe...",
            "Ask again later.",
            "Definitely!",
            "Unlikely.",
            "Absolutely.",
            "I don't think so.",
            "Signs point to yes.",
            "Outlook not so good.",
        ]
        answer = random.choice(responses)

        prompt = f"🎱 **Magic 8 Ball** says: *{answer}*"
        if question:
            prompt = f"🔮 Q: {question}\n{prompt}"

        if self.relationship_meter is None:
            await interaction.response.send_message(prompt, ephemeral=False)
            return

        user_id = interaction.user.id
        meter = await self.relationship_meter.get_meter(user_id)
        cookie_reward = random.randint(1, 3)
        if meter > 5:
            cookie_reward = max(cookie_reward, 2)
        elif meter < -5:
            cookie_reward = min(cookie_reward, 1)
        await self.relationship_meter.adjust_meter(user_id, 1)

        await interaction.response.send_message(
            f"{prompt}\n"
            f"You earned **{cookie_reward}** cookies. "
            f"Relationship meter: {await self.relationship_meter.get_meter(user_id)}",
            ephemeral=False,
        )
        if self.personality_memory is not None:
            await self.personality_memory.add_event(
                user_id,
                summary=f"Asked the magic 8 ball and got '{answer}'.",
                tags=["magic8"],
            )

    async def _run_rps(self, interaction: discord.Interaction, move: str) -> None:
        if not await ensure_bot_channel(interaction, getattr(self.config, "bot_channel_ids", set())):
            return

        moves = ["rock", "paper", "scissors"]
        user_move = move.lower()
        if user_move not in moves:
            await interaction.response.send_message(
                "🤔 Invalid move! Please choose 🪨 rock, 📄 paper, or ✂️ scissors.",
                ephemeral=False,
            )
            return

        bot_move = random.choice(moves)
        result = self._rps_result(user_move, bot_move)

        if self.relationship_meter is None:
            await interaction.response.send_message(
                f"You played **{user_move}**. FunBot played **{bot_move}**. "
                f"Result: **{result.upper()}**!",
                ephemeral=False,
            )
            return

        user_id = interaction.user.id
        meter = await self.relationship_meter.get_meter(user_id)
        cookie_reward = random.randint(1, 3)
        if meter > 5:
            cookie_reward = max(cookie_reward, 2)
        elif meter < -5:
            cookie_reward = min(cookie_reward, 1)

        if result == "win":
            await self.relationship_meter.adjust_meter(user_id, 2)
            if self.cookie_manager:
                await self.cookie_manager.add_cookies(user_id, cookie_reward)
            text = (
                f"🪨📄✂️ You played **{user_move}**. FunBot played **{bot_move}**.\n"
                f"🏆 **Result:** {result.upper()}!\n"
                f"🍪 You earned **{cookie_reward}** cookies!\n"
                f"Mood meter: {await self.relationship_meter.get_meter(user_id)}"
            )
        elif result == "tie":
            await self.relationship_meter.adjust_meter(user_id, 0)
            text = (
                f"🪨📄✂️ You played **{user_move}**. FunBot played **{bot_move}**.\n"
                f"🤝 **Result:** TIE!\n"
                f"Mood meter: {await self.relationship_meter.get_meter(user_id)}"
            )
        else:
            await self.relationship_meter.adjust_meter(user_id, -2)
            text = (
                f"🪨📄✂️ You played **{user_move}**. FunBot played **{bot_move}**.\n"
                f"😢 **Result:** {result.upper()}! No cookies this time.\n"
                f"Mood meter: {await self.relationship_meter.get_meter(user_id)}"
            )

        await interaction.response.send_message(text, ephemeral=False)

        if self.personality_memory is not None:
            tags = ["rps_win" if result == "win" else "rps_loss" if result == "lose" else "rps_tie"]
            mood_tag = "mood_up" if result == "win" else "mood_down" if result == "lose" else "mood_neutral"
            tags.append(mood_tag)
            await self.personality_memory.add_event(
                user_id,
                summary=(
                    f"Played rock-paper-scissors ({user_move} vs {bot_move}) "
                    f"with result: {result.upper()}."
                ),
                tags=tags,
            )

    @staticmethod
    def _rps_result(user_move: str, bot_move: str) -> str:
        if user_move == bot_move:
            return "tie"
        if (user_move == "rock" and bot_move == "scissors") or (
            user_move == "paper" and bot_move == "rock"
        ) or (user_move == "scissors" and bot_move == "paper"):
            return "win"
        return "lose"

    async def _run_ping(self, interaction: discord.Interaction) -> None:
        if not await ensure_bot_channel(interaction, getattr(self.config, "bot_channel_ids", set())):
            return

        text = self.personality.format("easter_ping")
        await interaction.response.send_message(text, ephemeral=False)

    async def _run_vibe(self, interaction: discord.Interaction) -> None:
        if not await ensure_bot_channel(interaction, getattr(self.config, "bot_channel_ids", set())):
            return

        vibe_word = random.choice(["chill", "hyped", "chaotic good", "pog", "cozy"])
        text = self.personality.format("easter_vibe", vibe=vibe_word)
        if self.relationship_meter is None:
            await interaction.response.send_message(text, ephemeral=False)
            return

        user_id = interaction.user.id
        if vibe_word in ["chill", "cozy"]:
            await self.relationship_meter.adjust_meter(user_id, 2)
            cookie_reward = random.randint(1, 3)
            if self.cookie_manager:
                await self.cookie_manager.add_cookies(user_id, cookie_reward)
            reply = (
                f"{text}\n"
                f"You earned **{cookie_reward}** cookies. "
                f"Relationship meter: {await self.relationship_meter.get_meter(user_id)}"
            )
        else:
            await self.relationship_meter.adjust_meter(user_id, -1)
            reply = (
                f"{text}\n"
                f"No cookies this time. "
                f"Relationship meter: {await self.relationship_meter.get_meter(user_id)}"
            )
        await interaction.response.send_message(reply, ephemeral=False)

        if self.relationship_meter is not None and self.personality_memory is not None:
            meter = await self.relationship_meter.get_meter(user_id)
            tags = ["vibe_good" if vibe_word in ["chill", "cozy"] else "vibe_bad"]
            if vibe_word not in ["chill", "cozy"]:
                tags.append("mood_down")
            await self.personality_memory.add_event(
                user_id,
                summary=f"Got a vibe check: '{vibe_word}' (meter now {meter}).",
                tags=tags,
            )

    # ------------------------------------------------------------------
    # Slash commands (public API)
    # ------------------------------------------------------------------

    @app_commands.command(name="trivia", description="Answer a random trivia question!")
    async def trivia(self, interaction: discord.Interaction) -> None:
        await self._run_trivia(interaction)

    @app_commands.command(name="weather", description="Get a randomized weather report!")
    async def weather(self, interaction: discord.Interaction) -> None:
        await self._run_weather(interaction)

    @app_commands.command(name="magic8", description="Ask the magic 8 ball!")
    @app_commands.describe(question="What do you want to ask the 8 ball?")
    async def magic8(self, interaction: discord.Interaction, question: str) -> None:
        await self._run_magic8(interaction, question=question)

    @app_commands.command(name="rps", description="Play rock-paper-scissors with FunBot!")
    @app_commands.describe(move="Your move: rock, paper, or scissors")
    async def rps(self, interaction: discord.Interaction, move: str) -> None:
        await self._run_rps(interaction, move=move)

    @app_commands.command(name="ping", description="Check if FunBot is awake")
    async def ping(self, interaction: discord.Interaction) -> None:
        await self._run_ping(interaction)

    @app_commands.command(name="vibe", description="Get a quick vibe check")
    async def vibe(self, interaction: discord.Interaction) -> None:
        await self._run_vibe(interaction)

    @app_commands.command(
        name="easteregg",
        description="Trigger a random easter egg game and reward.",
    )
    async def easteregg(self, interaction: discord.Interaction) -> None:
        """Randomly choose one of the easter egg games."""

        if not await ensure_bot_channel(interaction, getattr(self.config, "bot_channel_ids", set())):
            return

        handlers = [
            self._run_trivia,
            self._run_weather,
            lambda i: self._run_magic8(i, question="Will I get a cookie?"),
            self._start_easteregg_rps,
            self._run_ping,
            self._run_vibe,
        ]
        chosen = random.choice(handlers)
        await chosen(interaction)

    async def _start_easteregg_rps(self, interaction: discord.Interaction) -> None:
        """Easter egg entry point for interactive rock-paper-scissors."""

        if not await ensure_bot_channel(interaction, getattr(self.config, "bot_channel_ids", set())):
            return

        self._pending_rps_users.add(interaction.user.id)
        await interaction.response.send_message(
            "🪨📄✂️ Let's play rock-paper-scissors!\n"
            "Reply to this message in chat with `rock`, `paper`, or `scissors`.",
            ephemeral=False,
        )


__all__ = ["EasterEggCog"]
