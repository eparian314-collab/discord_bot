from __future__ import annotations

import json
import unicodedata
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


def _is_flag_emoji(s: str) -> bool:
    if not s or len(s) < 2:
        return False
    return all(0x1F1E6 <= ord(ch) <= 0x1F1FF for ch in s if not unicodedata.combining(ch))


def _flag_to_country(flag: str) -> Optional[str]:
    if not _is_flag_emoji(flag):
        return None
    code_points = [ord(ch) - 0x1F1E6 for ch in flag if 0x1F1E6 <= ord(ch) <= 0x1F1FF]
    if len(code_points) < 2:
        return None
    letters = "".join(chr(0x41 + cp) for cp in code_points[:2])
    return letters.upper()


# Base country→language candidates (order indicates preference)
# This remains as a fallback; more authoritative mappings may be loaded from language_map.json.
_COUNTRY_LANGS: Dict[str, List[str]] = {
    # English variants; we normalize to 'en'
    "US": ["en"],
    "GB": ["en"],
    "AU": ["en"],
    "NZ": ["en"],
    "CA": ["en", "fr"],  # bilingual country; prefer 'en' without further context
    "IE": ["en", "ga"],  # Irish Gaelic second
    # Spanish world
    "ES": ["es"],
    "MX": ["es"],
    "AR": ["es"],
    "CL": ["es"],
    "CO": ["es"],
    "PE": ["es"],
    "VE": ["es"],
    "EC": ["es"],
    "UY": ["es"],
    "PY": ["es"],
    "BO": ["es"],
    "DO": ["es"],
    "GT": ["es"],
    "HN": ["es"],
    "NI": ["es"],
    "SV": ["es"],
    "CR": ["es"],
    "PA": ["es"],
    "PR": ["es"],
    # Portuguese
    "PT": ["pt"],
    "BR": ["pt"],
    # French
    "FR": ["fr"],
    "BE": ["fr", "nl", "de"],
    "CH": ["de", "fr", "it", "rm"],
    "LU": ["lb", "fr", "de"],
    "MC": ["fr"],
    "CA-FR": ["fr", "en"],
    # Germanic
    "DE": ["de"],
    "AT": ["de"],
    "NL": ["nl"],
    "SE": ["sv"],
    "NO": ["no"],
    "DK": ["da"],
    "FI": ["fi", "sv"],
    "IS": ["is"],
    # East Asia
    "JP": ["ja"],
    "KR": ["ko"],
    "CN": ["zh"],
    "TW": ["zh"],  # Traditional in practice; we normalize to 'zh' core
    "HK": ["zh", "en"],
    "MO": ["zh", "pt"],
    "SG": ["en", "zh", "ms", "ta"],
    # Slavic / others
    "RU": ["ru"],
    "UA": ["uk"],
    "PL": ["pl"],
    "CZ": ["cs"],
    "SK": ["sk"],
    "SI": ["sl"],
    "HR": ["hr"],
    "RO": ["ro"],
    "BG": ["bg"],
    "EL": ["el"],
    # Middle East
    "IL": ["he", "ar"],
    "SA": ["ar"],
    "AE": ["ar"],
    "EG": ["ar"],
    "MA": ["ar", "fr", "ber"],
    # South / SE Asia
    "IN": ["hi", "en", "bn", "ta", "te", "ml", "mr", "gu", "pa", "or", "as", "ur", "kok"],
    "PK": ["ur", "en"],
    "BD": ["bn"],
    "TH": ["th"],
    "VN": ["vi"],
    "ID": ["id"],
}


def _detect_script(sample: str) -> Optional[str]:
    if not sample:
        return None
    # Japanese
    if any("\u3040" <= ch <= "\u30ff" for ch in sample):
        return "ja"
    # Chinese Han
    if any("\u4e00" <= ch <= "\u9fff" for ch in sample):
        return "zh"
    # Korean Hangul
    if any("\uac00" <= ch <= "\ud7af" for ch in sample):
        return "ko"
    # Cyrillic
    if any("\u0400" <= ch <= "\u04FF" for ch in sample):
        return "ru"
    # Arabic
    if any("\u0600" <= ch <= "\u06FF" for ch in sample):
        return "ar"
    # Hebrew
    if any("\u0590" <= ch <= "\u05FF" for ch in sample):
        return "he"
    return None


