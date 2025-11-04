from __future__ import annotations

import logging
import sys
import time
import traceback
import contextvars
from contextlib import contextmanager
from typing import Any, Optional, Dict

# Context variable for correlation / request id propagation
_CORRELATION_ID: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("hippo_correlation_id", default=None)

# Internal flag to avoid reconfiguring logging repeatedly
_CONFIGURED = False

DEFAULT_PREFIX = "hippo_bot"


class ContextFilter(logging.Filter):
    """Attach correlation id to LogRecord as `correlation_id` for formatters."""

    def filter(self, record: logging.LogRecord) -> bool:  # type: ignore[override]
        record.correlation_id = _CORRELATION_ID.get() or "-"
        return True


class HippoFormatter(logging.Formatter):
    """Logging formatter that tolerates missing correlation_id values."""

    def format(self, record: logging.LogRecord) -> str:
        if not hasattr(record, "correlation_id"):
            record.correlation_id = _CORRELATION_ID.get() or "-"
        return super().format(record)


def configure_logging(
    *,
    level: int = logging.INFO,
    log_file: Optional[str] = None,
    force: bool = False,
    fmt: Optional[str] = None,
) -> None:
    """
    Configure root logging for the application.

    - level: logging level (DEBUG for verbose).
    - log_file: optional file path to write logs to (rotating or external file management recommended).
    - force: if True, reconfigure even if already configured (use carefully).
    - fmt: optional printf-style format. Default includes timestamp, level, name, corr-id.
    """
    global _CONFIGURED
    if _CONFIGURED and not force:
        return

    if fmt is None:
        fmt = "%(asctime)s %(levelname)-5s %(name)s [corr=%(correlation_id)s] %(message)s"

    handler_stream = logging.StreamHandler(stream=sys.stdout)
    handler_stream.setFormatter(HippoFormatter(fmt, datefmt="%Y-%m-%dT%H:%M:%S%z"))

    root = logging.getLogger()
    # Clear handlers if forcing a reconfigure
    if force:
        for h in list(root.handlers):
            try:
                root.removeHandler(h)
            except Exception:
                pass

    root.setLevel(level)
    root.addHandler(handler_stream)

    if log_file:
        try:
            fh = logging.FileHandler(log_file, encoding="utf-8")
            fh.setFormatter(HippoFormatter(fmt))
            root.addHandler(fh)
        except Exception:
            # don't fail startup if file cannot be created; emit to stdout instead
            root.exception("Failed to create log file handler, continuing without file logging")

    # Add ContextFilter globally so all loggers get correlation_id
    root.addFilter(ContextFilter())

    _CONFIGURED = True


def set_correlation_id(cid: Optional[str]) -> None:
    """
    Set a correlation/request id for the current context.
    Use once at the start of a request/interaction (e.g., in a Cog command or InputEngine handler).
    """
    _CORRELATION_ID.set(cid)


def get_correlation_id() -> Optional[str]:
    """Return current correlation id (or None)."""
    return _CORRELATION_ID.get()


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Returns a logger with a standard HippoBot prefix and ContextFilter attached.

    Usage:
        logger = get_logger("processing")
        logger.debug("Starting job", extra={"job_id": job.id})
    """
    prefix = DEFAULT_PREFIX
    full_name = f"{prefix}.{name}" if name else prefix
    logger = logging.getLogger(full_name)
    # Ensure filter exists on this logger (it's safe to add duplicates; logging dedups filters by object identity)
    if not any(isinstance(f, ContextFilter) for f in logger.filters):
        logger.addFilter(ContextFilter())
    return logger


def log_exception(logger: logging.Logger, exc: Exception, *, context: Optional[str] = None, extra: Optional[Dict[str, Any]] = None) -> None:
    """
    Log an exception with traceback and structured context.
    Use instead of bare logger.exception when you want extra metadata attached.

    Example:
        try:
            ...
        except Exception as e:
            log_exception(logger, e, context="processing.execute_job", extra={"job_id": job.id})
    """
    try:
        msg = f"Exception in {context or 'unknown'}: {type(exc).__name__}: {exc}"
        # attach stacktrace as well
        tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        if extra:
            logger.error("%s | extra=%r\n%s", msg, extra, tb)
        else:
            logger.error("%s\n%s", msg, tb)
    except Exception:
        # best-effort: fallback to logger.exception
        logger.exception("Failed to log exception in structured helper")


@contextmanager
def timed(logger: logging.Logger, action: str, *, level: int = logging.INFO, extra: Optional[Dict[str, Any]] = None):
    """
    Context manager to log elapsed time around an action.

    Usage:
        with timed(logger, "calling-deepl", extra={"provider":"deepl"}):
            await call_deepl(...)
    """
    start = time.monotonic()
    try:
        yield
    except Exception as exc:
        # Log the error with elapsed time included and re-raise
        elapsed = time.monotonic() - start
        msg = f"{action} failed after {elapsed:.3f}s"
        if extra:
            logger.exception("%s | extra=%r", msg, extra)
        else:
            logger.exception(msg)
        raise
    else:
        elapsed = time.monotonic() - start
        msg = f"{action} completed in {elapsed:.3f}s"
        if extra:
            logger.log(level, "%s | extra=%r", msg, extra)
        else:
            logger.log(level, msg)


# Convenience alias for quick use
default_logger = get_logger()


