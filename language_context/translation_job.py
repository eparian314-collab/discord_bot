from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Dict, Any
import time
import uuid


@dataclass(frozen=True)
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
    tgt: str
    src: Optional[str] = None
    guild_id: int = 0
    author_id: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    job_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    timestamp: float = field(default_factory=lambda: time.time())

    def with_src(self, new_src: str) -> "TranslationJob":
        """Return a copy of this job with a new source language."""
        return TranslationJob(
            text=self.text,
            tgt=self.tgt,
            src=new_src,
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
            tgt=new_tgt,
            src=self.src,
            guild_id=self.guild_id,
            author_id=self.author_id,
            metadata=self.metadata,
            job_id=self.job_id,
            timestamp=self.timestamp,
        )

    def short(self) -> str:
        """Short identifier for logs and error reports."""
        return f"{self.job_id[:6]}:{self.src or 'auto'}->{self.tgt}"
