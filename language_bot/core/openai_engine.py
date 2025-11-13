# OpenAI Engine for LanguageBot
import openai
import os


class OpenAIEngine:
    def __init__(self, api_key=None, model=None):
        self.api_key = api_key or os.getenv("OPEN_AI_API_KEY")
        self.model = model or os.getenv("OPENAI_TRANSLATION_MODEL", "gpt-4o-mini")
        openai.api_key = self.api_key

    async def chat_completion(self, messages, temperature=0.7):
        # This is a synchronous call; for production use, wrap with run_in_executor or use an async library
        response = openai.ChatCompletion.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
        )
        return response["choices"][0]["message"]["content"].strip()

    def personality_response(self, persona, user_message):
        system_prompt = f"You are a Discord bot with a {persona} personality. Respond to the user in character."
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]
        return self.chat_completion(messages)
