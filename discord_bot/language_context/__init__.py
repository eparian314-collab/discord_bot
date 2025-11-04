from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

__all__ = [
    "LanguageAliasHelper",
    "AmbiguityResolver",
    "HeuristicDetector",
    "NLPProcessor",
    "ContextEngine",
    "TranslationRequest",
    "TranslationResponse",
    "TranslationResult",
    "TranslationJob",
    "load_language_map",
    "context_utils",
]

# Defensive imports: prefer explicit names but tolerate missing/optional modules.
try:
    from .alias_helper import LanguageAliasHelper  # type: ignore
except Exception:
    LanguageAliasHelper = None  # type: ignore

try:
    from .ambiguity_resolver import AmbiguityResolver  # type: ignore
except Exception:
    AmbiguityResolver = None  # type: ignore

try:
    from .detectors.heuristics import HeuristicDetector  # type: ignore
except Exception:
    HeuristicDetector = None  # type: ignore

try:
    from .detectors.nlp_model import NLPProcessor  # type: ignore
except Exception:
    NLPProcessor = None  # type: ignore

try:
    from .context_engine import ContextEngine  # type: ignore
except Exception:
    ContextEngine = None  # type: ignore

# Context/DTO models
try:
    from .context_models import TranslationRequest, TranslationResponse  # type: ignore
except Exception:
    TranslationRequest = None  # type: ignore
    TranslationResponse = None  # type: ignore

# Base model translation result/dataclass
try:
    from .base_model import TranslationResult  # type: ignore
except Exception:
    TranslationResult = None  # type: ignore

# Keep TranslationJob import available (canonical job)
try:
    from .translation_job import TranslationJob  # type: ignore
except Exception:
    TranslationJob = None  # type: ignore

# Utility module
try:
    from . import context_utils  # type: ignore
except Exception:
    context_utils = None  # type: ignore


def load_language_map(path: Optional[Path] = None) -> Optional[dict]:
    """
    Load language_map.json from this package directory by default.
    Caches are intentionally not used here � caller may cache if desired.
    Returns parsed dict or None if file missing/invalid.
    """
    try:
        base = Path(__file__).parent
        p = Path(path) if path else base / "language_map.json"
        if not p.exists():
            return None
        with p.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return None

