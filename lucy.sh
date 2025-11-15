#!/usr/bin/env bash
# Lucy launcher script for FunBot from the repo root.
# - Creates/uses a virtualenv in fun_bot/.venv (not in root)
# - Installs fun_bot requirements
# - Launches FunBot
#
# Usage (from discord_bot repo root):
#   bash lucy.sh
# or (if executable):
#   ./lucy.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FUN_ROOT="$SCRIPT_DIR/fun_bot"
VENV_PATH="$FUN_ROOT/.venv"

cd "$FUN_ROOT"

if [[ ! -d "$VENV_PATH" ]]; then
  echo "[Lucy] Creating virtualenv at $VENV_PATH"
  python3 -m venv "$VENV_PATH"
fi

echo "[Lucy] Activating virtualenv..."
source "$VENV_PATH/bin/activate"

if [[ -f "requirements.txt" ]]; then
  echo "[Lucy] Ensuring requirements are installed..."
  python -m pip install -r requirements.txt
fi

echo "[Lucy] Launching FunBot..."
python main.py

