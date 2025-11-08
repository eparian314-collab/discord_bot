"""
Ensure that .env.example exports the minimum configuration expected by CI/CD.

Checks are intentionally lightweight so they can run inside GitHub Actions
without additional dependencies.
"""

from __future__ import annotations

from pathlib import Path
import sys

REQUIRED_KEYS = ("BOT_CHANNEL_ID", "RANKINGS_CHANNEL_ID", "ENABLE_OCR_TRAINING")


def parse_env_file(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key.strip()] = value.strip()
    return data


def main() -> int:
    env_path = Path(".env.example")
    if not env_path.exists():
        print("Missing .env.example at repository root", file=sys.stderr)
        return 1

    values = parse_env_file(env_path)
    missing = [key for key in REQUIRED_KEYS if key not in values]
    if missing:
        print(
            "Missing required keys in .env.example: " + ", ".join(sorted(missing)),
            file=sys.stderr,
        )
        return 1

    print(
        "Validated .env.example keys: "
        + ", ".join(f"{key}={values.get(key, '') or '<placeholder>'}" for key in REQUIRED_KEYS)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
