"""
Compatibility package that exposes the existing top-level modules
(`core`, `cogs`, etc.) under the ``discord_bot`` namespace expected by tests.

The project historically treated the repository root as the import root, so
callers could do ``import core.utils``. Newer integrations (including the test
suite) use ``discord_bot.core.utils`` instead. Rather than moving large folder
trees, we provide lightweight aliases that forward imports to the existing
packages. This keeps the file structure unchanged while satisfying package
imports.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Iterable, Tuple

__all__: Tuple[str, ...] = (
    "bootstrap_aliases",
)


def _ensure_root_on_path() -> None:
    """Guarantee the repository root is importable when this package loads."""
    root = Path(__file__).resolve().parent.parent
    root_str = str(root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)


def _alias_package(name: str) -> None:
    """
    Import ``name`` (e.g. ``core``) and expose it as ``discord_bot.<name>``.

    We share the original module object rather than creating wrappers so that
    relative imports and package metadata continue to behave normally.
    """
    try:
        module = importlib.import_module(name)
    except ModuleNotFoundError:
        return

    alias = f"{__name__}.{name}"
    sys.modules[alias] = module
    setattr(sys.modules[__name__], name, module)


def bootstrap_aliases(targets: Iterable[str] | None = None) -> None:
    """
    Make commonly-used top-level packages available under ``discord_bot.*``.

    Parameters
    ----------
    targets:
        Optional iterable of package names to alias. Defaults to a curated list
        covering the modules referenced by the test suite.
    """
    _ensure_root_on_path()

    default_targets = (
        "core",
        "cogs",
        "config",
        "games",
        "integrations",
        "language_context",
        "scripts",
        "tests",
    )
    for name in (targets or default_targets):
        _alias_package(name)


# Run immediately so ``import discord_bot.core`` works without extra calls.
bootstrap_aliases()
