from language_bot.language_context.localization.profile import LanguageProfile


def test_language_profile_defaults_and_fields():
    profile = LanguageProfile(
        name="English",
        locale_code="en-US",
        default_prompts={"greeting": "Hello"},
        fallbacks=("en", "en-GB"),
    )
    assert profile.name == "English"
    assert profile.locale_code == "en-US"
    assert profile.default_prompts["greeting"] == "Hello"
    assert profile.fallbacks == ("en", "en-GB")
