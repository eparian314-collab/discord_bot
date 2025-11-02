"""Compatibility shim for legacy ``discord_bot`` import path.

This project recently reorganized its top-level modules (e.g. ``core``,
``games``, ``integrations``) out of the nested ``discord_bot`` package.
Many parts of the codebase – including the test-suite – still import
modules via the old dotted path (``discord_bot.core.utils`` and so on).

To keep those imports working without having to touch every call-site at
once, we alias the new top-level packages back under ``discord_bot``.
This keeps the refactor incremental and avoids a breaking change.
"""

from __future__ import annotations

import importlib
import sys
from types import ModuleType
from typing import Iterable


def _register_aliases(base_package: ModuleType, names: Iterable[str]) -> None:
    """Alias ``names`` modules so ``discord_bot.<name>`` resolves."""

    for name in names:
        try:
            module = importlib.import_module(name)
        except ModuleNotFoundError:
            continue

        alias = f"{base_package.__name__}.{name}"
        sys.modules[alias] = module
        setattr(base_package, name, module)


_register_aliases(
    sys.modules[__name__],
    (
        "core",
        "cogs",
        "config",
        "deploy",
        "docs",
        "games",
        "integrations",
        "language_context",
        "scripts",
        "tests",
    ),
)

