from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple
import unicodedata

import discord

from discord_bot.language_context.context_utils import (
    load_language_map,
    map_alias_to_code,
    normalize_lang_code,
)


class RoleManagerError(RuntimeError):
    """Base exception for language role operations."""

    def __init__(self, message: str, *, code: Optional[str] = None) -> None:
        super().__init__(message)
        self.code = code


class LanguageNotRecognized(RoleManagerError):
    """Raised when a provided language token cannot be resolved."""


class RoleLimitExceeded(RoleManagerError):
    """Raised when a member already holds the maximum number of language roles."""

    def __init__(self, max_roles: int) -> None:
        super().__init__(f"Maximum of {max_roles} language roles reached.")
        self.max_roles = max_roles


class RolePermissionError(RoleManagerError):
    """Raised when the bot lacks permission to manage roles."""


class RoleNotAssigned(RoleManagerError):
    """Raised when attempting to remove a language role the member does not have."""


class AmbiguousLanguage(RoleManagerError):
    """Raised when a token maps to multiple possible languages and a decision is required."""

    def __init__(self, options: List[Tuple[str, str]]) -> None:
        super().__init__("Multiple languages matched this input.")
        self.options = options


@dataclass(frozen=True)
class AssignmentResult:
    role: discord.Role
    code: str
    display_name: str
    created: bool
    already_had: bool


@dataclass(frozen=True)
class RemovalResult:
    role: discord.Role
    code: str
    display_name: str


