"""Domain exceptions and data structures for role management."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

import discord


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
    """Raised when a token maps to multiple possible languages."""

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


__all__ = [
    "RoleManagerError",
    "LanguageNotRecognized",
    "RoleLimitExceeded",
    "RolePermissionError",
    "RoleNotAssigned",
    "AmbiguousLanguage",
    "AssignmentResult",
    "RemovalResult",
]
