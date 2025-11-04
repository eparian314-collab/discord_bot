"""Compatibility shim for legacy ``discord_bot`` import path.

This project recently reorganized its top-level modules (e.g. ``core``,
``games``, ``integrations``) out of the nested ``discord_bot`` package.
Many parts of the codebase - including the test-suite - still import
modules via the old dotted path (``discord_bot.core.utils`` and so on).

To keep those imports working without having to touch every call-site at
once, we alias the new top-level packages back under ``discord_bot``.
This keeps the refactor incremental and avoids a breaking change.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import ModuleType
from typing import Iterable


# Ensure the project root (one level above this package) is importable.
_package_dir = Path(__file__).resolve().parent
_project_root = _package_dir
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))
_repo_root = _package_dir.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))


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

try:
    import integrations as _integrations
    sys.modules[__name__ + '.integrations'] = _integrations
    integrations = _integrations
except ModuleNotFoundError:
    pass