class RoleManager:
    """
    Manages detection, resolution, and assignment of language roles.
    Ensures roles align with canonical language codes (e.g., "en", "es", "ja").
    """

    def __init__(
        self,
        *,
        cache_manager,
        error_engine: Optional[Any] = None,
        alias_helper: Optional[Any] = None,
        language_map: Optional[Dict[str, Any]] = None,
        max_roles: int = 3,
        ambiguity_resolver: Optional[Any] = None,
    ) -> None:
        self.cache = cache_manager
        self.error_engine = error_engine
        self.alias_helper = alias_helper
        self.language_map = language_map or load_language_map()
        self.max_roles = max(1, int(max_roles))
        self.bot: Optional[discord.Client] = None
        self.ambiguity_resolver = ambiguity_resolver

        self._code_to_name: Dict[str, str] = self._build_code_to_name()
        self._flag_role_map: Dict[str, List[str]] = {}
        self._ambiguous_flag_options: Dict[str, List[Dict[str, str]]] = {}
        self._alias_index: Dict[str, str] = {}
        if isinstance(self.language_map, dict):
            flag_map = self.language_map.get("flag_role_map")
            if isinstance(flag_map, dict):
                self._flag_role_map = {k: list(v) for k, v in flag_map.items() if isinstance(v, list)}
            ambiguous = self.language_map.get("ambiguous_flag_options")
            if isinstance(ambiguous, dict):
                self._ambiguous_flag_options = {k: list(v) for k, v in ambiguous.items() if isinstance(v, list)}
        if self.alias_helper and hasattr(self.alias_helper, "alias_to_code"):
            try:
                self._alias_index = {
                    str(alias): normalize_lang_code(code)
                    for alias, code in getattr(self.alias_helper, "alias_to_code").items()
                }
            except Exception:
                self._alias_index = {}

    # ----------------------
    # Language Code Resolution
    # ----------------------

    def resolve_code(
        self,
        token: Optional[str],
        *,
        guild_id: Optional[int] = None,
        user_id: Optional[int] = None,
        preferred_codes: Optional[Iterable[str]] = None,
    ) -> Optional[str]:
        """
        Normalize role/language token into canonical base code.
        Returns None when the token cannot be resolved confidently.
        """
        preferred = [normalize_lang_code(c) for c in (preferred_codes or []) if self._is_valid_code(c)]
        if not token:
            return None
        if self._is_flag(token):
            candidates = self._flag_candidates(token)
            if len(candidates) == 1:
                return candidates[0][0]
            if len(candidates) > 1:
                return None
        # Direct alias resolution
        code = map_alias_to_code(token, alias_helper=self.alias_helper, language_map=self.language_map)
        if code and self._is_valid_code(code):
            return normalize_lang_code(code)

        # Ambiguity resolver (handles flags, broader names)
        if self.ambiguity_resolver:
            ctx: Dict[str, Any] = {}
            if guild_id is not None:
                ctx["guild_id"] = guild_id
            if user_id is not None:
                ctx["user_id"] = user_id
            if preferred:
                ctx["preferred_codes"] = preferred
            resolved = self.ambiguity_resolver.resolve(token, context=ctx)
            if resolved and self._is_valid_code(resolved):
                return normalize_lang_code(resolved)

        # Structural fallback (codes like "en", "fr-ca")
        candidate = normalize_lang_code(token)
        if self._is_valid_code(candidate):
            return candidate
        return None

    def friendly_name(self, code: str) -> str:
        """
        Return a display-friendly language name for a canonical code.
        """
        norm = normalize_lang_code(code)
        if norm in self._code_to_name:
            return self._code_to_name[norm]
        return norm.upper()

    def suggest_languages(
        self,
        query: str,
        *,
        limit: int = 25,
        restrict_to: Optional[Iterable[str]] = None,
    ) -> List[Tuple[str, str]]:
        """
        Return a list of (code, display-name) suggestions matching `query`.
        If `restrict_to` provided, only suggest from those codes.
        """
        normalized_query = self._normalize_search_token(query)

        # If the user already typed a specific language/alias, resolve immediately.
        if normalized_query:
            resolved = self.resolve_code(
                query,
                guild_id=None,
                user_id=None,
                preferred_codes=restrict_to,
            )
            if resolved:
                return [(resolved, self.friendly_name(resolved))]

        pool: Iterable[str]
        if restrict_to:
            pool = {normalize_lang_code(code) for code in restrict_to if self._is_valid_code(code)}
        else:
            pool = set(self._code_to_name.keys()) | set(self._alias_index.values())

        suggestions: List[Tuple[str, str]] = []
        seen: set[str] = set()

        def consider(code: str) -> None:
            if not code:
                return
            base = normalize_lang_code(code)
            if base in seen or not self._is_valid_code(base):
                return
            label = self.friendly_name(base)

            search_tokens = {
                self._normalize_search_token(label),
                self._normalize_search_token(code),
            }

            alias_tokens_raw: Iterable[str] = ()
            if self.alias_helper and hasattr(self.alias_helper, "code_to_aliases"):
                try:
                    alias_tokens_raw = getattr(self.alias_helper, "code_to_aliases").get(base, [])
                except Exception:
                    alias_tokens_raw = ()

            alias_tokens_norm = {
                self._normalize_search_token(a) for a in alias_tokens_raw if isinstance(a, str)
            }

            all_tokens = search_tokens | alias_tokens_norm

            match = False
            if not normalized_query:
                match = True
            else:
                match = any(token.startswith(normalized_query) for token in all_tokens if token)
                if not match:
                    match = any(normalized_query in token for token in all_tokens if token)

            if match:
                seen.add(base)
                suggestions.append((base, label))

        for code in pool:
            consider(code)
            if len(suggestions) >= limit:
                break

        if not normalized_query and len(suggestions) < limit:
            for code in self._code_to_name.keys():
                if len(suggestions) >= limit:
                    break
                consider(code)

        return suggestions[:limit]

    # ----------------------
    # Public API
    # ----------------------

    async def assign_language_role(self, member: discord.Member, token: str) -> AssignmentResult:
        language_roles = self._language_roles_for_member(member)
        existing_codes = [self.resolve_code(r.name, guild_id=member.guild.id, user_id=member.id) for r in language_roles]
        preferred_codes = [c for c in existing_codes if c]

        code = self.resolve_code(
            token,
            guild_id=member.guild.id,
            user_id=member.id,
            preferred_codes=preferred_codes,
        )
        if not code:
            # Handle flag emoji / ambiguous selections manually
            ambiguous = self._flag_candidates(token)
            if ambiguous:
                if len(ambiguous) == 1:
                    code = ambiguous[0][0]
                else:
                    raise AmbiguousLanguage(ambiguous)
        if not code:
            raise LanguageNotRecognized(f"I don't recognise the language '{token}'.", code=None)

        existing_role = self._match_role(language_roles, code)
        display_name = self.friendly_name(code)

        if existing_role:
            # Refresh preference when the member already has the role.
            self._set_preference(member.guild.id, member.id, code)
            return AssignmentResult(
                role=existing_role,
                code=code,
                display_name=display_name,
                created=False,
                already_had=True,
            )

        if len(language_roles) >= self.max_roles:
            raise RoleLimitExceeded(self.max_roles)

        role, created = await self._ensure_role(member.guild, code, display_name)

        try:
            await member.add_roles(role, reason="Language role assignment")
        except discord.Forbidden as exc:
            raise RolePermissionError("I don't have permission to assign that role.") from exc
        except discord.HTTPException as exc:
            raise RoleManagerError("Failed to assign the language role.") from exc

        self._set_preference(member.guild.id, member.id, code)
        return AssignmentResult(role=role, code=code, display_name=display_name, created=created, already_had=False)

    async def remove_language_role(self, member: discord.Member, token: str) -> RemovalResult:
        language_roles = self._language_roles_for_member(member)
        existing_codes = [self.resolve_code(r.name, guild_id=member.guild.id, user_id=member.id) for r in language_roles]
        preferred_codes = [c for c in existing_codes if c]

        code = self.resolve_code(
            token,
            guild_id=member.guild.id,
            user_id=member.id,
            preferred_codes=preferred_codes,
        )
        if not code:
            candidates = self._flag_candidates(token)
            if candidates:
                code = candidates[0][0]
        if not code:
            raise LanguageNotRecognized(f"I don't recognise the language '{token}'.", code=None)

        target_role = self._match_role(language_roles, code)
        if not target_role:
            raise RoleNotAssigned(f"You don't currently have a role for '{self.friendly_name(code)}'.", code=code)

        try:
            await member.remove_roles(target_role, reason="Language role removal")
        except discord.Forbidden as exc:
            raise RolePermissionError("I don't have permission to remove that role.") from exc
        except discord.HTTPException as exc:
            raise RoleManagerError("Failed to remove the language role.") from exc

        self._update_preference_after_removal(member, code, language_roles, target_role)
        return RemovalResult(role=target_role, code=code, display_name=self.friendly_name(code))

    async def get_user_languages(self, user_id: int, guild_id: int) -> List[str]:
        """
        Return canonical language codes for the given user by inspecting guild roles.
        """
        guild = None
        if self.bot:
            guild = self.bot.get_guild(guild_id)
        if not guild:
            return []

        member = guild.get_member(user_id)
        if member is None:
            try:
                member = await guild.fetch_member(user_id)
            except discord.HTTPException:
                return []

        return [
            code
            for code in (self.resolve_code(role.name) for role in member.roles)
            if code is not None
        ]

    async def sync_language_roles(self, guild: discord.Guild) -> Tuple[int, int]:
        """
        Best-effort sync: currently scans existing roles and reports how many match known languages.
        Returns (created_roles, recognised_roles).
        """
        recognised = sum(1 for role in guild.roles if self.resolve_code(role.name))
        return 0, recognised

    # ----------------------
    # Internal helpers
    # ----------------------

    def _build_code_to_name(self) -> Dict[str, str]:
        mapping: Dict[str, str] = {}
        if isinstance(self.language_map, dict):
            aliases = self.language_map.get("language_aliases", {})
            if isinstance(aliases, dict):
                for alias_token, canonical in aliases.items():
                    if not isinstance(alias_token, str) or not isinstance(canonical, str):
                        continue
                    code = map_alias_to_code(alias_token, alias_helper=self.alias_helper, language_map=self.language_map)
                    if code:
                        mapping.setdefault(normalize_lang_code(code), canonical)
        return mapping

    def _language_roles_for_member(self, member: discord.Member) -> List[discord.Role]:
        roles: List[discord.Role] = []
        for role in member.roles:
            if self.resolve_code(role.name):
                roles.append(role)
        return roles

    def _match_role(self, roles: Iterable[discord.Role], code: str) -> Optional[discord.Role]:
        target = normalize_lang_code(code)
        for role in roles:
            if self.resolve_code(role.name) == target:
                return role
        return None

    async def _ensure_role(self, guild: discord.Guild, code: str, display_name: str) -> Tuple[discord.Role, bool]:
        existing = self._match_role(guild.roles, code)
        if existing:
            return existing, False

        try:
            role = await guild.create_role(name=display_name, reason="Auto-created language role")
        except discord.Forbidden as exc:
            raise RolePermissionError("I don't have permission to create new language roles.") from exc
        except discord.HTTPException as exc:
            raise RoleManagerError("Failed to create a new language role.") from exc
        return role, True

    def _set_preference(self, guild_id: int, user_id: int, code: str) -> None:
        try:
            if hasattr(self.cache, "set_user_lang"):
                self.cache.set_user_lang(guild_id, user_id, code)
        except Exception:
            if self.error_engine and hasattr(self.error_engine, "log_error"):
                self.error_engine.log_error(Exception("cache set_user_lang failed"), context="role_manager.set_preference")

    def _update_preference_after_removal(
        self,
        member: discord.Member,
        removed_code: str,
        language_roles: List[discord.Role],
        removed_role: discord.Role,
    ) -> None:
        guild_id = member.guild.id
        user_id = member.id

        remaining = [
            self.resolve_code(role.name)
            for role in language_roles
            if role.id != removed_role.id
        ]
        remaining = [code for code in remaining if code]

        if remaining:
            self._set_preference(guild_id, user_id, remaining[0])  # type: ignore[index]
        else:
            if hasattr(self.cache, "delete_user_lang"):
                self.cache.delete_user_lang(guild_id, user_id)

    # ----------------------
    # Internal helpers for token resolution
    # ----------------------

    @staticmethod
    def _is_valid_code(token: Optional[str]) -> bool:
        if not token:
            return False
        t = normalize_lang_code(token)
        return t.isalpha() and 2 <= len(t) <= 3

    @staticmethod
    def _is_flag(token: str) -> bool:
        if not token:
            return False
        return all(0x1F1E6 <= ord(ch) <= 0x1F1FF for ch in token)

    def _flag_candidates(self, token: str) -> List[Tuple[str, str]]:
        if not token or not self._is_flag(token):
            return []

        candidates: List[Tuple[str, str]] = []

        # First check explicit ambiguous options with button labels
        options = self._ambiguous_flag_options.get(token, [])
        for opt in options:
            role_name = opt.get("role_name")
            if not isinstance(role_name, str):
                continue
            code = map_alias_to_code(role_name, alias_helper=self.alias_helper, language_map=self.language_map)
            if code and self._is_valid_code(code):
                code = normalize_lang_code(code)
                label = opt.get("button_label") if isinstance(opt.get("button_label"), str) else self.friendly_name(code)
                candidates.append((code, label))

        if candidates:
            return candidates

        # Fall back to direct role-name mapping for the flag
        names = self._flag_role_map.get(token, [])
        for name in names:
            code = map_alias_to_code(name, alias_helper=self.alias_helper, language_map=self.language_map)
            if code and self._is_valid_code(code):
                code = normalize_lang_code(code)
            candidates.append((code, self.friendly_name(code)))

        return candidates

    @staticmethod
    def _normalize_search_token(token: Optional[str]) -> str:
        if not token:
            return ""
        text = unicodedata.normalize("NFKD", token)
        text = "".join(ch for ch in text if not unicodedata.combining(ch))
        text = text.lower().strip()
        text = text.replace("_", " ").replace("-", " ")
        while "  " in text:
            text = text.replace("  ", " ")
        return text