class AmbiguityResolver:
    """
    Resolves ambiguous signals (flags, broad codes, aliases) to a canonical language code.

    This resolver will:
      - Prefer explicit mappings from a language_map.json if available.
      - Support flag emoji -> country -> candidate languages.
      - Support language aliases (user-friendly names and abbreviations).
      - Consult cache_manager for user preferences and role_manager hints.
      - Fall back to heuristic script detection and base country-language map.

    Context may include:
      - guild_id: int
      - user_id: int
      - preferred_codes: List[str]
      - sample_text: str
      - role_manager: object with resolve_code(str)->str or suggest_languages(...)
      - cache_manager: object with get_user_lang(gid, uid)->str
    """

    def __init__(
        self,
        *,
        role_manager: Optional[Any] = None,
        cache_manager: Optional[Any] = None,
        language_map: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.roles = role_manager
        self.cache = cache_manager

        # Load language map either from provided dict or default JSON file
        lm = language_map or self._load_language_map()
        self._language_map = lm or {}

        # Convenience caches derived from language_map.json
        self.flag_role_map: Dict[str, List[str]] = {}
        self.ambiguous_flag_options: Dict[str, List[Dict[str, str]]] = {}
        self.language_aliases: Dict[str, str] = {}
        self.name_to_code: Dict[str, str] = {}

        try:
            self.flag_role_map = {k: list(v) for k, v in self._language_map.get("flag_role_map", {}).items()}
        except Exception:
            self.flag_role_map = {}

        try:
            self.ambiguous_flag_options = {k: list(v) for k, v in self._language_map.get("ambiguous_flag_options", {}).items()}
        except Exception:
            self.ambiguous_flag_options = {}

        try:
            self.language_aliases = {k.lower(): v for k, v in self._language_map.get("language_aliases", {}).items()}
        except Exception:
            self.language_aliases = {}

        # Build name -> normalized code mapping using deepl and google mappings if present.
        # Normalization: take primary part of code (before any dash) and lowercase it.
        try:
            name_code_map: Dict[str, str] = {}
            # google_lang_codes first (broad coverage)
            for name, code in self._language_map.get("google_lang_codes", {}).items():
                if isinstance(name, str) and isinstance(code, str):
                    name_code_map[name.lower()] = self._normalize_code(code)
            # deepl_lang_codes override or add (DeepL preferred where applicable)
            for name, code in self._language_map.get("deepl_lang_codes", {}).items():
                if isinstance(name, str) and isinstance(code, str):
                    name_code_map[name.lower()] = self._normalize_code(code)
            self.name_to_code = name_code_map
        except Exception:
            self.name_to_code = {}

    @staticmethod
    def _load_language_map() -> Optional[Dict[str, Any]]:
        try:
            base = Path(__file__).parent
            p = base / "language_map.json"
            if not p.exists():
                return None
            with p.open("r", encoding="utf-8") as fh:
                return json.load(fh)
        except Exception:
            return None

    @staticmethod
    def _normalize_code(code: str) -> str:
        """
        Normalize a language code string to its base two-letter (or core) lowercase form.
        Examples: "EN-US" -> "en", "pt-BR" -> "pt", "zh" -> "zh"
        """
        if not code:
            return "en"
        c = str(code).strip().lower()
        if "-" in c:
            parts = c.split("-", 1)
            if parts and parts[0]:
                return parts[0]
        return c

    def resolve(self, value: str, *, context: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """
        Resolve a token (flag emoji, alias, code, role name) into a canonical language code.
        Returns a base code like 'en', 'fr', 'zh', or None if nothing useful.
        """
        ctx = context or {}
        token = (value or "").strip()
        if not token:
            return None

        # 1) Flag emoji -> use ambiguous options or flag -> role mapping -> name -> code
        if _is_flag_emoji(token):
            # First, check if the explicit ambiguous options exist in the JSON map
            if token in self.ambiguous_flag_options:
                opts = self.ambiguous_flag_options.get(token) or []
                # Try to pick one that matches user preference/context
                chosen = self._choose_from_ambiguous_options(opts, ctx)
                if chosen:
                    return chosen

            # Next, see if flag_role_map has direct role names associated
            role_names = self.flag_role_map.get(token)
            if role_names:
                # map role name -> code (try first matching preferred or known)
                codes = []
                for rn in role_names:
                    if not rn:
                        continue
                    # try find by name in name_to_code
                    code = self.name_to_code.get(rn.lower())
                    if code:
                        codes.append(code)
                if codes:
                    return self._choose_best(codes, ctx)

            # Fallback: convert flag to country and use country map
            country = _flag_to_country(token)
            candidates = self._candidates_for_country(country)
            return self._choose_best(candidates, ctx)

        # 2) Check explicit language aliases from JSON (alias -> canonical name)
        lower = token.lower()
        if lower in self.language_aliases:
            canonical_name = self.language_aliases[lower]
            if isinstance(canonical_name, str):
                code = self.name_to_code.get(canonical_name.lower())
                if code:
                    return code

        # 3) If token looks like a role name or a canonical language name (e.g., "English")
        #    try direct mapping name -> code
        if lower in self.name_to_code:
            return self.name_to_code[lower]

        # 4) Broad code forms (e.g., zh, pt, en, or en-US) -> keep canonical core
        code = lower.replace("_", "-")
        if "-" in code:
            code = code.split("-", 1)[0]
        if code:
            # If we have a name_to_code entry for this (some maps might use codes as keys), prefer that
            if code in self.name_to_code:
                return self.name_to_code[code]
            # Otherwise assume it's already a base code and return it
            return code

        # 5) If sample text present, prefer script-inferred language
        sample = ctx.get("sample_text")
        inferred = _detect_script(sample) if isinstance(sample, str) else None
        if inferred:
            return inferred

        # 6) Use explicit user preference in cache if available
        gid = ctx.get("guild_id")
        uid = ctx.get("user_id")
        if self.cache and isinstance(gid, int) and isinstance(uid, int):
            try:
                pref = self.cache.get_user_lang(gid, uid)
                if pref:
                    pref = str(pref).split("-", 1)[0].lower()
                    return pref
            except Exception:
                pass

        # 7) Preferred codes from context
        pref_list: List[str] = [
            c.split("-", 1)[0].lower() for c in (ctx.get("preferred_codes") or []) if isinstance(c, str)
        ]
        if pref_list:
            if code in pref_list:
                return code
            return pref_list[0]

        # 8) Role manager hint
        if self.roles and hasattr(self.roles, "resolve_code"):
            try:
                hinted = self.roles.resolve_code(token)
                if isinstance(hinted, str) and hinted:
                    return hinted
            except Exception:
                pass

        # 9) Default: return canonical base or 'en'
        return code or "en"

    def _choose_from_ambiguous_options(self, opts: List[Dict[str, str]], ctx: Dict[str, Any]) -> Optional[str]:
        """
        Given JSON ambiguous options like:
          [ {"role_name": "Hindi", "button_label": "Hindi"}, ... ]
        pick the best code using context (cache preference, preferred_codes, role hints).
        """
        if not opts:
            return None

        # Build candidate codes from options
        candidates = []
        for opt in opts:
            rn = opt.get("role_name") if isinstance(opt, dict) else None
            if not rn:
                continue
            code = self.name_to_code.get(rn.lower())
            if code:
                candidates.append(code)

        if not candidates:
            return None

        return self._choose_best(candidates, ctx)

    def _candidates_for_country(self, country: Optional[str]) -> List[str]:
        """
        Return candidate language codes for a country.
        This will use the internal _COUNTRY_LANGS fallbacks. If the language_map.json
        provided more specific country mappings in future, this method can be extended
        to read that.
        """
        if not country:
            return ["en"]
        # Special case "CA-FR" if consumer provided that pseudo country
        if country == "CA-FR":
            return _COUNTRY_LANGS.get(country, ["fr", "en"])
        return _COUNTRY_LANGS.get(country, ["en"])

    def _choose_best(self, candidates: Iterable[str], ctx: Dict[str, Any]) -> str:
        """
        Choose the best candidate code from a list using:
         1) user cache preference
         2) explicit preferred_codes in context
         3) role manager hints
         4) first candidate fallback
        """
        cands = [str(c).split("-", 1)[0].lower() for c in candidates if isinstance(c, str)]
        if not cands:
            return "en"

        # 1) Honor user preference in cache
        gid = ctx.get("guild_id")
        uid = ctx.get("user_id")
        if self.cache and isinstance(gid, int) and isinstance(uid, int):
            try:
                pref = self.cache.get_user_lang(gid, uid)
                if pref:
                    pref = pref.split("-", 1)[0].lower()
                    if pref in cands:
                        return pref
            except Exception:
                pass

        # 2) Honor explicit preferred_codes in context
        pref_list: List[str] = [
            c.split("-", 1)[0].lower() for c in (ctx.get("preferred_codes") or []) if isinstance(c, str)
        ]
        for p in pref_list:
            if p in cands:
                return p

        # 3) If role_manager can suggest or rank, try it
        rm = self.roles
        if rm and hasattr(rm, "resolve_code"):
            try:
                for cand in cands:
                    hinted = rm.resolve_code(cand)
                    if isinstance(hinted, str) and hinted:
                        return hinted
            except Exception:
                pass

        # 4) Fallback to first in candidate order
        return cands[0]