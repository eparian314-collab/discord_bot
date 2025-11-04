from __future__ import annotations

import os
import random
from datetime import datetime, timedelta
from typing import Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from openai import AsyncOpenAI
    from discord_bot.core.engines.relationship_manager import RelationshipManager


class PersonalityEngine:
    """
    Provides personality strings and micro-prompts for bot responses.
    Integrates with OpenAI for dynamic, mood-influenced responses.
    
    Mood system:
    - happy: Cheerful, generous, enthusiastic
    - neutral: Friendly, balanced, helpful
    - grumpy: Sarcastic, grouchy, but still helpful
    """

    # Static responses for fallback (when OpenAI is unavailable)
    GREETINGS = {
        'happy': [
            "Hello {user}! 🦛💖 I'm so excited to see you!",
            "Hey there {user}! 🌟 You always brighten my day!",
            "Welcome back {user}! 🎉 Ready for some fun?"
        ],
        'neutral': [
            "Hello {user}! 😊",
            "Hey {user}, how can I help?",
            "Hi {user}! What's up?"
        ],
        'grumpy': [
            "Oh, it's you again, {user}... 😒",
            "*yawns* What do you want, {user}?",
            "Fine, fine, hello {user}... 🙄"
        ]
    }

    BEST_FRIEND_GREETINGS = {
        'happy': [
            "Heyyyy {user}! \U0001f31f I saved a cozy spot just for you!",
            "{user}! You're here! Let's make today extra fun! \U0001f389",
            "Guess who I was hoping to see? You, {user}! \U0001f308"
        ],
        'neutral': [
            "Oh! {user}, glad you dropped by-I've got something brewing. \U00002615\ufe0f",
            "Nice timing, {user}. I was just thinking about you! \U0001f642",
            "Welcome back, {user}. I kept things warm for you. \U0001f506"
        ],
        'grumpy': [
            "Hmm... it's {user}. You get a rare smile today. Maybe. \U0001f60f",
            "{user}, I'm not saying I missed you... but here's a fresh cushion. \U0001f6cb\ufe0f",
            "If anyone gets a warm welcome today, it's you, {user}. Don't tell. \U0001f92b"
        ]
    }

    CONFIRMATIONS = {
        'happy': [
            "✅ Done! That was fun! 🎉",
            "✅ All set! You're the best! 💖",
            "✅ {text} Woohoo! 🦛"
        ],
        'neutral': [
            "✅ {text}",
            "✅ Done! {text}",
            "✅ Got it! {text}"
        ],
        'grumpy': [
            "✅ {text} ...happy now? 😒",
            "✅ Fine, {text}",
            "✅ {text} ...I guess..."
        ]
    }
    
    ERRORS = {
        'happy': [
            "⚠️ Oops! Something went wrong, but don't worry! We'll figure it out! 💪",
            "⚠️ Hmm, that didn't work... but hey, mistakes happen! Let's try again! 🌟"
        ],
        'neutral': [
            "⚠️ Something went wrong. Please try again.",
            "⚠️ Error occurred. Let's give that another shot."
        ],
        'grumpy': [
            "⚠️ Great, something broke. Of course it did. 🙄",
            "⚠️ Error. Not my fault. Try again. 😒"
        ]
    }
    
    # Easter egg limit messages (escalate with aggravation level)
    EASTER_EGG_LIMIT_MESSAGES = {
        'happy': {
            1: [
                "Hey {user}! You've already gotten all your cookies for today! 🍪✨ Come back tomorrow for more fun! 🦛💖",
                "Aww {user}, you've reached your today's cookie limit! 🍪 Save some for tomorrow! 😊",
            ],
            2: [
                "{user}, I already told you - no more cookies today! 🙅‍♀️ Please don't keep asking! 🦛",
                "C'mon {user}, you know the rules! No more cookies today! Stop trying! 😅",
            ],
            3: [
                "{user}! Stop bugging me! 😤 I said no more cookies today! You're pushing it...",
                "Seriously {user}? STOP! No more cookies! You're making me upset! 😠",
            ],
            4: [
                "ENOUGH {user}! 😡 One more time and I'm taking a cookie back!",
                "{user}, you're really testing my patience! STOP IT! 🛑",
            ]
        },
        'neutral': {
            1: [
                "{user}, you've reached your daily cookie limit. Try again tomorrow. 🍪",
                "Daily cookie limit reached, {user}. Come back tomorrow for more. 🦛",
            ],
            2: [
                "{user}, I already said no more cookies today. Please stop asking.",
                "Stop spamming, {user}. You've had your cookies. That's it.",
            ],
            3: [
                "{user}, this is getting annoying. Stop trying to bug me for more cookies. 😒",
                "Seriously {user}? Stop spamming me. No more cookies today!",
            ],
            4: [
                "{user}, STOP. One more attempt and there will be consequences. 🛑",
                "Last warning, {user}. Stop spamming or I'll take action!",
            ]
        },
        'grumpy': {
            1: [
                "Ugh, {user}... You already got your cookies. Go away. 😒",
                "*grumbles* {user}, stop bothering me. No more cookies today. 🙄",
            ],
            2: [
                "{user}, I'm NOT in the mood. Stop asking for cookies! 😤",
                "Are you DEAF, {user}?! I said NO MORE COOKIES! 😡",
            ],
            3: [
                "{user}, you're REALLY annoying me now! STOP IT! 🤬",
                "I'm THIS close to taking cookies away, {user}! STOP SPAMMING! 💢",
            ],
            4: [
                "THAT'S IT {user}! Keep it up and I'll mute you! 🚫",
                "ONE MORE TIME {user} and you're getting muted! I mean it! 😠",
            ]
        }
    }
    
    COOKIE_PENALTY_MESSAGES = {
        'happy': [
            "Okay {user}, that's enough! I'm taking back {amount} cookie! 🍪➖ Please stop now! 😢",
            "I warned you {user}! -{amount} cookie for spamming! 🦛💔",
        ],
        'neutral': [
            "Cookie penalty applied, {user}. -{amount} cookie for spamming. 🍪",
            "{user}, you lost {amount} cookie for continued spamming. Stop now.",
        ],
        'grumpy': [
            "HAH! I took {amount} cookie from you, {user}! That's what you get! 😒🍪",
            "Serve you right, {user}! -{amount} cookie! Maybe NOW you'll stop! 😤",
        ]
    }

    BEST_FRIEND_COOKIE_MESSAGES = {
        'happy': [
            "✨ Surprise treat time! {user_name}, enjoy these {amount} cookies with extra sprinkles! 🍪💖",
            "Woo! {amount} VIP cookies just for you, {user_name}! Don't tell the others~ 🤫🎉",
            "I packed {amount} cookies with the fluffiest frosting for you, {user_name}! 🍪🌟"
        ],
        'neutral': [
            "{user_name}, I set aside {amount} warm cookies for you. Hope they make you smile. 🍪🙂",
            "Special delivery: {amount} fresh cookies heading your way, {user_name}! 🍪🚀",
            "I saved the best batch for you, {user_name}. Enjoy these {amount} cookies! 🍪✨"
        ],
        'grumpy': [
            "Don't get used to it, {user_name}... but here's {amount} secretly delicious cookies. 🍪😑",
            "I guess you earned these {amount} cookies, {user_name}. Try not to brag. 🍪🙄",
            "Fine. {amount} cookies, just for you, {user_name}. They might be my best batch. Maybe. 🍪😏"
        ],
    }
    
    MUTE_WARNING_MESSAGES = {
        'happy': [
            "⚠️ {user}, you're at {chance:.0f}% chance of getting muted! Please stop! 🛑",
            "Please {user}, I don't want to mute you! Stop before it's too late! ({chance:.0f}% risk) 😰",
        ],
        'neutral': [
            "⚠️ Warning {user}: {chance:.0f}% chance of mute. Stop spamming.",
            "Mute risk: {chance:.0f}%, {user}. Final warning.",
        ],
        'grumpy': [
            "{user}, you've got a {chance:.0f}% chance of getting muted. Keep testing me. 😒",
            "Go ahead {user}, keep spamming. {chance:.0f}% mute chance and rising... 🙄",
        ]
    }

    POKEMON_CATCH_SUCCESS_MESSAGES = {
        'happy': [
            "🎉 {user}! {pokemon} jumped straight into your arms! Let's celebrate! 🥳",
            "🧸 Sparkles everywhere! {pokemon} chose you, {user}! 🌟",
            "🤌 Another cuddly friend for you, {user}! Welcome home, {pokemon}! 💖"
        ],
        'neutral': [
            "✅ Nice work, {user}. {pokemon} is now part of your team.",
            "🎯 Clean catch, {user}. {pokemon} is yours to train.",
            "📦 {pokemon} captured successfully, {user}. On to the next!"
        ],
        'grumpy': [
            "🙄 Fine, {user}. You caught {pokemon}. Try not to brag about it.",
            "😐 {pokemon} is yours, {user}. Guess luck was on your side this time.",
            "🧱 Tch, {pokemon} fell for it. Keep it together, {user}."
        ]
    }

    POKEMON_CATCH_FAIL_MESSAGES = {
        'happy': [
            "😢 So close, {user}! {pokemon} slipped away - let's try again soon! 💪",
            "💫 {pokemon} dashed off, {user}! We'll get them next time! ✨",
            "🦅 {pokemon} said 'not yet!' but I believe in you, {user}! 💗"
        ],
        'neutral': [
            "⚠️ {pokemon} escaped this time, {user}. Regroup and try again.",
            "📝 Catch failed. {pokemon} didn't stay in the ball for {user}.",
            "🔄 {user}, {pokemon} got away. Adjust strategy and retry."
        ],
        'grumpy': [
            "😞 {pokemon} bolted. Told you to hold the ball tighter, {user}.",
            "🤪 Welp, {pokemon} laughed and ran. Nice job, {user}.",
            "🤬 Figures. {pokemon} escaped. Maybe focus, {user}?"
        ]
    }

    BATTLE_VICTORY_MESSAGES = {
        'happy': [
            "🏆 {winner} absolutely dazzled the arena! {loser}, better luck next time! ✨",
            "⚡ Boom! {winner} outplayed {loser}! Let's throw a victory party! 🎉",
            "🔥 {winner} just served a legendary win! Don't feel bad, {loser}! 💜"
        ],
        'neutral': [
            "🏆 {winner} wins the match against {loser}.",
            "📣 Battle complete: {winner} defeated {loser}.",
            "✅ {winner} came out on top. Solid fight, {loser}."
        ],
        'grumpy': [
            "😒 {winner} steamrolled {loser}. Saw that coming.",
            "😏 {winner} wiped the floor with {loser}. Try again when you're ready.",
            "🧹 Sweep. {winner} over {loser}. Next."
        ]
    }

    MOOD_BASELINE = "happy"
    MOOD_RECOVERY_MINUTES = 30

    def __init__(self, *, cache_manager, ai_adapter: Optional[Any] = None) -> None:
        self.cache = cache_manager
        self.ai_adapter = ai_adapter
        self.current_mood = self.MOOD_BASELINE
        self._last_mood_change = datetime.utcnow()
        self._openai_client: Optional[AsyncOpenAI] = None
        self.relationship_manager: Optional["RelationshipManager"] = None
        self._initialize_openai()
    
    def _initialize_openai(self) -> None:
        """Initialize OpenAI client if API key is available."""
        api_key = os.getenv('OPENAI_API_KEY')
        if api_key:
            try:
                from openai import AsyncOpenAI
                self._openai_client = AsyncOpenAI(api_key=api_key)
            except ImportError:
                pass  # OpenAI not installed or import failed

    def set_relationship_manager(self, relationship_manager: "RelationshipManager") -> None:
        """Link the relationship manager for contextual messaging."""
        self.relationship_manager = relationship_manager

    def set_mood(self, mood: str) -> None:
        """Set the bot's current mood (happy, neutral, grumpy)."""
        if mood in ('happy', 'neutral', 'grumpy'):
            self.current_mood = mood
            self._last_mood_change = datetime.utcnow()

    def get_mood(self) -> str:
        """Get the bot's current mood."""
        self._maybe_recover_mood()
        return self.current_mood
    
    def random_mood_shift(self) -> str:
        """
        Randomly shift mood (small chance).
        Call this periodically to keep things interesting.
        """
        self._maybe_recover_mood()
        roll = random.random()
        if roll < 0.05:  # 5% chance to become grumpy
            self.current_mood = 'grumpy'
        elif roll < 0.10:  # 5% chance to become happy
            self.current_mood = 'happy'
        elif roll < 0.20:  # 10% chance to return to neutral
            self.current_mood = 'neutral'
        # 80% chance to stay the same
        self._last_mood_change = datetime.utcnow()
        return self.current_mood

    def _maybe_recover_mood(self) -> None:
        """Passively drift mood back toward a slightly happy baseline."""
        if self.current_mood == self.MOOD_BASELINE:
            return

        if datetime.utcnow() - self._last_mood_change >= timedelta(minutes=self.MOOD_RECOVERY_MINUTES):
            self.current_mood = self.MOOD_BASELINE
            self._last_mood_change = datetime.utcnow()

    def _current_mood(self) -> str:
        """Return the current mood after applying any recovery."""
        self._maybe_recover_mood()
        return self.current_mood

    def set_ai_adapter(self, adapter: Optional[Any]) -> None:
        """Inject or replace the AI adapter used for personality embellishments."""
        self.ai_adapter = adapter

    def greeting(self, user_name: str, user_id: Optional[str] = None) -> str:
        """Get a greeting based on current mood."""
        is_secret_favorite = False
        if user_id and self.relationship_manager:
            best_friend_id = self.relationship_manager.get_best_friend_of_day()
            if best_friend_id and str(best_friend_id) == str(user_id):
                is_secret_favorite = True

        current_mood = self._current_mood()
        if is_secret_favorite:
            templates = self.BEST_FRIEND_GREETINGS[current_mood]
        else:
            templates = self.GREETINGS[current_mood]
        return random.choice(templates).format(user=user_name)

    def confirmation(self, text: str) -> str:
        """Get a confirmation message based on current mood."""
        templates = self.CONFIRMATIONS[self._current_mood()]
        template = random.choice(templates)
        return template.format(text=text) if '{text}' in template else f"{template} {text}"

    def error(self) -> str:
        """Get an error message based on current mood."""
        templates = self.ERRORS[self._current_mood()]
        return random.choice(templates)
    
    async def generate_dynamic_response(self, context: str, user_name: str,
                                       relationship_level: int = 50) -> Optional[str]:
        """
        Generate a dynamic response using OpenAI based on context, mood, and relationship.
        Returns None if OpenAI is unavailable.
        """
        if not self._openai_client:
            return None
        
        # Build personality prompt based on mood and relationship
        mood = self._current_mood()
        mood_personalities = {
            'happy': "You are Baby Hippo, a cheerful and enthusiastic bot! You love helping users and get excited about everything. Use emojis liberally! 🦛💖",
            'neutral': "You are Baby Hippo, a friendly and helpful bot. You're balanced and professional but still warm and approachable. 🦛😊",
            'grumpy': "You are Baby Hippo, but you're in a grumpy mood today. You're still helpful but sarcastic and a bit grouchy. Use subtle sass. 🦛😒"
        }
        
        relationship_context = ""
        if relationship_level >= 75:
            relationship_context = f"You and {user_name} are close friends. Be extra warm and personal."
        elif relationship_level >= 50:
            relationship_context = f"You and {user_name} are good friends."
        elif relationship_level < 25:
            relationship_context = f"You're just getting to know {user_name}. Be friendly but not too familiar."
        
        system_prompt = f"{mood_personalities[mood]} {relationship_context} Keep responses under 200 characters."
        
        try:
            response = await self._openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": context}
                ],
                max_tokens=60,
                temperature=0.9
            )
            return response.choices[0].message.content.strip()
        except Exception:
            return None  # Fallback to static responses
    
    def get_cookie_reward_message(
        self,
        amount: int,
        user_name: str,
        user_id: Optional[str] = None
    ) -> str:
        """Get a message for cookie rewards based on mood."""
        is_secret_favorite = False
        if user_id and self.relationship_manager:
            best_friend_id = self.relationship_manager.get_best_friend_of_day()
            if best_friend_id and str(best_friend_id) == str(user_id):
                is_secret_favorite = True

        mood = self._current_mood()

        if is_secret_favorite:
            templates = self.BEST_FRIEND_COOKIE_MESSAGES[mood]
            return random.choice(templates).format(amount=amount, user_name=user_name)

        messages = {
            'happy': [
                "🍪✨ Here's {amount} cookies for you, {user_name}! You're amazing! 🦛💖",
                "🍪 Yay! {amount} cookies coming your way! Keep being awesome! 🎉",
                "🍪 {amount} fresh cookies just for you, {user_name}! 🌟"
            ],
            'neutral': [
                "🍪 You earned {amount} cookies, {user_name}!",
                "🍪 Nice! Here's {amount} cookies for you.",
                "🍪 {amount} cookies added to your collection!"
            ],
            'grumpy': [
                "🍪 Fine, take {amount} cookies... 😒",
                "🍪 Here, {amount} cookies. Don't spend them all at once...",
                "🍪 *grumbles* {amount} cookies for {user_name}..."
            ]
        }
        return random.choice(messages[mood]).format(amount=amount, user_name=user_name)
    
    def get_easter_egg_limit_message(self, user_name: str, aggravation_level: int) -> str:
        """Get a message when user hits easter egg limit based on mood and aggravation."""
        # Cap aggravation at 4 for message selection
        level = min(aggravation_level, 4)
        
        # If aggravation is 0, use level 1 messages
        if level == 0:
            level = 1
        
        messages = self.EASTER_EGG_LIMIT_MESSAGES[self._current_mood()][level]
        return random.choice(messages).format(user=user_name)
    
    def get_cookie_penalty_message(self, user_name: str, amount: int) -> str:
        """Get a message when cookies are taken as penalty."""
        messages = self.COOKIE_PENALTY_MESSAGES[self._current_mood()]
        return random.choice(messages).format(user=user_name, amount=amount)
    
    def get_mute_warning_message(self, user_name: str, chance: float) -> str:
        """Get a warning message about mute chance."""
        messages = self.MUTE_WARNING_MESSAGES[self._current_mood()]
        return random.choice(messages).format(user=user_name, chance=chance)

    def get_pokemon_catch_success(self, user_name: str, pokemon_name: str) -> str:
        """Return a celebratory catch message adjusted for the current mood."""
        messages = self.POKEMON_CATCH_SUCCESS_MESSAGES[self._current_mood()]
        return random.choice(messages).format(user=user_name, pokemon=pokemon_name)

    def get_pokemon_catch_fail(self, user_name: str, pokemon_name: str) -> str:
        """Return a supportive (or grumpy) miss message adjusted for the current mood."""
        messages = self.POKEMON_CATCH_FAIL_MESSAGES[self._current_mood()]
        return random.choice(messages).format(user=user_name, pokemon=pokemon_name)

    def get_battle_victory(self, winner_name: str, loser_name: str) -> str:
        """Return a battle victory message with personality flair."""
        messages = self.BATTLE_VICTORY_MESSAGES[self._current_mood()]
        return random.choice(messages).format(winner=winner_name, loser=loser_name)


