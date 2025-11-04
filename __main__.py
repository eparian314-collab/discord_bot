"""
Entry point for running the project as a module:
    python -m discord_bot
"""
from pathlib import Path
import sys

_current_file = Path(__file__).resolve()
_project_root = _current_file.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from main import main  # noqa: E402


if __name__ == "__main__":
    main()


