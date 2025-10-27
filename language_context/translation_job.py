from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Dict, Any
import time
import uuid


@dataclass(frozen=True, init=False)
class TranslationJob:
    """
    A single translation request.

    Created by ContextEngine and used by:
      - Orchestrator (preferred path)
      - ProcessingEngine.execute_job (adapter fallback)

    Fields:
        text: original text from user
        src: detected or user-selected source language (None = auto)
        tgt: target language code
        guild_id: Discord guild/server ID (0 if DM)
        author_id: Discord user ID
        metadata: optional info for heuristics, logging, caching
        job_id: unique identifier for tracing, caching
        timestamp: created timestamp (epoch seconds)
    """

    text: str
    tgt_lang: str
    src_lang: Optional[str]
    guild_id: int
    author_id: int
    metadata: Dict[str, Any]
    job_id: str
    timestamp: float

    def __init__(
        self,
        *,
        text: str,
        tgt: Optional[str] = None,
        tgt_lang: Optional[str] = None,
        src: Optional[str] = None,
        src_lang: Optional[str] = None,
        guild_id: int = 0,
        author_id: int = 0,
        metadata: Optional[Dict[str, Any]] = None,
        job_id: Optional[str] = None,
        timestamp: Optional[float] = None,
    ) -> None:
        target = tgt_lang if tgt_lang is not None else tgt
        source = src_lang if src_lang is not None else src
        object.__setattr__(self, "text", text)
        object.__setattr__(self, "tgt_lang", target or "en")
        object.__setattr__(self, "src_lang", source)
        object.__setattr__(self, "guild_id", guild_id)
        object.__setattr__(self, "author_id", author_id)
        object.__setattr__(self, "metadata", metadata.copy() if isinstance(metadata, dict) else {})
        object.__setattr__(self, "job_id", job_id or uuid.uuid4().hex)
        object.__setattr__(self, "timestamp", timestamp or time.time())

    @property
    def tgt(self) -> str:
        return self.tgt_lang

    @property
    def src(self) -> Optional[str]:
        return self.src_lang

    def with_src(self, new_src: str) -> "TranslationJob":
        """Return a copy of this job with a new source language."""
        return TranslationJob(
            text=self.text,
            tgt_lang=self.tgt_lang,
            src_lang=new_src,
            guild_id=self.guild_id,
            author_id=self.author_id,
            metadata=self.metadata,
            job_id=self.job_id,
            timestamp=self.timestamp,
        )

    def with_tgt(self, new_tgt: str) -> "TranslationJob":
        """Return a copy of this job with a new target language."""
        return TranslationJob(
            text=self.text,
            tgt_lang=new_tgt,
            src_lang=self.src_lang,
            guild_id=self.guild_id,
            author_id=self.author_id,
            metadata=self.metadata,
            job_id=self.job_id,
            timestamp=self.timestamp,
        )

    def short(self) -> str:
        """Short identifier for logs and error reports."""
        return f"{self.job_id[:6]}:{self.src or 'auto'}->{self.tgt}"
