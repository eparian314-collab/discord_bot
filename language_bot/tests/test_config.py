import pytest

from language_bot.config import LanguageBotConfig, _split_ints, _split_str


def test_split_ints_handles_mixed_delimiters_and_invalid():
    assert _split_ints("1, 2; 3,not-a-number,4 ") == {1, 2, 3, 4}


def test_split_str_respects_default_and_lowercases():
    assert _split_str("") == []
    assert _split_str("", default=["A", "b"]) == ["A", "b"]
    assert _split_str(" En , ES ,", default=["fallback"]) == ["en", "es"]


def test_from_env_parses_values(monkeypatch):
    env = {
        "DISCORD_TOKEN": "abc",
        "OWNER_IDS": "1,2",
        "TEST_GUILDS": "3;4",
        "DEEPL_API_KEY": "deepl",
        "MY_MEMORY_API_KEY": "mm",
        "MYMEMORY_USER_EMAIL": "me@example.com",
        "OPEN_AI_API_KEY": "openai",
        "OPENAI_TRANSLATION_MODEL": "gpt-lab",
        "TRANSLATION_PROVIDERS": "mymemory,deepl",
        "TRANSLATION_FALLBACK_LANGUAGE": "fr",
        "LANGUAGE_ROLE_PREFIX": "Lang-",
        "BOT_CHANNEL_ID": "42",
    }
    for key, value in env.items():
        monkeypatch.setenv(key, value)

    config = LanguageBotConfig.from_env()

    assert config.discord_token == "abc"
    assert config.owner_ids == {1, 2}
    assert config.test_guild_ids == {3, 4}
    assert config.deepl_api_key == "deepl"
    assert config.my_memory_api_key == "mm"
    assert config.my_memory_email == "me@example.com"
    assert config.openai_api_key == "openai"
    assert config.openai_model == "gpt-lab"
    assert config.provider_order == ["mymemory", "deepl"]
    assert config.default_fallback_language == "FR"
    assert config.language_role_prefix == "lang-"
    assert config.bot_channel_id == 42


def test_from_env_requires_token(monkeypatch):
    monkeypatch.delenv("DISCORD_TOKEN", raising=False)
    with pytest.raises(RuntimeError):
        LanguageBotConfig.from_env()


def test_bot_channel_id_defaults_to_none(monkeypatch):
    monkeypatch.setenv("DISCORD_TOKEN", "abc")
    monkeypatch.delenv("BOT_CHANNEL_ID", raising=False)
    config = LanguageBotConfig.from_env()
    assert config.bot_channel_id is None
