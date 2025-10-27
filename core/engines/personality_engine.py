from __future__ import annotations

import os
import random
from typing import Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from openai import AsyncOpenAI


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
                "Hey {user}! You've already gotten all your cookies for today (5/5)! 🍪✨ Come back tomorrow for more fun! 🦛💖",
                "Aww {user}, you've reached your daily cookie limit! 🍪 Save some for tomorrow! 😊",
            ],
            2: [
                "{user}, I already told you - no more cookies today! 🙅‍♀️ Please don't keep asking! 🦛",
                "C'mon {user}, you know the rules! 5 cookies max per day! Stop trying! 😅",
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
                "{user}, you've reached your daily limit of 5 cookies. Try again tomorrow. 🍪",
                "Daily cookie limit reached, {user}. Come back tomorrow for more. 🦛",
            ],
            2: [
                "{user}, I already said no more cookies today. Please stop asking.",
                "Stop spamming, {user}. You've had your 5 cookies. That's it.",
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
                "Ugh, {user}... You already got your 5 cookies. Go away. 😒",
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

    def __init__(self, *, cache_manager, ai_adapter: Optional[Any] = None) -> None:
        self.cache = cache_manager
        self.ai_adapter = ai_adapter
        self.current_mood = 'neutral'
        self._openai_client: Optional[AsyncOpenAI] = None
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

    def set_mood(self, mood: str) -> None:
        """Set the bot's current mood (happy, neutral, grumpy)."""
        if mood in ('happy', 'neutral', 'grumpy'):
            self.current_mood = mood

    def get_mood(self) -> str:
        """Get the bot's current mood."""
        return self.current_mood
    
    def random_mood_shift(self) -> str:
        """
        Randomly shift mood (small chance).
        Call this periodically to keep things interesting.
        """
        roll = random.random()
        if roll < 0.05:  # 5% chance to become grumpy
            self.current_mood = 'grumpy'
        elif roll < 0.10:  # 5% chance to become happy
            self.current_mood = 'happy'
        elif roll < 0.20:  # 10% chance to return to neutral
            self.current_mood = 'neutral'
        # 80% chance to stay the same
        return self.current_mood

    def set_ai_adapter(self, adapter: Optional[Any]) -> None:
        """Inject or replace the AI adapter used for personality embellishments."""
        self.ai_adapter = adapter

    def greeting(self, user_name: str) -> str:
        """Get a greeting based on current mood."""
        templates = self.GREETINGS[self.current_mood]
        return random.choice(templates).format(user=user_name)

    def confirmation(self, text: str) -> str:
        """Get a confirmation message based on current mood."""
        templates = self.CONFIRMATIONS[self.current_mood]
        template = random.choice(templates)
        return template.format(text=text) if '{text}' in template else f"{template} {text}"

    def error(self) -> str:
        """Get an error message based on current mood."""
        templates = self.ERRORS[self.current_mood]
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
        
        system_prompt = f"{mood_personalities[self.current_mood]} {relationship_context} Keep responses under 200 characters."
        
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
    
    def get_cookie_reward_message(self, amount: int, user_name: str) -> str:
        """Get a message for cookie rewards based on mood."""
        messages = {
            'happy': [
                f"🍪✨ Here's {amount} cookies for you, {user_name}! You're amazing! 🦛💖",
                f"🍪 Yay! {amount} cookies coming your way! Keep being awesome! 🎉",
                f"🍪 {amount} fresh cookies just for you, {user_name}! 🌟"
            ],
            'neutral': [
                f"🍪 You earned {amount} cookies, {user_name}!",
                f"🍪 Nice! Here's {amount} cookies for you.",
                f"🍪 {amount} cookies added to your collection!"
            ],
            'grumpy': [
                f"🍪 Fine, take {amount} cookies... 😒",
                f"🍪 Here, {amount} cookies. Don't spend them all at once...",
                f"🍪 *grumbles* {amount} cookies for {user_name}..."
            ]
        }
        return random.choice(messages[self.current_mood])
    
    def get_easter_egg_limit_message(self, user_name: str, aggravation_level: int) -> str:
        """Get a message when user hits easter egg limit based on mood and aggravation."""
        # Cap aggravation at 4 for message selection
        level = min(aggravation_level, 4)
        
        # If aggravation is 0, use level 1 messages
        if level == 0:
            level = 1
        
        messages = self.EASTER_EGG_LIMIT_MESSAGES[self.current_mood][level]
        return random.choice(messages).format(user=user_name)
    
    def get_cookie_penalty_message(self, user_name: str, amount: int) -> str:
        """Get a message when cookies are taken as penalty."""
        messages = self.COOKIE_PENALTY_MESSAGES[self.current_mood]
        return random.choice(messages).format(user=user_name, amount=amount)
    
    def get_mute_warning_message(self, user_name: str, chance: float) -> str:
        """Get a warning message about mute chance."""
        messages = self.MUTE_WARNING_MESSAGES[self.current_mood]
        return random.choice(messages).format(user=user_name, chance=chance)
