# Personality engine stub for FunBot
class PersonalityEngine:
    def __init__(self):
        # No initialization required for stub
        pass

    def get_personality_prompt(self, persona: str) -> str:
        """Return a prompt string for the given persona."""
        return f"[Personality: {persona}]"
