from __future__ import annotations
import json, os
from dataclasses import dataclass
from typing import Dict, Optional, Tuple, Iterable, List
from .profile import LanguageProfile
from .templates import BUILTIN_LOCALE_SEEDS, EN_US_DEFAULTS

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOCALE_DIR = os.path.join(BASE_DIR, "resources", "locale")

@dataclass(frozen=True)
class PromptBundle:
    locale_code: str
    prompts: Dict[str, str]
    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        return self.prompts.get(key, default)

class LanguageRegistry:
    def __init__(self) -> None:
        self._profiles: Dict[str, LanguageProfile] = {}
        self._guild_locale: Dict[int, str] = {}
        self._user_locale: Dict[Tuple[int, int], str] = {}
        for code, data in BUILTIN_LOCALE_SEEDS.items():
            self.register_profile(LanguageProfile(name=code, locale_code=code, default_prompts=dict(data)))
        if "en-US" not in self._profiles:
            self.register_profile(LanguageProfile(name="en-US", locale_code="en-US", default_prompts=dict(EN_US_DEFAULTS)))
        self._load_filesystem_locales()

    def register_profile(self, profile: LanguageProfile) -> None:
        self._profiles[profile.locale_code] = profile

    def set_guild_locale(self, guild_id: int, locale_code: str) -> None:
        self._guild_locale[guild_id] = locale_code

    def set_user_locale(self, guild_id: int, user_id: int, locale_code: str) -> None:
        self._user_locale[(guild_id, user_id)] = locale_code

    def resolve_prompt_bundle(self, *, guild_id: Optional[int], user_id: Optional[int]) -> PromptBundle:
        code = None
        if guild_id is not None and user_id is not None:
            code = self._user_locale.get((guild_id, user_id))
        if not code and guild_id is not None:
            code = self._guild_locale.get(guild_id)
        if not code:
            code = "en-US"
        merged = self._resolve_locale_chain(code)
        return PromptBundle(locale_code=code, prompts=merged)

    def render_prompt(self, key: str, *, guild_id: Optional[int], user_id: Optional[int], default: Optional[str] = None, **fmt) -> str:
        bundle = self.resolve_prompt_bundle(guild_id=guild_id, user_id=user_id)
        raw = bundle.get(key, default if default is not None else key)
        try:
            return raw.format(**fmt) if isinstance(raw, str) else str(raw)
        except Exception:
            return str(raw)

    def _resolve_locale_chain(self, code: str) -> Dict[str, str]:
        merged: Dict[str, str] = dict(EN_US_DEFAULTS)
        builtin = BUILTIN_LOCALE_SEEDS.get(code)
        if builtin: merged.update(builtin)
        flat_path = os.path.join(LOCALE_DIR, f"{code}.json")
        merged.update(self._load_json_if_exists(flat_path))
        cat_dir = os.path.join(LOCALE_DIR, code)
        if os.path.isdir(cat_dir):
            for fname in sorted(os.listdir(cat_dir)):
                if fname.endswith(".json"):
                    merged.update(self._load_json_if_exists(os.path.join(cat_dir, fname)))
        return merged

    def _load_filesystem_locales(self) -> None:
        if not os.path.isdir(LOCALE_DIR):
            return
        for fname in os.listdir(LOCALE_DIR):
            if fname.endswith(".json"):
                code = fname[:-5]
                data = self._load_json_if_exists(os.path.join(LOCALE_DIR, fname))
                self._merge_profile(code, data)
        for entry in os.listdir(LOCALE_DIR):
            code_dir = os.path.join(LOCALE_DIR, entry)
            if os.path.isdir(code_dir):
                combined: Dict[str, str] = {}
                for fname in sorted(os.listdir(code_dir)):
                    if fname.endswith(".json"):
                        combined.update(self._load_json_if_exists(os.path.join(code_dir, fname)))
                self._merge_profile(entry, combined)

    def _merge_profile(self, code: str, data: Dict[str, str]) -> None:
        if not data: return
        existing = self._profiles.get(code)
        if existing:
            m = dict(existing.default_prompts); m.update(data)
            self._profiles[code] = LanguageProfile(name=existing.name or code, locale_code=code, default_prompts=m, fallbacks=existing.fallbacks)
        else:
            self._profiles[code] = LanguageProfile(name=code, locale_code=code, default_prompts=data)

    @staticmethod
    def _load_json_if_exists(path: str) -> Dict[str, str]:
        try:
            if os.path.isfile(path):
                import json
                with open(path, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                out = {}
                for k, v in raw.items():
                    if isinstance(k, str) and isinstance(v, str): out[k] = v
                return out
        except Exception:
            pass
        return {}
