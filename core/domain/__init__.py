"""Shared domain models bridging engines and adapters."""

from .event_models import EventCategory, RecurrenceType, EventReminder
from .role_models import (
    AssignmentResult,
    RemovalResult,
    RoleManagerError,
    RoleLimitExceeded,
    RolePermissionError,
    RoleNotAssigned,
    LanguageNotRecognized,
    AmbiguousLanguage,
)

__all__ = [
    "EventCategory",
    "RecurrenceType",
    "EventReminder",
    "AssignmentResult",
    "RemovalResult",
    "RoleManagerError",
    "RoleLimitExceeded",
    "RolePermissionError",
    "RoleNotAssigned",
    "LanguageNotRecognized",
    "AmbiguousLanguage",
]
