"""
Discord Bot namespace package bootstrapper.

This package intentionally mirrors modules that physically live at the repository
root (e.g. ``core/``, ``cogs/``).  By extending ``sys.path`` and the package
``__path__`` we let ``import discord_bot.core`` resolve without maintaining
duplicated directory trees.
"""
import sys
from pathlib import Path

_package_dir = Path(__file__).resolve().parent
_project_root = _package_dir.parent

root_str = str(_project_root)
if root_str not in sys.path:
    sys.path.insert(0, root_str)

# Allow submodule searches (discord_bot.core, discord_bot.cogs, ...) to fall
# back to the project root directories.
if root_str not in __path__:
    __path__.append(root_str)
