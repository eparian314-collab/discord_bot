from __future__ import annotations

import json
import unicodedata
from difflib import get_close_matches
from pathlib import Path
from typing import Dict, Iterable, Optional


def _strip_accents(s: str) -> str:
    nfkd = unicodedata.normalize("NFKD", s)
    return "".join(ch for ch in nfkd if not unicodedata.combining(ch))


def _norm_token(token: str) -> str:
    t = (token or "").strip().lower().replace("_", "-")
    t = _strip_accents(t)
    t = t.replace(".", "").replace(",", "").replace("(", "").replace(")", "")
    t = " ".join(t.split())
    return t


def _normalize_code(code: str) -> str:
    """
    Normalize a language code to its base (lowercase) form.
    Examples: "EN-US" -> "en", "pt-BR" -> "pt", "zh" -> "zh"
    """
    if not code:
        return ""
    c = str(code).strip().lower()
    if "-" in c:
        return c.split("-", 1)[0]
    return c


class LanguageAliasHelper:
    """
    Advanced alias resolver (no external APIs).

    Responsibilities:
    - Resolve ISO codes, localized names, exonyms, and common variants.
    - Fuzzy match near-misses when exact lookup fails.
    - Support optional loading of additional alias maps from a JSON-style dict or file.

    Usage:
      helper = LanguageAliasHelper()
      helper.resolve("english") -> "en"
      helper.add_alias("pt", ["portuguese (brazil)"])
      helper.load_from_language_map(Path("language_map.json"))  # optional
    """

    def __init__(
        self,
        *,
        base_map: Optional[Dict[str, Dict[str, Iterable[str]]]] = None,
        extra_aliases: Optional[Dict[str, Iterable[str]]] = None,
        fuzzy_threshold: float = 0.86,
    ) -> None:
        self.fuzzy_threshold = float(fuzzy_threshold)
        # code_to_aliases keys are normalized base codes (e.g., "en", "pt")
        self.code_to_aliases: Dict[str, set[str]] = {}
        # alias_to_code maps normalized alias -> normalized base code
        self.alias_to_code: Dict[str, str] = {}

        # Seed base map (use provided or default)
        seed = base_map or self._default_map()
        for code, info in seed.items():
            norm_code = _normalize_code(code)
            bucket: set[str] = set()

            # Add canonical name if present
            name = info.get("name") if isinstance(info, dict) else None
            if name:
                bucket.add(_norm_token(name))

            # Add configured aliases
            for alias in info.get("aliases", []) if isinstance(info, dict) else []:
                bucket.add(_norm_token(alias))

            # Add the code token itself normalized and a common region variant
            bucket.add(_norm_token(norm_code))
            if "-" not in str(code):
                bucket.add(_norm_token(f"{norm_code}-{norm_code}"))

            # Store under normalized code
            self.code_to_aliases[norm_code] = bucket

        # Extra aliases from caller (mapping: code -> iterable of alias strings)
        if extra_aliases:
            for code, aliases in extra_aliases.items():
                norm_code = _normalize_code(code)
                if not norm_code:
                    continue
                self.code_to_aliases.setdefault(norm_code, set()).update(_norm_token(a) for a in aliases if isinstance(a, str))

        # Build reverse map alias -> normalized code; first seen wins
        for code, aliases in self.code_to_aliases.items():
            for a in aliases:
                if a and a not in self.alias_to_code:
                    self.alias_to_code[a] = code

    # --- Convenience loaders / mutators ------------------------------------------------

    def add_alias(self, code: str, alias: str) -> None:
        """
        Add a single alias for a language code at runtime.
        """
        if not alias:
            return
        norm_code = _normalize_code(code)
        if not norm_code:
            return
        norm_alias = _norm_token(alias)
        self.code_to_aliases.setdefault(norm_code, set()).add(norm_alias)
        # Only set reverse mapping if not present to preserve first-wins
        self.alias_to_code.setdefault(norm_alias, norm_code)

    def add_aliases(self, code: str, aliases: Iterable[str]) -> None:
        for a in aliases:
            if isinstance(a, str):
                self.add_alias(code, a)

    def load_from_language_map(self, path_or_dict: Optional[object]) -> None:
        """
        Load additional aliases from either:
          - a Path / str pointing to a JSON file with a "language_aliases" mapping, or
          - a dict-like object containing "language_aliases".

        The JSON structure expected (language_aliases): { "alias_token": "CanonicalName", ... }
        CanonicalName will be mapped to existing codes when possible.
        """
        mapping: Dict[str, str] = {}
        try:
            if isinstance(path_or_dict, (str, Path)):
                p = Path(path_or_dict)
                if not p.exists():
                    return
                with p.open("r", encoding="utf-8") as fh:
                    data = json.load(fh)
            elif isinstance(path_or_dict, dict):
                data = path_or_dict
            else:
                return

            mapping = data.get("language_aliases", {}) if isinstance(data, dict) else {}
            if not isinstance(mapping, dict):
                return

            # The mapping is alias -> CanonicalName (e.g., "en": "English")
            for alias_token, canonical_name in mapping.items():
                if not isinstance(alias_token, str) or not isinstance(canonical_name, str):
                    continue
                norm_alias = _norm_token(alias_token)
                # Try to map canonical_name to a known code
                # First check name matches any existing code_to_aliases name entries
                found_code = None
                cn_norm = _norm_token(canonical_name)
                for code, aliases in self.code_to_aliases.items():
                    if cn_norm in aliases:
                        found_code = code
                        break
                # If not found, maybe canonical_name is itself a code
                if not found_code:
                    potential_code = _normalize_code(canonical_name)
                    if potential_code in self.code_to_aliases:
                        found_code = potential_code

                # If still not found, create a new code entry using normalized canonical name as key
                if not found_code:
                    new_code = _normalize_token_to_code(canonical_name)
                    if new_code:
                        found_code = new_code
                        self.code_to_aliases.setdefault(found_code, set()).add(cn_norm)

                if found_code:
                    self.code_to_aliases.setdefault(found_code, set()).add(norm_alias)
                    self.alias_to_code.setdefault(norm_alias, found_code)
        except Exception:
            # Best-effort loader - ignore errors to avoid breaking runtime.
            return

    # --- Resolution API ---------------------------------------------------------------

    def resolve(self, token: str) -> Optional[str]:
        """
        Resolve an alias or token to a normalized base language code (e.g., "en", "pt", "zh").
        Returns None when token is empty or no reasonable match is found.
        """
        key = _norm_token(token)
        if not key:
            return None

        # Fast direct alias match
        if key in self.alias_to_code:
            return self.alias_to_code[key]

        # Try hyphen/space variants: "pt-br" <-> "pt br"
        if "-" in key:
            alt = key.replace("-", " ")
            if alt in self.alias_to_code:
                return self.alias_to_code[alt]
        else:
            alt = key.replace(" ", "-")
            if alt in self.alias_to_code:
                return self.alias_to_code[alt]

        # Fuzzy match on known aliases
        aliases = list(self.alias_to_code.keys())
        for candidate in get_close_matches(key, aliases, n=3, cutoff=self.fuzzy_threshold):
            code = self.alias_to_code.get(candidate)
            if code:
                return code

        # Fuzzy search on language codes (typos like "js" -> "ja")
        codes = list(self.code_to_aliases.keys())
        for candidate in get_close_matches(key, codes, n=1, cutoff=self.fuzzy_threshold):
            return _normalize_code(candidate)

        # If the token itself looks like a code (e.g., "en-US", "pt_BR"), return normalized base
        if "/" not in key:
            code_candidate = key.replace("_", "-")
            if "-" in code_candidate:
                code_candidate = code_candidate.split("-", 1)[0]
            if code_candidate and code_candidate in self.code_to_aliases:
                return code_candidate
            # Accept two-letter or valid-looking codes as-is
            if len(code_candidate) in (2, 3) and code_candidate.isalpha():
                return _normalize_code(code_candidate)

        return None

    def get_all_codes(self) -> Iterable[str]:
        """Return all normalized language codes known to this helper."""
        return tuple(self.code_to_aliases.keys())

    # --- Default map -----------------------------------------------------------------

    @staticmethod
    def _default_map() -> Dict[str, Dict[str, Iterable[str]]]:
        # Minimal but broad set of languages with common exonyms/endonyms/variants.
        return {
            "en": {
                "name": "English",
                "aliases": [
                    "eng",
                    "en-us",
                    "en-uk",
                    "us english",
                    "uk english",
                    "american english",
                    "british english",
                ],
            },
            "es": {
                "name": "Spanish",
                "aliases": [
                    "español",
                    "castellano",
                    "es-es",
                    "latam spanish",
                    "mexican spanish",
                    "span",
                ],
            },
            "pt": {
                "name": "Portuguese",
                "aliases": ["português", "portugues", "pt-br", "pt-pt", "brazilian portuguese", "portuguese (brazil)"],
            },
            "fr": {
                "name": "French",
                "aliases": ["français", "francais", "fr-fr", "canadian french", "fr-ca"],
            },
            "de": {
                "name": "German",
                "aliases": ["deutsch", "hochdeutsch", "de-de"],
            },
            "it": {
                "name": "Italian",
                "aliases": ["italiano", "it-it"],
            },
            "ja": {
                "name": "Japanese",
                "aliases": ["nihongo", "日本語", "ja-jp"],
            },
            "zh": {
                "name": "Chinese",
                "aliases": [
                    "中文",
                    "汉语",
                    "漢語",
                    "zh-cn",
                    "zh-tw",
                    "chinese simplified",
                    "chinese traditional",
                    "mandarin",
                ],
            },
            "ko": {
                "name": "Korean",
                "aliases": ["한국어", "조선말", "ko-kr"],
            },
            "ru": {
                "name": "Russian",
                "aliases": ["русский", "ru-ru"],
            },
            "uk": {
                "name": "Ukrainian",
                "aliases": ["українська", "uk-ua"],
            },
            "pl": {
                "name": "Polish",
                "aliases": ["polski", "pl-pl"],
            },
            "tr": {
                "name": "Turkish",
                "aliases": ["türkçe", "tr-tr", "turkce"],
            },
            "nl": {
                "name": "Dutch",
                "aliases": ["nederlands", "nl-nl", "vlaams", "flemish"],
            },
            "sv": {
                "name": "Swedish",
                "aliases": ["svenska", "sv-se"],
            },
            "no": {
                "name": "Norwegian",
                "aliases": ["norsk", "bokmål", "nynorsk", "nb-no", "nn-no"],
            },
            "da": {
                "name": "Danish",
                "aliases": ["dansk", "da-dk"],
            },
            "fi": {
                "name": "Finnish",
                "aliases": ["suomi", "fi-fi"],
            },
            "cs": {
                "name": "Czech",
                "aliases": ["čeština", "cestina", "cs-cz"],
            },
            "sk": {
                "name": "Slovak",
                "aliases": ["slovenčina", "slovencina", "sk-sk"],
            },
            "sl": {
                "name": "Slovenian",
                "aliases": ["slovenščina", "slovenscina", "sl-si"],
            },
            "hr": {
                "name": "Croatian",
                "aliases": ["hrvatski", "hr-hr"],
            },
            "ro": {
                "name": "Romanian",
                "aliases": ["română", "romana", "ro-ro"],
            },
            "bg": {
                "name": "Bulgarian",
                "aliases": ["български", "bg-bg"],
            },
            "el": {
                "name": "Greek",
                "aliases": ["ελληνικά", "ellinika", "el-gr"],
            },
            "he": {
                "name": "Hebrew",
                "aliases": ["עברית", "he-il", "ivrit"],
            },
            "ar": {
                "name": "Arabic",
                "aliases": ["العربية", "ar-sa", "ar-eg", "msa"],
            },
            "hi": {
                "name": "Hindi",
                "aliases": ["हिन्दी", "hindi", "hi-in"],
            },
            "th": {
                "name": "Thai",
                "aliases": ["ไทย", "th-th"],
            },
            "vi": {
                "name": "Vietnamese",
                "aliases": ["tiếng việt", "tieng viet", "vi-vn"],
            },
            "id": {
                "name": "Indonesian",
                "aliases": ["bahasa indonesia", "id-id"],
            },
        }


# --- Helper not exported: convert a canonical name into a plausible code key
def _normalize_token_to_code(token: Optional[str]) -> Optional[str]:
    if not token or not isinstance(token, str):
        return None
    # Prefer ascii letters-only base up to three chars
    k = _norm_token(token)
    # if token appears to already be a code-like form, normalize it
    if len(k) in (2, 3) and k.isalpha():
        return _normalize_code(k)
    # otherwise try first word as code
    parts = k.split()
    if parts and len(parts[0]) <= 3 and parts[0].isalpha():
        return _normalize_code(parts[0])
    # fallback: None (don't invent codes aggressively)
    return None

