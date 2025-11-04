"""
Discord Bot package - PEP 420 namespace package.

This directory serves as a namespace package to enable disco rd_bot.* imports.
The actual modules live in the parent directory.
"""
import sys
from pathlib import Path

# Add parent directory to sys.path to enable relative imports
_root = Path(__file__).parent.parent.resolve()
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))
