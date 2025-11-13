from language_bot.language_context.context.policies import PolicyRepository, TranslationPolicy


def test_translation_policy_blocks_languages():
    policy = TranslationPolicy(blocked_languages=("fr", "de-DE"))
    assert policy.allows_language("en")
    assert not policy.allows_language("FR")
    assert not policy.allows_language("de")


def test_policy_repository_resolution_order():
    repo = PolicyRepository()
    root_policy = TranslationPolicy(fallback_language="en")
    channel_policy = TranslationPolicy(fallback_language="es")
    user_policy = TranslationPolicy(fallback_language="fr")

    repo.set_policy(guild_id=1, policy=root_policy)
    repo.set_policy(guild_id=1, channel_id=2, policy=channel_policy)
    repo.set_policy(guild_id=1, channel_id=2, user_id=3, policy=user_policy)

    assert repo.get_policy(guild_id=1, channel_id=2, user_id=3).fallback_language == "fr"
    assert repo.get_policy(guild_id=1, channel_id=2, user_id=None).fallback_language == "es"
    assert repo.get_policy(guild_id=1, channel_id=5, user_id=None).fallback_language == "en"
    assert repo.get_policy(guild_id=9).fallback_language == "en"


def test_policy_repository_remove_and_list():
    repo = PolicyRepository()
    policy = TranslationPolicy(fallback_language="de")
    repo.set_policy(guild_id=1, policy=policy)
    assert repo.list_policies()
    repo.remove_policy(guild_id=1)
    assert repo.list_policies() == {}


def test_policy_repository_bulk_load():
    repo = PolicyRepository()
    policies = [
        (1, None, None, TranslationPolicy(fallback_language="es")),
        (2, 3, None, TranslationPolicy(fallback_language="fr")),
    ]
    repo.load_bulk(policies)
    assert repo.get_policy(guild_id=1).fallback_language == "es"
    assert repo.get_policy(guild_id=2, channel_id=3).fallback_language == "fr"
