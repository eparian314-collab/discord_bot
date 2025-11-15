from __future__ import annotations

from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from fun_bot.core.personality_engine import PersonalityEngine


def test_personality_engine_uses_classic_fallback() -> None:
    engine = PersonalityEngine(persona="nonexistent")
    result = engine.format("cookies_balance", amount=5)
    assert "5" in result


def test_personality_engine_formats_known_key() -> None:
    engine = PersonalityEngine(persona="classic")
    text = engine.format("pokemon_catch", name="Pikachu", total=3)
    assert "Pikachu" in text
    assert "3" in text


def test_personality_engine_gracefully_handles_bad_kwargs() -> None:
    engine = PersonalityEngine(persona="classic")
    # Missing kwargs should not raise; we fall back to the raw template.
    text = engine.format("pokemon_catch")
    assert isinstance(text, str)
