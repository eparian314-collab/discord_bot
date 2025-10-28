"""
HippoBot entry point.

Environment:
    set DISCORD_TOKEN=...
    set OWNER_IDS=1234567890,9876543210  (optional)
    set TEST_GUILDS=111222222222         (optional)

Run:
    python -m discord_bot.main
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
import uuid
from pathlib import Path
from typing import Mapping

# Ensure parent directory is in path for proper package imports
_current_file = Path(__file__).resolve()
_project_root = _current_file.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from discord_bot.core.engines.base.logging_utils import (
    configure_logging,
    get_logger,
    set_correlation_id,
)
from discord_bot.integrations import build_application, load_config, require_keys

from discord_bot.scripts.sanitize_encoding import run as sanitize

# Ensure source files are consistently decoded (safe no-op if already clean).
# Use verbose=False for clean startup logs
sanitize(verbose=False)

logger = get_logger("main")

SENSITIVE_KEYS = {
    "DISCORD_TOKEN",
    "DEEPL_API_KEY",
    "OPENAI_API_KEY",
    "MYMEMORY_USER_EMAIL",
}


def _mask(value: str, *, show: int = 4) -> str:
    """Return a masked representation of a secret-like value."""
    if not value:
        return "<empty>"
    if len(value) <= show:
        return "*" * len(value)
    return f"{value[:show]}...{value[-show:]}"


def run_preflight_checks(injected: Mapping[str, str]) -> None:
    """
    Perform light-weight sanity checks prior to booting the bot.

    Intentionally avoids mutating global state; purely diagnostic.
    """
    missing: list[str] = []
    masked_env: dict[str, str] = {}

    for key in ("DISCORD_TOKEN", "OWNER_IDS", "TEST_GUILDS"):
        raw = os.getenv(key)
        if not raw:
            if key == "DISCORD_TOKEN":
                missing.append(key)
            continue

        if key in SENSITIVE_KEYS:
            masked_env[key] = _mask(raw)
        else:
            masked_env[key] = raw

    if missing:
        logger.warning("Preflight missing required environment variables: %s", ", ".join(missing))

    if masked_env:
        logger.debug("Preflight environment snapshot (sanitised): %s", masked_env)

    if injected:
        redacted = {k: (_mask(v) if k in SENSITIVE_KEYS else v) for k, v in injected.items()}
        logger.debug("Preflight JSON configuration injected keys: %s", redacted)

    config_json = os.getenv("CONFIG_JSON")
    if config_json:
        path = Path(config_json)
        if not path.exists():
            logger.warning("Preflight: CONFIG_JSON points to missing file: %s", path)


def configure_logging_from_env() -> None:
    """Configure logging based on LOG_LEVEL / LOG_FILE environment variables."""
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    # Map provided level to logging numeric constant; default to INFO on errors.
    try:
        level = int(level_name) if level_name.isdigit() else getattr(logging, level_name, logging.INFO)
    except Exception:
        level = logging.INFO

    log_file = os.getenv("LOG_FILE")
    # Do not force reconfiguration to respect libs/tests that preconfigure logging.
    configure_logging(level=level, log_file=log_file, force=False)

    # Reduce discord library chatter unless debugging.
    if level > logging.DEBUG:
        logging.getLogger("discord").setLevel(logging.WARNING)
    logger.debug("Logging configured (level=%s%s)", level_name, f", file={log_file}" if log_file else "")


async def _amain() -> None:
    try:
        injected = load_config()
    except Exception as exc:
        # Logging may not be configured yet; write to stdout and continue.
        print("Warning: load_config() failed:", exc)
        injected = {}

    configure_logging_from_env()
    run_preflight_checks(injected)

    try:
        require_keys(["DISCORD_TOKEN"])
    except Exception as exc:
        logger.critical("Missing required configuration: %s", exc)
        raise

    instance_id = os.getenv("INSTANCE_ID") or uuid.uuid4().hex
    set_correlation_id(instance_id)
    logger.info("🚀 Starting HippoBot (instance=%s)", instance_id)

    try:
        bot, _registry = build_application()
    except Exception:
        logger.exception("Failed to build application stack")
        raise

    token = os.getenv("DISCORD_TOKEN")
    if not token:
        logger.critical("DISCORD_TOKEN not set after configuration load")
        raise RuntimeError("DISCORD_TOKEN not set")

    try:
        await bot.start(token)
    except KeyboardInterrupt:
        logger.warning("⏹️ Keyboard interrupt received, shutting down...")
    except Exception:
        logger.exception("Unhandled exception in bot.start()")
        raise
    finally:
        try:
            await bot.close()
        except Exception:
            logger.exception("Error while closing bot")
        logger.info("🛑 HippoBot shut down cleanly.")


def main() -> None:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(_amain())


if __name__ == "__main__":
    main()
