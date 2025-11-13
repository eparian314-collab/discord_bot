"""Language metadata and flag emoji helpers."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Dict, List, Optional, Sequence, Tuple


_FLAG_REGEX = re.compile(r"([\U0001F1E6-\U0001F1FF]{2})")


@dataclass(frozen=True, slots=True)
class LanguageSpec:
    name: str
    iso_code: str
    default_role_slug: str
    aliases: Tuple[str, ...]
    flag_emojis: Tuple[str, ...]

    def normalized_aliases(self) -> Tuple[str, ...]:
        return tuple({alias.lower() for alias in (self.iso_code, self.default_role_slug, *self.aliases)})


class LanguageDirectory:
    """Lookup helper covering iso codes, aliases, and flag emojis."""

    def __init__(self, specs: Sequence[LanguageSpec]) -> None:
        self._by_iso: Dict[str, LanguageSpec] = {}
        self._by_alias: Dict[str, LanguageSpec] = {}
        self._by_flag: Dict[str, LanguageSpec] = {}

        for spec in specs:
            self._register_spec(spec)

    def _register_spec(self, spec: LanguageSpec) -> None:
        self._by_iso[spec.iso_code.lower()] = spec
        for alias in spec.normalized_aliases():
            self._by_alias[alias] = spec
        for flag in spec.flag_emojis:
            self._by_flag[flag] = spec

    @classmethod
    def default(cls) -> "LanguageDirectory":
        specs = [
            LanguageSpec("English", "en", "english", ("eng", "en-us", "en-gb"), ("🇺🇸", "🇬🇧", "🇦🇺", "🇨🇦", "🇳🇿", "🇮🇪")),
            LanguageSpec("Spanish", "es", "spanish", ("esp", "es-mx", "es-es"), ("🇲🇽", "🇪🇸", "🇨🇴", "🇦🇷", "🇵🇪", "🇨🇱", "🇻🇪", "🇬🇹", "🇺🇾", "🇵🇦", "🇧🇴", "🇨🇺")),
            LanguageSpec("Portuguese", "pt", "portuguese", ("pt-br", "pt-pt"), ("🇧🇷", "🇵🇹")),
            LanguageSpec("French", "fr", "french", ("fra",), ("🇫🇷", "🇧🇪", "🇨🇦", "🇨🇭", "🇱🇺", "🇲🇶", "🇸🇳")),
            LanguageSpec("German", "de", "german", ("ger", "deu"), ("🇩🇪", "🇦🇹", "🇨🇭", "🇱🇮")),
            LanguageSpec("Italian", "it", "italian", ("ita",), ("🇮🇹", "🇸🇲", "🇻🇦")),
            LanguageSpec("Dutch", "nl", "dutch", ("nld", "flemish"), ("🇳🇱", "🇧🇪", "🇸🇷")),
            LanguageSpec("Swedish", "sv", "swedish", ("swe",), ("🇸🇪", "🇫🇮")),
            LanguageSpec("Norwegian", "no", "norwegian", ("nob", "nno"), ("🇳🇴", "🇸🇯")),
            LanguageSpec("Danish", "da", "danish", ("dan",), ("🇩🇰", "🇬🇱")),
            LanguageSpec("Finnish", "fi", "finnish", ("fin",), ("🇫🇮",)),
            LanguageSpec("Polish", "pl", "polish", ("pol",), ("🇵🇱",)),
            LanguageSpec("Russian", "ru", "russian", ("rus",), ("🇷🇺", "🇧🇾", "🇰🇿")),
            LanguageSpec("Ukrainian", "uk", "ukrainian", ("ukr",), ("🇺🇦",)),
            LanguageSpec("Turkish", "tr", "turkish", ("tur",), ("🇹🇷", "🇨🇾")),
            LanguageSpec("Arabic", "ar", "arabic", ("ara", "arab"), ("🇸🇦", "🇦🇪", "🇶🇦", "🇧🇭", "🇴🇲", "🇰🇼", "🇯🇴", "🇪🇬", "🇲🇦", "🇹🇳", "🇱🇧", "🇩🇿")),
            LanguageSpec("Hebrew", "he", "hebrew", ("heb",), ("🇮🇱",)),
            LanguageSpec("Hindi", "hi", "hindi", ("hin",), ("🇮🇳",)),
            LanguageSpec("Bengali", "bn", "bengali", ("ben",), ("🇧🇩", "🇮🇳")),
            LanguageSpec("Urdu", "ur", "urdu", ("urd",), ("🇵🇰", "🇮🇳")),
            LanguageSpec("Persian", "fa", "persian", ("farsi", "prs"), ("🇮🇷", "🇦🇫")),
            LanguageSpec("Chinese (Simplified)", "zh", "chinese", ("zh-cn", "zh-hans", "mandarin"), ("🇨🇳", "🇸🇬")),
            LanguageSpec("Chinese (Traditional)", "zh-tw", "chinese-traditional", ("zh-hant", "taiwanese"), ("🇹🇼", "🇭🇰", "🇲🇴")),
            LanguageSpec("Japanese", "ja", "japanese", ("jpn",), ("🇯🇵",)),
            LanguageSpec("Korean", "ko", "korean", ("kor",), ("🇰🇷", "🇰🇵")),
            LanguageSpec("Vietnamese", "vi", "vietnamese", ("vie",), ("🇻🇳",)),
            LanguageSpec("Thai", "th", "thai", ("tha",), ("🇹🇭",)),
            LanguageSpec("Tagalog", "tl", "tagalog", ("filipino", "fil"), ("🇵🇭",)),
            LanguageSpec("Indonesian", "id", "indonesian", ("ind", "bahasa"), ("🇮🇩",)),
            LanguageSpec("Malay", "ms", "malay", ("msa",), ("🇲🇾", "🇧🇳")),
            LanguageSpec("Swahili", "sw", "swahili", ("swa",), ("🇰🇪", "🇹🇿", "🇺🇬")),
            LanguageSpec("Greek", "el", "greek", ("ell",), ("🇬🇷", "🇨🇾")),
            LanguageSpec("Czech", "cs", "czech", ("ces", "cze"), ("🇨🇿",)),
            LanguageSpec("Hungarian", "hu", "hungarian", ("hun",), ("🇭🇺",)),
            LanguageSpec("Romanian", "ro", "romanian", ("ron", "rum"), ("🇷🇴", "🇲🇩")),
            LanguageSpec("Bulgarian", "bg", "bulgarian", ("bul",), ("🇧🇬",)),
            LanguageSpec("Serbian", "sr", "serbian", ("srp",), ("🇷🇸", "🇲🇪", "🇧🇦")),
            LanguageSpec("Croatian", "hr", "croatian", ("hrv",), ("🇭🇷", "🇧🇦")),
            LanguageSpec("Slovak", "sk", "slovak", ("slk", "slo"), ("🇸🇰",)),
            LanguageSpec("Slovenian", "sl", "slovenian", ("slv",), ("🇸🇮",)),
            LanguageSpec("Lithuanian", "lt", "lithuanian", ("lit",), ("🇱🇹",)),
            LanguageSpec("Latvian", "lv", "latvian", ("lav",), ("🇱🇻",)),
            LanguageSpec("Estonian", "et", "estonian", ("est",), ("🇪🇪",)),
        ]
        return cls(specs)

    def resolve_by_flag(self, emoji: str) -> Optional[LanguageSpec]:
        return self._by_flag.get(emoji)

    def resolve_by_fragment(self, fragment: str) -> Optional[LanguageSpec]:
        normalized = fragment.strip().lower()
        return self._by_alias.get(normalized)

    def iso_from_fragment(self, fragment: str) -> Optional[str]:
        spec = self.resolve_by_fragment(fragment)
        return spec.iso_code.upper() if spec else None

    def specs_from_text(self, text: str) -> List[LanguageSpec]:
        matches = _FLAG_REGEX.findall(text or "")
        seen = set()
        specs: List[LanguageSpec] = []
        for emoji in matches:
            spec = self.resolve_by_flag(emoji)
            if spec and spec.iso_code not in seen:
                specs.append(spec)
                seen.add(spec.iso_code)
        return specs


def extract_flag_emojis(text: str) -> List[str]:
    return _FLAG_REGEX.findall(text or "")


__all__ = ["LanguageSpec", "LanguageDirectory", "extract_flag_emojis"]
