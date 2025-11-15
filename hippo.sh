#!/usr/bin/env bash
# Hippo launcher script for LanguageBot from the repo root.
# - Creates/uses a virtualenv in language_bot/.venv
# - Installs LanguageBot requirements
# - Launches LanguageBot
#
# Usage (from discord_bot repo root):
#   bash hippo.sh
# or (after making executable):
#   ./hippo.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LANG_ROOT="$SCRIPT_DIR/language_bot"
VENV_PATH="$LANG_ROOT/.venv"

cd "$LANG_ROOT"

if [[ ! -d "$VENV_PATH" ]]; then
  echo "[Hippo] Creating virtualenv at $VENV_PATH"
  python3 -m venv "$VENV_PATH"
fi

echo "[Hippo] Activating virtualenv..."
source "$VENV_PATH/bin/activate"

if [[ -f "requirements.txt" ]]; then
  if [[ "${HIPPO_SKIP_PIP_INSTALL:-0}" != "1" ]]; then
    echo "[Hippo] Ensuring requirements are installed (quiet)..."
    python -m pip install --disable-pip-version-check -q -r requirements.txt
  else
    echo "[Hippo] Skipping pip install because HIPPO_SKIP_PIP_INSTALL=1"
  fi
fi

echo "[Hippo] Launching LanguageBot (module mode)..."
cd "$SCRIPT_DIR"
python -m language_bot.main
