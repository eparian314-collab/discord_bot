"""
Config loading utilities for HippoBot integrations.

Responsibilities:
 - Optionally hydrate environment variables from one or more `.env` files
 - Load structured defaults from `config.json` (or a supplied JSON path)
 - Respect existing environment variables unless explicit override requested
 - Provide a helper to assert required keys at startup
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Iterable, Mapping, MutableMapping, Optional, Sequence

try:
    from dotenv import load_dotenv as _load_dotenv  # type: ignore
    _HAS_DOTENV = True
except Exception:  # pragma: no cover - optional dependency
    _HAS_DOTENV = False


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_JSON_CANDIDATES: Sequence[Path] = (
    PROJECT_ROOT / "config" / "config.json",
    PROJECT_ROOT / "config.json",
)
DEFAULT_ENV_PATHS: Sequence[Path] = (
    PROJECT_ROOT / ".env",
    PROJECT_ROOT / "config" / ".env",
    PROJECT_ROOT.parent / ".env",
)


def _as_path(value: Optional[str | Path]) -> Optional[Path]:
    if value is None:
        return None
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = (PROJECT_ROOT / path).resolve()
    return path


def load_dotenv_files(paths: Optional[Iterable[str | Path]] = None) -> Sequence[Path]:
    """
    Load one or more .env files into os.environ (best-effort).
    Returns the collection of files that were successfully processed.
    """
    if not _HAS_DOTENV:
        return ()

    processed: list[Path] = []
    candidates = paths or DEFAULT_ENV_PATHS
    for raw in candidates:
        path = _as_path(raw)
        if not path or not path.exists():
            continue
        try:
            _load_dotenv(dotenv_path=str(path))
            processed.append(path)
        except Exception:
            # swallow errors; failing to load an env file should not abort startup
            continue
    return tuple(processed)


def load_json_config(
    json_path: Optional[str | Path] = None,
    *,
    force: bool = False,
    target: Optional[MutableMapping[str, str]] = None,
) -> Mapping[str, str]:
    """
    Load JSON configuration and merge scalar values into the target mapping.
    By default the target is os.environ. Existing keys are preserved unless `force` is True.
    Returns the values that were injected.
    """
    path = _as_path(json_path)
    if path is None:
        env_override = os.getenv("CONFIG_JSON")
        if env_override:
            path = _as_path(env_override)

    if path is None:
        for candidate in DEFAULT_JSON_CANDIDATES:
            if candidate.exists():
                path = candidate
                break

    if path is None:
        # Fall back to first candidate even if it does not yet exist (caller may generate it later)
        path = DEFAULT_JSON_CANDIDATES[0]
    if not path.exists():
        return {}

    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:
        return {}

    if not isinstance(data, dict):
        return {}

    env: MutableMapping[str, str] = target or os.environ  # type: ignore[assignment]
    injected: dict[str, str] = {}
    for key, value in data.items():
        if isinstance(value, (str, int, float, bool)):
            string_value = str(value)
            if force or env.get(key) is None:
                env[key] = string_value
                injected[key] = string_value
    return injected


def load_config(
    *,
    dotenv_paths: Optional[Iterable[str | Path]] = None,
    json_path: Optional[str | Path] = None,
    json_force: bool = False,
    load_dotenv_first: bool = True,
    target: Optional[MutableMapping[str, str]] = None,
) -> Mapping[str, str]:
    """
    High-level helper to load .env files and JSON configuration.

    Parameters:
        dotenv_paths: iterable of paths to .env files (defaults to project root fallbacks)
        json_path: path to config.json (defaults to repo-level config.json)
        json_force: overwrite existing values when loading JSON
        load_dotenv_first: whether to process .env files before JSON
        target: mapping to populate (defaults to os.environ)

    Returns:
        Mapping of JSON keys that were injected into the target.
    """
    combined_paths: Optional[Sequence[str | Path]] = None
    if dotenv_paths is not None:
        combined_paths = tuple(dotenv_paths)

    env_override = os.getenv("DOTENV_PATHS")
    if env_override:
        override_paths = tuple(p.strip() for p in env_override.split(os.pathsep) if p.strip())
        combined_paths = override_paths + tuple(combined_paths or ())

    if load_dotenv_first:
        load_dotenv_files(combined_paths)

    json_override = os.getenv("CONFIG_JSON") if json_path is None else None
    effective_json_path = json_path or json_override

    injected = load_json_config(effective_json_path, force=json_force, target=target)
    return injected


def require_keys(keys: Iterable[str], *, source: Optional[Mapping[str, str]] = None) -> None:
    """
    Validate that all required keys exist in the environment (or provided mapping).
    Raises RuntimeError listing any missing keys.
    """
    env = source or os.environ
    missing = [key for key in keys if env.get(key) is None]
    if missing:
        raise RuntimeError(f"Missing required environment keys: {', '.join(missing)}")
