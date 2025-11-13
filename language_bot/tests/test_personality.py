from language_bot.core.personality_engine import PersonalityEngine
from language_bot.core.personality_prompts import PERSONALITY_PROMPTS


def test_personality_engine_returns_prompt():
    engine = PersonalityEngine()
    assert engine.get_personality_prompt("friendly") == "[Personality: friendly]"


def test_personality_prompts_catalog():
    assert PERSONALITY_PROMPTS["friendly"].startswith("You are")
