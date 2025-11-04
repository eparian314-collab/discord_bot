"""
Context models used across the language_context package.

Purpose:
- Provide lightweight, serializable dataclasses for requests, responses,
  detection results, provider metadata, and job environment plumbing.
- Keep translation_job.py as the canonical TranslationJob (no duplication).
- Utility helpers for merging chunked responses and converting between
  TranslationJob -> TranslationRequest.

These models are intentionally small and dependency-free so they are easy to
mock and test.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

from discord_bot.language_context.translation_job import TranslationJob


@dataclass
class DetectionResult:
    """Result from a language detector."""
    lang: str
    confidence: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ProviderMeta:
    """Provider metadata attached to translation responses."""
    provider: Optional[str] = None  # e.g., "deepl", "mymemory"
    model: Optional[str] = None     # model id or version when applicable
    provider_info: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TranslationRequest:
    """
    High-level request passed into orchestrator services.

    Keep this small; orchestrator engines and processing pipeline can extend it
    through the `meta` free-form dict when needed.
    """
    guild_id: int
    user_id: int
    text: str
    src_hint: Optional[str] = None
    tgt_hint: Optional[str] = None
    force_tgt: Optional[str] = None
    pair: bool = False
    meta: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_job(cls, job: TranslationJob) -> "TranslationRequest":
        return cls(
            guild_id=job.guild_id,
            user_id=job.author_id,
            text=job.text,
            src_hint=job.src_lang,
            tgt_hint=job.tgt_lang,
            force_tgt=None,
            pair=False,
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TranslationResponse:
    """
    Structured translation response produced by adapters/orchestrator.

    Matches the project schema shape used elsewhere:
      {
        "text": "<translated string or null>",
        "src": "<detected src code>",
        "tgt": "<target code>",
        "provider": "<deepl|mymemory|null>",
        "confidence": 0.0,
        "meta": { "error": "...", "timings": {...}, "provider_info": {...} }
      }
    """
    text: Optional[str]
    src: str
    tgt: str
    provider: Optional[str] = None
    confidence: float = 0.0
    meta: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class JobEnvironment:
    """
    Wrapper for the dict returned by ContextEngine.plan_* helpers.
    Keeps the same semantics but gives a typed container for easier testing.
    """
    job: Optional[TranslationJob] = None
    context: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "JobEnvironment":
        return cls(job=d.get("job"), context=d.get("context", {}))

    def to_dict(self) -> Dict[str, Any]:
        return {"job": self.job, "context": self.context}


@dataclass
class ChunkedTranslation:
    """
    Result of chunking/streaming multi-part translations.
    `parts` should be in source order and will be joined by the orchestrator/UI.
    """
    parts: List[TranslationResponse] = field(default_factory=list)

    def join_text(self, sep: str = "\n\n") -> Optional[str]:
        texts = [p.text for p in self.parts if p and p.text]
        if not texts:
            return None
        return sep.join(texts)

    def combined_response(self) -> TranslationResponse:
        """
        Merge parts into a single TranslationResponse.
        - Joins texts with paragraph separation.
        - Keeps src/tgt from the first available part.
        - provider is set to the provider of the first successful part.
        - confidence is max confidence across parts.
        - meta aggregates timings and provider_info where present.
        """
        if not self.parts:
            return TranslationResponse(text=None, src="en", tgt="en", provider=None, confidence=0.0, meta={"error": "no_parts"})

        first = next((p for p in self.parts if p and p.text is not None), self.parts[0])
        joined = self.join_text()

        combined_meta: Dict[str, Any] = {"parts": len(self.parts), "timings": {}, "provider_info": {}}
        max_conf = 0.0
        for idx, p in enumerate(self.parts):
            if not p:
                continue
            # aggregate timings if present (sum elapsed where applicable)
            timings = (p.meta or {}).get("timings") or {}
            for k, v in timings.items():
                try:
                    combined_meta["timings"].setdefault(k, 0.0)
                    combined_meta["timings"][k] += float(v)
                except Exception:
                    # ignore non-numeric timing
                    pass
            # merge provider_info shallowly (later parts may overwrite)
            prov_info = (p.meta or {}).get("provider_info") or {}
            combined_meta["provider_info"].update(prov_info)
            if isinstance(p.confidence, (int, float)) and p.confidence > max_conf:
                max_conf = float(p.confidence)

        return TranslationResponse(
            text=joined,
            src=(first.src or "en"),
            tgt=(first.tgt or "en"),
            provider=(first.provider or None),
            confidence=max_conf,
            meta=combined_meta,
        )


