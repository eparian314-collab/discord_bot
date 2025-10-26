from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
import discord


class RoleManager:
    """
    Manages detection, resolution, and assignment of language roles.
    Ensures roles align with canonical language codes (e.g., "en", "es", "ja").
    """

    def __init__(self, *, cache_manager, error_engine=None) -> None:
        self.cache = cache_manager
        self.error_engine = error_engine

    # ----------------------
    # Language Code Resolution
    # ----------------------

    def resolve_code(self, token: str) -> Optional[str]:
        """
        Normalize role/language token into canonical code.
        """
        if not token:
            return None
        t = token.strip().lower()
        if "-" in t:
            t = t.split("-", 1)[0]
        t = t.replace("_", "")
        return t

    def suggest_languages(self, query: str, limit: int = 10) -> List[Any]:
        """
        Optional extension hook (not populated in this baseline).
        Returns sample language objects if available.
        """
        return []

    # ----------------------
    # Role Syncing
    # ----------------------

    async def sync_language_roles(self, guild: discord.Guild) -> Tuple[int, int]:
        """
        Ensure roles exist for known languages. Baseline implementation scans existing roles only.
        Returns: (created_count, skipped_count)
        """
        created = 0
        skipped = 0

        existing = {r.name.lower(): r for r in guild.roles}
        known = set()

        for name, role in existing.items():
            code = self.resolve_code(name)
            if code:
                known.add(code)

        # No auto-creation in this baseline version
        return created, skipped

    # ----------------------
    # Assignment
    # ----------------------

    async def assign_language_role(self, member: discord.Member, code: str) -> Optional[discord.Role]:
        code = self.resolve_code(code)
        if not code or not member.guild:
            return None

        guild = member.guild
        target_role = None

        for r in guild.roles:
            if self.resolve_code(r.name) == code:
                target_role = r
                break

        if not target_role:
            return None

        try:
            await member.add_roles(target_role, reason="Language role assignment")
            return target_role
        except Exception as e:
            if self.error_engine:
                await self.error_engine.log_error(e, context="assign_language_role")
            return None
