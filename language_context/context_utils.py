from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

# Existing helpers kept as-is
def normalize_lang_code(code: Optional[str]) -> str:
    """
    Normalize a language token into canonical 2�3 letter lowercase code.
    Examples:
        "EN-US" -> "en"
        " pt_br " -> "pt"
        "fr_FR" -> "fr"
        "ES" -> "es"
    """
    if not code:
        return "en"

    c = code.strip().lower().replace("_", "-")
    if "-" in c:
        c = c.split("-", 1)[0]
    return c


def is_same_language(a: Optional[str], b: Optional[str]) -> bool:
    """
    Returns True if two language codes represent the same canonical language.
    """
    if not a or not b:
        return False
    return normalize_lang_code(a) == normalize_lang_code(b)


def detect_script(text: str) -> str:
    """
    Detect primary script family to guess a likely language core.
    Lightweight, non-NLP, zero-API heuristic.
    """

    t = text or ""
    for ch in t:
        o = ord(ch)

        # Japanese Hiragana/Katakana
        if 0x3040 <= o <= 0x30FF:
            return "ja"

        # Chinese Han
        if 0x4E00 <= o <= 0x9FFF:
            return "zh"

        # Korean Hangul
        if 0xAC00 <= o <= 0xD7AF:
            return "ko"

        # Cyrillic
        if 0x0400 <= o <= 0x04FF:
            return "ru"

        # Arabic
        if 0x0600 <= o <= 0x06FF:
            return "ar"

        # Hebrew
        if 0x0590 <= o <= 0x05FF:
            return "he"

        # Extended Latin found in Romance languages
        if 0x00C0 <= o <= 0x024F:
            return "es"

    # Default to English if uncertain
    return "en"


# --------------------
# New/additive helpers
# --------------------
_LANGUAGE_MAP_CACHE: Optional[Dict[str, Any]] = None


def load_language_map(path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """
    Load `language_map.json` from language_context directory by default.
    Caches result in module-level variable to avoid repeated disk I/O.
    """
    global _LANGUAGE_MAP_CACHE
    if _LANGUAGE_MAP_CACHE is not None:
        return _LANGUAGE_MAP_CACHE

    try:
        base = Path(__file__).parent
        p = Path(path) if path else base / "language_map.json"
        if not p.exists():
            return None
        with p.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        _LANGUAGE_MAP_CACHE = data
        return data
    except Exception:
        return None


def get_deepl_supported_codes(language_map: Optional[Dict[str, Any]] = None) -> set[str]:
    """
    Return a set of normalized deepl target codes (lowercase).
    Falls back to known hardcoded set if language_map not present.
    """
    lm = language_map or load_language_map()
    codes = set()
    try:
        deepl = lm.get("deepl_lang_codes", {}) if isinstance(lm, dict) else {}
        for name, code in deepl.items():
            if isinstance(code, str):
                codes.add(normalize_lang_code(code))
    except Exception:
        pass

    # Fallback: common DeepL cores (kept conservative)
    if not codes:
        fallback = {
            "bg", "cs", "da", "de", "el", "en", "es", "et", "fi", "fr", "hu", "id",
            "it", "ja", "ko", "lt", "lv", "nl", "pl", "pt", "ro", "ru", "sk", "sl",
            "sv", "tr", "uk", "zh"
        }
        codes = {normalize_lang_code(x) for x in fallback}
    return codes


def is_valid_lang_code(token: Optional[str], *, language_map: Optional[Dict[str, Any]] = None) -> bool:
    """
    Validate a language token:
      - Accepts two-letter codes (e.g., "en") or region variants ("en-US")
      - Accepts tokens that map via language_aliases in language_map.json
    """
    if not token:
        return False
    tok = token.strip()
    norm = normalize_lang_code(tok)
    # quick structural validation
    if len(norm) in (2, 3) and norm.isalpha():
        return True
    # check alias map
    lm = language_map or load_language_map()
    try:
        aliases = lm.get("language_aliases", {}) if isinstance(lm, dict) else {}
        if isinstance(aliases, dict) and tok.lower() in aliases:
            return True
    except Exception:
        pass
    return False


def is_supported_by_provider(provider: str, tgt_token: str, *, language_map: Optional[Dict[str, Any]] = None) -> bool:
    """
    Check whether a target language is supported by a provider.
    Provider names: 'deepl', 'mymemory', 'openai'
    - DeepL: checks explicit list from language_map.json or fallback set.
    - MyMemory/OpenAI: treated as broadly supporting (returns True) since they have wide coverage.
    """
    if not provider or not tgt_token:
        return False
    tgt = normalize_lang_code(tgt_token)
    p = (provider or "").strip().lower()
    if p == "deepl":
        codes = get_deepl_supported_codes(language_map)
        return tgt in codes
    # MyMemory and OpenAI are considered generic/fallback (broad support)
    if p in ("mymemory", "openai"):
        return True
    # Unknown provider: be conservative and return False
    return False


def map_alias_to_code(token: Optional[str], *, alias_helper: Optional[Any] = None, language_map: Optional[Dict[str, Any]] = None) -> Optional[str]:
    """
    Map a user-provided token (alias, name, code) to a normalized base code.
    Preference order:
      1) alias_helper.resolve(token) if provided
      2) language_map.language_aliases mapping
      3) structural normalization (normalize_lang_code)
    Returns normalized code (e.g., 'en') or None.
    """
    if not token:
        return None
    # 1) alias helper
    if alias_helper and hasattr(alias_helper, "resolve"):
        try:
            r = alias_helper.resolve(token)
            if isinstance(r, str) and r:
                return normalize_lang_code(r)
        except Exception:
            # swallow to fallback
            pass

    # 2) language_map alias
    lm = language_map or load_language_map()
    try:
        aliases = lm.get("language_aliases", {}) if isinstance(lm, dict) else {}
        if isinstance(aliases, dict):
            v = aliases.get(token.lower())
            if isinstance(v, str) and v:
                return normalize_lang_code(v)
    except Exception:
        pass

    # 3) structural fallback
    norm = normalize_lang_code(token)
    return norm if norm else None


def safe_truncate(text: Optional[str], max_chars: int = 4000) -> str:
    """
    Trim text to provider-friendly length without cutting mid-paragraph when possible.
    Adds an ellipsis marker when truncated.
    """
    if not text:
        return ""
    t = str(text)
    if len(t) <= max_chars:
        return t
    # prefer cut at last double-newline within limit
    cut = t.rfind("\n\n", 0, max_chars)
    if cut <= 0:
        cut = t.rfind("\n", 0, max_chars)
    if cut <= 0:
        cut = max_chars
    return t[:cut].rstrip() + "\n\n..."