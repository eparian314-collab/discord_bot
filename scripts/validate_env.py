#!/usr/bin/env python3
"""
Quick environment + dependency smoke test for HippoBot.
- Loads .env (if python-dotenv present) and JSON config via system_config.load_config
- Verifies required env keys
- Attempts to import adapters (DeepL/MyMemory/OpenAI) to catch missing libs
Exit codes:
  0 = ok, 1 = fatal
"""
from __future__ import annotations

import os
import sys
import importlib
from pathlib import Path

# load project config helper (optional)
try:
    from discord_bot.integrations.system_config import load_config, require_keys  # type: ignore
except Exception:
    load_config = None
    require_keys = None

ROOT = Path(__file__).resolve().parent.parent

def main() -> int:
    # Load .env and json config (non-destructive)
    if load_config:
        try:
            injected = load_config(load_dotenv_first=True)
            if injected:
                print("Injected config keys from JSON:", list(injected.keys()))
        except Exception as exc:
            print("Warning: load_config failed:", exc)

    # Required keys
    required = ["DISCORD_TOKEN"]
    # optional, but warn if missing
    optional = ["DEEPL_API_KEY", "OPENAI_API_KEY", "MYMEMORY_USER_EMAIL"]

    missing = [k for k in required if os.environ.get(k) is None]
    if missing:
        print("ERROR: Missing required env keys:", missing)
        return 1

    for k in optional:
        if os.environ.get(k) is None:
            print(f"Warning: optional key {k} not set (adapter may be disabled)")

    # Try import adapters to catch missing dependencies
    adapters = [
        ("DeepLAdapter", "discord_bot.language_context.translators.deepl_adapter"),
        ("MyMemoryAdapter", "discord_bot.language_context.translators.mymemory_adapter"),
        ("OpenAIAdapter", "discord_bot.language_context.translators.openai_adapter"),
    ]

    ok = True
    for name, mod in adapters:
        try:
            importlib.import_module(mod)
            print(f"Imported {mod} OK")
        except Exception as exc:
            print(f"Adapter import failed: {name} ({mod}): {exc}")
            ok = False

    if not ok:
        print("One or more adapters failed to import. Install requirements or fix adapter code.")
    else:
        print("Adapter import smoke-test PASSED")

    print("Environment validation complete. Ready to launch the bot.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
