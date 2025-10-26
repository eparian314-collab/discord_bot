"""
Policy helpers for configuring translation behaviour.

Policies are lightweight objects that describe how the system should interpret
and respond to language requests for a given scope (guild, channel, or user).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, Optional, Tuple

DEFAULT_PROVIDER_ORDER = ("deepl", "openai", "mymemory")


@dataclass
class TranslationPolicy:
    """
    Declarative description of translation preferences for a scope.
    """

    fallback_language: str = "en"
    auto_detect_source: bool = True
    allow_inline_commands: bool = True
    preferred_providers: Tuple[str, ...] = field(default_factory=lambda: DEFAULT_PROVIDER_ORDER)
    blocked_languages: Tuple[str, ...] = field(default_factory=tuple)
    notes: str = ""

    def allows_language(self, code: str) -> bool:
        """Return True when the language code is not explicitly blocked."""
        normalized = (code or "").split("-", 1)[0].lower()
        return normalized not in {lang.split("-", 1)[0].lower() for lang in self.blocked_languages}


class PolicyRepository:
    """
    Very small in-memory policy registry keyed by (guild_id, channel_id, user_id).
    """

    def __init__(self) -> None:
        self._policies: Dict[Tuple[Optional[int], Optional[int], Optional[int]], TranslationPolicy] = {}

    def set_policy(
        self,
        *,
        guild_id: Optional[int],
        channel_id: Optional[int] = None,
        user_id: Optional[int] = None,
        policy: TranslationPolicy,
    ) -> None:
        key = (guild_id, channel_id, user_id)
        self._policies[key] = policy

    def get_policy(
        self,
        *,
        guild_id: Optional[int],
        channel_id: Optional[int] = None,
        user_id: Optional[int] = None,
        default: Optional[TranslationPolicy] = None,
    ) -> TranslationPolicy:
        """
        Resolve a policy following specificity order:
          1. Exact (guild, channel, user)
          2. (guild, channel, None)
          3. (guild, None, None)
          4. Global fallback
        """
        search_keys = [
            (guild_id, channel_id, user_id),
            (guild_id, channel_id, None),
            (guild_id, None, None),
            (None, None, None),
        ]
        for key in search_keys:
            policy = self._policies.get(key)
            if policy:
                return policy
        return default or TranslationPolicy()

    def remove_policy(
        self,
        *,
        guild_id: Optional[int],
        channel_id: Optional[int] = None,
        user_id: Optional[int] = None,
    ) -> None:
        """Delete a specific policy if it exists."""
        self._policies.pop((guild_id, channel_id, user_id), None)

    def list_policies(self) -> Dict[Tuple[Optional[int], Optional[int], Optional[int]], TranslationPolicy]:
        """Return a shallow copy of all stored policies (useful for diagnostics)."""
        return dict(self._policies)

    def load_bulk(self, items: Iterable[Tuple[Optional[int], Optional[int], Optional[int], TranslationPolicy]]) -> None:
        """Bulk-load policies from an iterable of tuples."""
        for guild_id, channel_id, user_id, policy in items:
            self.set_policy(guild_id=guild_id, channel_id=channel_id, user_id=user_id, policy=policy)
