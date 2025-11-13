"""Logging helpers that keep configuration consistent across modules."""

from __future__ import annotations

import logging
from typing import Iterable, Optional

DEFAULT_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


def configure_library_logging(
    *,
    level: int = logging.INFO,
    fmt: str = DEFAULT_FORMAT,
    handlers: Optional[Iterable[logging.Handler]] = None,
) -> logging.Logger:
    """Return a logger configured with the common format."""

    logger = logging.getLogger("language_bot")
    logger.setLevel(level)
    logger.handlers.clear()

    if handlers:
        for handler in handlers:
            handler.setFormatter(logging.Formatter(fmt))
            logger.addHandler(handler)
    else:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(fmt))
        logger.addHandler(handler)

    logger.propagate = False
    return logger


def get_logger(name: str) -> logging.Logger:
    """Shortcut that returns a namespaced child logger."""

    parent = logging.getLogger("language_bot")
    return parent.getChild(name)


__all__ = ["configure_library_logging", "get_logger"]
