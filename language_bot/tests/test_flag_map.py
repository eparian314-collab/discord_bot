from language_bot.language_context.flag_map import LanguageDirectory, extract_flag_emojis


def test_flag_lookup_and_aliases():
    directory = LanguageDirectory.default()

    spec = directory.resolve_by_flag("\U0001F1F2\U0001F1FD")  # 🇲🇽
    assert spec is not None
    assert spec.iso_code == "es"
    assert "spanish" in spec.normalized_aliases()

    assert directory.resolve_by_fragment("EN") is not None
    assert directory.iso_from_fragment("Es") == "ES"


def test_specs_from_text_deduplicates_and_orders():
    directory = LanguageDirectory.default()
    specs = directory.specs_from_text("Flags: 🇲🇽 🇲🇽 🇯🇵 🇯🇵")
    assert [spec.iso_code for spec in specs] == ["es", "ja"]


def test_extract_flag_emojis_returns_unique_emojis():
    flags = extract_flag_emojis("Mix 🇺🇸 text 🇲🇽 and symbols")
    assert flags == ["🇺🇸", "🇲🇽"]
