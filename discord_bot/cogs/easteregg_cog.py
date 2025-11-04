"""
EasterEggCog - Fun interactions, games, and random surprises.

Includes:
- Rock-Paper-Scissors
- Trivia questions
- Riddles
- Jokes, cat facts, random facts
- Weather lookup
- Magic 8-ball
- Random easter eggs
- Daily cookie limits (max 5 per day)
- Spam detection and progressive penalties
"""

from __future__ import annotations

import aiohttp
import discord
import random
from datetime import datetime, timedelta
from discord import app_commands
from discord.ext import commands
from typing import Optional, TYPE_CHECKING

from discord_bot.core import ui_groups
from discord_bot.core.utils import (
    find_bot_channel,
    is_allowed_channel,
    safe_send_interaction_response,
)

if TYPE_CHECKING:
    from discord_bot.core.engines.relationship_manager import RelationshipManager
    from discord_bot.core.engines.cookie_manager import CookieManager
    from discord_bot.core.engines.personality_engine import PersonalityEngine
    from discord_bot.games.storage.game_storage_engine import GameStorageEngine


class EasterEggCog(commands.Cog):
    """Fun interactions and mini-games with cookie rewards."""
    
    # Command groups for better organization
    fun = app_commands.Group(
        name=ui_groups.GAMES_FUN_NAME,
        description=ui_groups.GAMES_FUN_DESCRIPTION,
        parent=ui_groups.games,
    )
    
    # Note: cookies group is defined in GameCog to avoid duplicate registration
    # We'll attach cookie commands dynamically in __init__
    
    # RPS choices
    RPS_CHOICES = ['rock', 'paper', 'scissors']
    RPS_EMOJIS = {'rock': '🪨', 'paper': '📄', 'scissors': '✂️'}
    
    # 8-ball responses
    EIGHT_BALL_RESPONSES = [
        "Yes, definitely! 🎱",
        "It is certain. 🎱",
        "Without a doubt. 🎱",
        "You may rely on it. 🎱",
        "As I see it, yes. 🎱",
        "Most likely. 🎱",
        "Outlook good. 🎱",
        "Signs point to yes. 🎱",
        "Reply hazy, try again. 🎱",
        "Ask again later. 🎱",
        "Better not tell you now. 🎱",
        "Cannot predict now. 🎱",
        "Concentrate and ask again. 🎱",
        "Don't count on it. 🎱",
        "My reply is no. 🎱",
        "My sources say no. 🎱",
        "Outlook not so good. 🎱",
        "Very doubtful. 🎱"
    ]
    
    # Simple trivia questions
    TRIVIA_QUESTIONS = [
        {"question": "What is the capital of France?", "answer": "paris", "options": ["London", "Berlin", "Paris", "Madrid"]},
        {"question": "How many continents are there?", "answer": "7", "options": ["5", "6", "7", "8"]},
        {"question": "What year did World War II end?", "answer": "1945", "options": ["1943", "1944", "1945", "1946"]},
        {"question": "What is the largest planet in our solar system?", "answer": "jupiter", "options": ["Mars", "Saturn", "Jupiter", "Neptune"]},
        {"question": "Who painted the Mona Lisa?", "answer": "leonardo da vinci", "options": ["Michelangelo", "Leonardo da Vinci", "Raphael", "Donatello"]},
    ]
    
    # Simple riddles
    RIDDLES = [
        {"question": "I speak without a mouth and hear without ears. I have no body, but I come alive with wind. What am I?", "answer": "echo"},
        {"question": "What has keys but no locks, space but no room, and you can enter but can't go inside?", "answer": "keyboard"},
        {"question": "The more you take, the more you leave behind. What am I?", "answer": "footsteps"},
        {"question": "What has hands but can't clap?", "answer": "clock"},
        {"question": "What gets wetter the more it dries?", "answer": "towel"},
    ]
    
    def __init__(self, bot: commands.Bot, relationship_manager: RelationshipManager,
                 cookie_manager: CookieManager, personality_engine: PersonalityEngine,
                 storage: Optional[GameStorageEngine] = None):
        self.bot = bot
        self.relationship_manager = relationship_manager
        self.cookie_manager = cookie_manager
        self.personality_engine = personality_engine
        self.storage = storage
        self.active_trivia = {}  # Track active trivia sessions
        self.active_riddles = {}  # Track active riddle sessions

    async def _check_allowed_channel(self, interaction: discord.Interaction) -> bool:
        """Check if command is used in bot channel only. Call BEFORE responding to interaction."""
        if not interaction.channel:
            await safe_send_interaction_response(
                interaction,
                content="🦛 I can only respond to game and fun commands in the bot channel!",
                ephemeral=True,
            )
            return False
        
        if not is_allowed_channel(interaction.channel.id):
            await safe_send_interaction_response(
                interaction,
                content=(
                    "🦛 I can only respond to game and fun commands in the bot channel! "
                    "Please use the designated bot channel."
                ),
                ephemeral=True,
            )
            return False
        return True

    @app_commands.command(name="easteregg", description="🎲 Trigger a random easter egg surprise!")
    async def easter_egg(self, interaction: discord.Interaction) -> None:
        """Random easter egg - could be anything!"""
        # Defer response to prevent timeout during database operations
        await interaction.response.defer(ephemeral=True)
        
        # Check if in allowed channel
        if not await self._check_allowed_channel(interaction):
            return
        
        user_id = str(interaction.user.id)
        
        # Check if user is muted (from spam detection)
        if self.storage and self.storage.is_muted(user_id):
            mute_until = self.storage.get_mute_until(user_id)
            if mute_until:
                time_left = mute_until - datetime.utcnow()
                minutes_left = int(time_left.total_seconds() / 60)
                await interaction.followup.send(
                    f"🚫 You're currently muted for spamming! Time remaining: {minutes_left} minutes.",
                    ephemeral=True
                )
                return
        
        # Check daily easter egg limit
        can_earn, cookies_today = self.cookie_manager.check_easter_egg_limit(user_id)
        
        if not can_earn:
            # User has reached daily limit - handle spam
            spam_result = self.cookie_manager.handle_easter_egg_spam(user_id)
            
            # Get dynamic message based on aggravation level and mood
            limit_msg = self.personality_engine.get_easter_egg_limit_message(
                interaction.user.display_name,
                spam_result['aggravation_level']
            )
            
            response_parts = [limit_msg]
            
            # Add cookie penalty message if applicable
            if spam_result['cookie_penalty'] > 0:
                penalty_msg = self.personality_engine.get_cookie_penalty_message(
                    interaction.user.display_name,
                    spam_result['cookie_penalty']
                )
                response_parts.append(penalty_msg)
                # Make bot more grumpy
                self.personality_engine.set_mood('grumpy')
            
            # Add mute warning if chance is high
            if spam_result['mute_chance'] >= 30:
                warning_msg = self.personality_engine.get_mute_warning_message(
                    interaction.user.display_name,
                    spam_result['mute_chance']
                )
                response_parts.append(warning_msg)
            
            # Apply mute if triggered
            if spam_result['should_mute'] and self.storage:
                mute_until = datetime.utcnow() + timedelta(minutes=self.cookie_manager.MUTE_DURATION_MINUTES)
                self.storage.set_mute_until(user_id, mute_until)
                
                # Try to apply Discord timeout
                if interaction.guild and interaction.guild.me.guild_permissions.moderate_members:
                    try:
                        await interaction.user.timeout(
                            timedelta(minutes=self.cookie_manager.MUTE_DURATION_MINUTES),
                            reason="Spamming easter egg commands after reaching daily limit"
                        )
                        response_parts.append(
                            f"🚫 **MUTED for {self.cookie_manager.MUTE_DURATION_MINUTES} minutes!** That's what happens when you don't listen! 😤"
                        )
                    except (discord.Forbidden, discord.HTTPException):
                        response_parts.append(
                            f"⚠️ I tried to mute you but couldn't! Consider this a warning! 😠"
                        )
                else:
                    response_parts.append(
                        f"⚠️ You've been internally muted for {self.cookie_manager.MUTE_DURATION_MINUTES} minutes! 🚫"
                    )
            
            await interaction.followup.send("\n\n".join(response_parts), ephemeral=True)
            return
        
        # Record interaction
        self.relationship_manager.record_interaction(user_id, 'easter_egg')
        
        # Random easter egg selection
        egg_type = random.choice(['joke', 'catfact', 'fact', 'wisdom', 'rps', 'trivia', 'riddle', '8ball'])
        
        if egg_type == 'rps':
            await interaction.followup.send(
                "🎲 Rock, Paper, Scissors! Use `/rps <choice>` to play!"
            )
        elif egg_type == 'trivia':
            await self._start_trivia(interaction)
        elif egg_type == 'riddle':
            await self._start_riddle(interaction)
        elif egg_type == '8ball':
            response = random.choice(self.EIGHT_BALL_RESPONSES)
            await interaction.followup.send(f"🎱 The magic 8-ball says: {response}")
        elif egg_type == 'joke':
            joke = await self._fetch_joke()
            await interaction.followup.send(f"😄 {joke}")
        elif egg_type == 'catfact':
            fact = await self._fetch_cat_fact()
            await interaction.followup.send(f"🐱 {fact}")
        elif egg_type == 'fact':
            fact = await self._fetch_random_fact()
            await interaction.followup.send(f"💡 {fact}")
        else:  # wisdom
            wisdom = self._get_hippo_wisdom()
            await interaction.followup.send(f"🦛 {wisdom}")
        
        # Try to award cookies (with daily limit checking)
        cookies = self.cookie_manager.try_award_easter_egg_cookies(
            user_id, self.personality_engine.get_mood()
        )
        if cookies:
            reward_msg = self.personality_engine.get_cookie_reward_message(cookies, interaction.user.display_name, str(interaction.user.id))
            
            # Show progress toward daily limit
            _, cookies_today = self.cookie_manager.check_easter_egg_limit(user_id)
            progress = f" ({cookies_today}/{self.cookie_manager.MAX_DAILY_EASTER_EGG_COOKIES} daily cookies)"
            
            await interaction.followup.send(reward_msg + progress, ephemeral=True)
            
            # Reset aggravation on successful interaction
            if self.storage:
                self.storage.reset_aggravation(user_id)

    @fun.command(name="rps", description="✊ Play Rock, Paper, Scissors with Baby Hippo!")
    @app_commands.describe(choice="Your choice: rock, paper, or scissors")
    async def rps(self, interaction: discord.Interaction, choice: str) -> None:
        """Play Rock-Paper-Scissors."""
        # Check if in allowed channel
        if not await self._check_allowed_channel(interaction):
            return
        
        user_id = str(interaction.user.id)
        choice = choice.lower()
        
        if choice not in self.RPS_CHOICES:
            await interaction.response.send_message(
                "❌ Invalid choice! Pick: rock, paper, or scissors",
                ephemeral=True
            )
            return
        
        # Bot makes a choice
        bot_choice = random.choice(self.RPS_CHOICES)
        
        # Determine winner
        result = self._rps_winner(choice, bot_choice)
        
        # Build response
        user_emoji = self.RPS_EMOJIS[choice]
        bot_emoji = self.RPS_EMOJIS[bot_choice]
        
        # RESPOND IMMEDIATELY to avoid timeout
        if result == 'win':
            message = f"{user_emoji} vs {bot_emoji}\n🎉 You won! *grumbles* 😒"
        elif result == 'lose':
            message = f"{user_emoji} vs {bot_emoji}\n😄 I won! Better luck next time!"
        else:  # tie
            message = f"{user_emoji} vs {bot_emoji}\n🤝 It's a tie! Let's go again!"
        
        await interaction.response.send_message(message)
        
        # Process personality/cookies AFTER responding
        if result == 'win':
            # User wins - bot gets grumpy, user gets cookies
            self.personality_engine.set_mood('grumpy')
            self.relationship_manager.record_interaction(user_id, 'rps_win')
            
            cookies = self.cookie_manager.try_award_cookies(user_id, 'rps_win', 'neutral')
            if cookies:
                cookie_msg = self.personality_engine.get_cookie_reward_message(cookies, interaction.user.display_name, str(interaction.user.id))
                await interaction.followup.send(cookie_msg, ephemeral=True)
            
        elif result == 'lose':
            # Bot wins - bot gets happy
            self.personality_engine.set_mood('happy')
            self.relationship_manager.record_interaction(user_id, 'game_action')
            
        else:  # tie
            self.relationship_manager.record_interaction(user_id, 'game_action')

    @fun.command(name="joke", description="😂 Get a random joke!")
    async def joke(self, interaction: discord.Interaction) -> None:
        """Fetch a random joke."""
        # Check if in allowed channel
        if not await self._check_allowed_channel(interaction):
            return
        
        user_id = str(interaction.user.id)
        
        # Check if user is muted
        if self.storage and self.storage.is_muted(user_id):
            mute_until = self.storage.get_mute_until(user_id)
            if mute_until:
                time_left = mute_until - datetime.utcnow()
                minutes_left = int(time_left.total_seconds() / 60)
                await interaction.response.send_message(
                    f"🚫 You're currently muted! Time remaining: {minutes_left} minutes.",
                    ephemeral=True
                )
                return
        
        # Check daily limit
        can_earn, cookies_today = self.cookie_manager.check_easter_egg_limit(user_id)
        if not can_earn:
            spam_result = self.cookie_manager.handle_easter_egg_spam(user_id)
            limit_msg = self.personality_engine.get_easter_egg_limit_message(
                interaction.user.display_name,
                spam_result['aggravation_level']
            )
            await interaction.response.send_message(limit_msg, ephemeral=True)
            return
        
        self.relationship_manager.record_interaction(user_id, 'easter_egg')
        
        joke = await self._fetch_joke()
        await interaction.response.send_message(f"😄 {joke}")
        
        # Try cookie reward with limit
        cookies = self.cookie_manager.try_award_easter_egg_cookies(user_id, self.personality_engine.get_mood())
        if cookies:
            reward_msg = self.personality_engine.get_cookie_reward_message(cookies, interaction.user.display_name, str(interaction.user.id))
            _, cookies_today = self.cookie_manager.check_easter_egg_limit(user_id)
            progress = f" ({cookies_today}/{self.cookie_manager.MAX_DAILY_EASTER_EGG_COOKIES} daily cookies)"
            await interaction.followup.send(reward_msg + progress, ephemeral=True)
            if self.storage:
                self.storage.reset_aggravation(user_id)

    @fun.command(name="catfact", description="🐱 Get a random cat fact!")
    async def cat_fact(self, interaction: discord.Interaction) -> None:
        """Fetch a random cat fact."""
        # Check if in allowed channel
        if not await self._check_allowed_channel(interaction):
            return
        
        user_id = str(interaction.user.id)
        
        # Check if user is muted
        if self.storage and self.storage.is_muted(user_id):
            mute_until = self.storage.get_mute_until(user_id)
            if mute_until:
                time_left = mute_until - datetime.utcnow()
                minutes_left = int(time_left.total_seconds() / 60)
                await interaction.response.send_message(
                    f"🚫 You're currently muted! Time remaining: {minutes_left} minutes.",
                    ephemeral=True
                )
                return
        
        # Check daily limit
        can_earn, cookies_today = self.cookie_manager.check_easter_egg_limit(user_id)
        if not can_earn:
            spam_result = self.cookie_manager.handle_easter_egg_spam(user_id)
            limit_msg = self.personality_engine.get_easter_egg_limit_message(
                interaction.user.display_name,
                spam_result['aggravation_level']
            )
            await interaction.response.send_message(limit_msg, ephemeral=True)
            return
        
        self.relationship_manager.record_interaction(user_id, 'easter_egg')
        
        fact = await self._fetch_cat_fact()
        await interaction.response.send_message(f"🐱 {fact}")
        
        # Try cookie reward with limit
        cookies = self.cookie_manager.try_award_easter_egg_cookies(user_id, self.personality_engine.get_mood())
        if cookies:
            reward_msg = self.personality_engine.get_cookie_reward_message(cookies, interaction.user.display_name, str(interaction.user.id))
            _, cookies_today = self.cookie_manager.check_easter_egg_limit(user_id)
            progress = f" ({cookies_today}/{self.cookie_manager.MAX_DAILY_EASTER_EGG_COOKIES} daily cookies)"
            await interaction.followup.send(reward_msg + progress, ephemeral=True)
            if self.storage:
                self.storage.reset_aggravation(user_id)

    @fun.command(name="weather", description="🌤️ Get weather for a location")
    @app_commands.describe(location="City name or location")
    async def weather(self, interaction: discord.Interaction, location: str) -> None:
        """Fetch weather information."""
        # Check if in allowed channel
        if not await self._check_allowed_channel(interaction):
            return
        
        user_id = str(interaction.user.id)
        
        # Check if user is muted
        if self.storage and self.storage.is_muted(user_id):
            mute_until = self.storage.get_mute_until(user_id)
            if mute_until:
                time_left = mute_until - datetime.utcnow()
                minutes_left = int(time_left.total_seconds() / 60)
                await interaction.response.send_message(
                    f"🚫 You're currently muted! Time remaining: {minutes_left} minutes.",
                    ephemeral=True
                )
                return
        
        # Check daily limit
        can_earn, cookies_today = self.cookie_manager.check_easter_egg_limit(user_id)
        if not can_earn:
            spam_result = self.cookie_manager.handle_easter_egg_spam(user_id)
            limit_msg = self.personality_engine.get_easter_egg_limit_message(
                interaction.user.display_name,
                spam_result['aggravation_level']
            )
            await interaction.response.send_message(limit_msg, ephemeral=True)
            return
        
        self.relationship_manager.record_interaction(user_id, 'easter_egg')
        
        weather_info = await self._fetch_weather(location)
        await interaction.response.send_message(weather_info)
        
        # Try cookie reward with limit
        cookies = self.cookie_manager.try_award_easter_egg_cookies(user_id, self.personality_engine.get_mood())
        if cookies:
            reward_msg = self.personality_engine.get_cookie_reward_message(cookies, interaction.user.display_name, str(interaction.user.id))
            _, cookies_today = self.cookie_manager.check_easter_egg_limit(user_id)
            progress = f" ({cookies_today}/{self.cookie_manager.MAX_DAILY_EASTER_EGG_COOKIES} daily cookies)"
            await interaction.followup.send(reward_msg + progress, ephemeral=True)
            if self.storage:
                self.storage.reset_aggravation(user_id)

    @fun.command(name="8ball", description="🎱 Ask the magic 8-ball a question")
    @app_commands.describe(question="Your yes/no question")
    async def eight_ball(self, interaction: discord.Interaction, question: str) -> None:
        """Magic 8-ball responses."""
        # Check if in allowed channel
        if not await self._check_allowed_channel(interaction):
            return
        
        user_id = str(interaction.user.id)
        
        # Check if user is muted
        if self.storage and self.storage.is_muted(user_id):
            mute_until = self.storage.get_mute_until(user_id)
            if mute_until:
                time_left = mute_until - datetime.utcnow()
                minutes_left = int(time_left.total_seconds() / 60)
                await interaction.response.send_message(
                    f"🚫 You're currently muted! Time remaining: {minutes_left} minutes.",
                    ephemeral=True
                )
                return
        
        # Check daily limit
        can_earn, cookies_today = self.cookie_manager.check_easter_egg_limit(user_id)
        if not can_earn:
            spam_result = self.cookie_manager.handle_easter_egg_spam(user_id)
            limit_msg = self.personality_engine.get_easter_egg_limit_message(
                interaction.user.display_name,
                spam_result['aggravation_level']
            )
            await interaction.response.send_message(limit_msg, ephemeral=True)
            return
        
        self.relationship_manager.record_interaction(user_id, 'easter_egg')
        
        response = random.choice(self.EIGHT_BALL_RESPONSES)
        await interaction.response.send_message(f"❓ {question}\n{response}")
        
        # Try cookie reward with limit
        cookies = self.cookie_manager.try_award_easter_egg_cookies(user_id, self.personality_engine.get_mood())
        if cookies:
            reward_msg = self.personality_engine.get_cookie_reward_message(cookies, interaction.user.display_name, str(interaction.user.id))
            _, cookies_today = self.cookie_manager.check_easter_egg_limit(user_id)
            progress = f" ({cookies_today}/{self.cookie_manager.MAX_DAILY_EASTER_EGG_COOKIES} daily cookies)"
            await interaction.followup.send(reward_msg + progress, ephemeral=True)
            if self.storage:
                self.storage.reset_aggravation(user_id)

    # Helper methods
    def _rps_winner(self, user_choice: str, bot_choice: str) -> str:
        """Determine RPS winner. Returns 'win', 'lose', or 'tie'."""
        if user_choice == bot_choice:
            return 'tie'
        
        wins = {
            'rock': 'scissors',
            'paper': 'rock',
            'scissors': 'paper'
        }
        
        return 'win' if wins[user_choice] == bot_choice else 'lose'

    async def _start_trivia(self, interaction: discord.Interaction) -> None:
        """Start a trivia question."""
        question_data = random.choice(self.TRIVIA_QUESTIONS)
        self.active_trivia[interaction.user.id] = question_data
        
        options = "\n".join([f"{i+1}. {opt}" for i, opt in enumerate(question_data['options'])])
        await interaction.response.send_message(
            f"🧠 **Trivia Time!**\n{question_data['question']}\n\n{options}\n\nReply with the number or answer!"
        )

    async def _start_riddle(self, interaction: discord.Interaction) -> None:
        """Start a riddle."""
        riddle_data = random.choice(self.RIDDLES)
        self.active_riddles[interaction.user.id] = riddle_data
        
        await interaction.response.send_message(
            f"🤔 **Riddle Time!**\n{riddle_data['question']}\n\nReply with your answer!"
        )

    async def _fetch_joke(self) -> str:
        """Fetch a joke from an API."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get('https://official-joke-api.appspot.com/random_joke') as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return f"{data['setup']}\n...{data['punchline']}"
        except Exception:
            pass
        
        # Fallback jokes
        fallback_jokes = [
            "Why don't hippos like fast food? Because they can't catch it! 🦛",
            "What do you call a hippo with a bad attitude? A hippocrite! 🦛",
            "Why did the hippo cross the road? To prove it wasn't chicken! 🦛🐔"
        ]
        return random.choice(fallback_jokes)

    async def _fetch_cat_fact(self) -> str:
        """Fetch a cat fact from an API."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get('https://catfact.ninja/fact') as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data['fact']
        except Exception:
            pass
        
        return "Cats spend 70% of their lives sleeping. That's 13-16 hours a day! 😴🐱"

    async def _fetch_random_fact(self) -> str:
        """Fetch a random fun fact."""
        fallback_facts = [
            "Hippos can run up to 30 mph on land! 🦛💨",
            "A group of hippos is called a bloat! 🦛🦛🦛",
            "Hippos produce their own sunscreen - a red, oily substance! 🦛☀️",
            "Baby hippos are born underwater and must swim to the surface for their first breath! 🦛🌊",
            "Hippos can hold their breath for up to 5 minutes! 🦛💨"
        ]
        return random.choice(fallback_facts)

    async def _fetch_weather(self, location: str) -> str:
        """Fetch weather information."""
        try:
            # Using wttr.in - no API key required
            async with aiohttp.ClientSession() as session:
                async with session.get(f'https://wttr.in/{location}?format=3') as resp:
                    if resp.status == 200:
                        text = await resp.text()
                        return f"🌤️ {text.strip()}"
        except Exception:
            pass
        
        return f"⚠️ Couldn't fetch weather for {location}. Try again later!"

    def _get_hippo_wisdom(self) -> str:
        """Get random hippo wisdom."""
        wisdom = [
            "Remember: stay cool like a hippo in water! 🦛💧",
            "Life is better when you're floating! 🦛🌊",
            "Don't let anyone dull your sparkle! ✨🦛",
            "Take time to relax in the river of life! 🦛🌊",
            "Be yourself - everyone else is taken! 🦛💖",
            "Sometimes you just need a good nap in the mud! 🦛😴"
        ]
        return random.choice(wisdom)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """Handle @mentions and check for trivia/riddle answers."""
        if message.author.bot:
            return
        
        user_id = str(message.author.id)
        
        # Check for trivia answer
        if message.author.id in self.active_trivia:
            question_data = self.active_trivia[message.author.id]
            user_answer = message.content.lower().strip()
            
            if user_answer == question_data['answer'] or user_answer in question_data['answer']:
                del self.active_trivia[message.author.id]
                self.relationship_manager.record_interaction(user_id, 'trivia_correct')
                
                cookies = self.cookie_manager.try_award_cookies(user_id, 'trivia_correct', self.personality_engine.get_mood())
                response = "🎉 Correct! Great job!"
                if cookies:
                    response += f"\n{self.personality_engine.get_cookie_reward_message(cookies, message.author.display_name, str(message.author.id))}"
                
                await message.channel.send(response)
                return
        
        # Check for riddle answer
        if message.author.id in self.active_riddles:
            riddle_data = self.active_riddles[message.author.id]
            user_answer = message.content.lower().strip()
            
            if user_answer == riddle_data['answer'] or user_answer in riddle_data['answer']:
                del self.active_riddles[message.author.id]
                self.relationship_manager.record_interaction(user_id, 'riddle_correct')
                
                cookies = self.cookie_manager.try_award_cookies(user_id, 'riddle_correct', self.personality_engine.get_mood())
                response = "🎉 You got it! Well done!"
                if cookies:
                    response += f"\n{self.personality_engine.get_cookie_reward_message(cookies, message.author.display_name, str(message.author.id))}"
                
                await message.channel.send(response)
                return
        
        # Check for bot mention
        if self.bot.user and self.bot.user.mentioned_in(message) and not message.mention_everyone:
            self.relationship_manager.record_interaction(user_id, 'mention')
            
            # Random mood shift
            self.personality_engine.random_mood_shift()
            
            # Generate response
            greeting = self.personality_engine.greeting(message.author.display_name, str(message.author.id))
            await message.channel.send(f"{greeting} Use `/easteregg` for a surprise!")
            
            # Try cookie reward
            cookies = self.cookie_manager.try_award_cookies(user_id, 'mention', self.personality_engine.get_mood())
            if cookies:
                reward_msg = self.personality_engine.get_cookie_reward_message(cookies, message.author.display_name, str(message.author.id))
                await message.channel.send(reward_msg)


async def setup(bot: commands.Bot) -> None:
    """Setup function called by Discord.py."""
    # Note: Dependencies will be injected by IntegrationLoader
    pass


