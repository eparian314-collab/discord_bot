"""Root entry point shared by fun_bot and language_bot wrappers."""

from __future__ import annotations

import logging
import os

from dotenv import load_dotenv


logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


def main() -> None:
    load_dotenv()
    profile = os.getenv("BOT_PROFILE", "language").lower()
    if profile == "language":
        from language_bot.runner import run_language_bot

        run_language_bot()
    else:
        raise SystemExit(f"Unsupported BOT_PROFILE '{profile}' for this build")


if __name__ == "__main__":
    main()
