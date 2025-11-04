from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Tuple

@dataclass(frozen=True)
class LanguageProfile:
    name: str
    locale_code: str
    default_prompts: Dict[str, str] = field(default_factory=dict)
    fallbacks: Tuple[str, ...] = field(default_factory=tuple)


