"""
Central catalog of event bus topics and expected payload keys.

This module defines string constants for topics and lightweight type hints for
payloads. Engines should import only the constants (not the bus) to avoid
cycles. The IntegrationLoader wires publishers/subscribers.

Design rules:
- Topics are snake.case with domain prefix, e.g. "translation.requested".
- Payloads are plain dicts; keys documented here for traceability.
- No imports from discord.* - keep domain-pure and testable.
"""
from __future__ import annotations

from typing import TypedDict, Optional, Any


# -----------------------
# Topic name constants
# -----------------------
TRANSLATION_REQUESTED = "translation.requested"
TRANSLATION_COMPLETED = "translation.completed"
TRANSLATION_FAILED = "translation.failed"

ENGINE_ERROR = "engine.error"
STORAGE_READY = "storage.ready"
SHUTDOWN_INITIATED = "shutdown.initiated"


# -----------------------
# Payload contracts
# -----------------------
class TranslationRequested(TypedDict, total=False):
    text: str
    src: Optional[str]
    tgt: Optional[str]
    user_id: Optional[int]
    message_id: Optional[int]
    correlation_id: Optional[str]


class TranslationCompleted(TypedDict, total=False):
    text: str  # resolved/translated text
    provider: Optional[str]
    src: Optional[str]
    tgt: Optional[str]
    duration_ms: Optional[float]
    correlation_id: Optional[str]


class TranslationFailed(TypedDict, total=False):
    reason: str
    exc: Optional[Exception]
    correlation_id: Optional[str]
    context: Optional[dict[str, Any]]


class EngineError(TypedDict, total=False):
    name: str           # engine/source name
    category: str       # e.g., adapter/orchestrator/cog/event
    severity: str       # info|warning|error|critical
    exc: Optional[Exception]
    context: Optional[dict[str, Any]]


class StorageReady(TypedDict, total=False):
    ok: bool
    reason: Optional[str]


class ShutdownInitiated(TypedDict, total=False):
    reason: Optional[str]


__all__ = [
    # topics
    "TRANSLATION_REQUESTED",
    "TRANSLATION_COMPLETED",
    "TRANSLATION_FAILED",
    "ENGINE_ERROR",
    "STORAGE_READY",
    "SHUTDOWN_INITIATED",
    # payloads
    "TranslationRequested",
    "TranslationCompleted",
    "TranslationFailed",
    "EngineError",
    "StorageReady",
    "ShutdownInitiated",
]



