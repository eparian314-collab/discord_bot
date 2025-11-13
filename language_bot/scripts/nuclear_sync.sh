#!/usr/bin/env bash
# Nuclear sync script for LanguageBot: clears old Discord tree commands and introduces the new bot.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LANG_ROOT="$PROJECT_ROOT/language_bot"
VENV_PATH="${VENV_PATH:-$PROJECT_ROOT/.venv}"

# Activate venv
source "$VENV_PATH/bin/activate"

# Step 1: Remove old Discord application commands (tree sync)
python3 "$LANG_ROOT/scripts/clear_discord_commands.py"

# Step 2: Register new commands for LanguageBot
python3 "$LANG_ROOT/scripts/register_discord_commands.py"

# Step 3: Start the bot
bash "$LANG_ROOT/ready_set_go.sh"
