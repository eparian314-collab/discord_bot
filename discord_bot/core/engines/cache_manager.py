from __future__ import annotations

from typing import Any, Dict, Optional, Tuple
import time


class CacheManager:
    """
    Hybrid in-memory cache for language preferences and ephemeral data.
    Does not persist across restart (persistence handled by other modules if needed).
    """

    def __init__(self, *, default_ttl: int = 60 * 60 * 24) -> None:
        self._default_ttl = default_ttl
        self._user_lang: Dict[Tuple[int, int], Tuple[str, float]] = {}
        self._kv: Dict[str, Tuple[Any, float]] = {}

    # ----------------------
    # User Language Cache
    # ----------------------

    def set_user_lang(self, guild_id: int, user_id: int, code: str, *, ttl: Optional[int] = None) -> None:
        expire = time.time() + (ttl or self._default_ttl)
        self._user_lang[(guild_id, user_id)] = (code, expire)

    def get_user_lang(self, guild_id: int, user_id: int) -> Optional[str]:
        key = (guild_id, user_id)
        if key not in self._user_lang:
            return None
        code, expire = self._user_lang[key]
        if expire < time.time():
            del self._user_lang[key]
            return None
        return code

    def delete_user_lang(self, guild_id: int, user_id: int) -> None:
        """
        Remove a cached language preference for a user if present.
        """
        self._user_lang.pop((guild_id, user_id), None)

    # ----------------------
    # Generic KV Cache
    # ----------------------

    def set(self, key: str, value: Any, *, ttl: Optional[int] = None) -> None:
        expire = time.time() + (ttl or self._default_ttl)
        self._kv[key] = (value, expire)

    def get(self, key: str) -> Optional[Any]:
        if key not in self._kv:
            return None
        value, expire = self._kv[key]
        if expire < time.time():
            del self._kv[key]
            return None
        return value

    def delete(self, key: str) -> None:
        if key in self._kv:
            del self._kv[key]

    def clear(self) -> None:
        self._user_lang.clear()
        self._kv.clear()


