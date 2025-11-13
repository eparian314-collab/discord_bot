#!/usr/bin/env bash
# Unified bootstrap script for LanguageBot runtime + smoke checks.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LANG_ROOT="$PROJECT_ROOT/language_bot"
VENV_PATH="${VENV_PATH:-$PROJECT_ROOT/.venv}"
RUN_TESTS=true
RUN_BOT=true

# Auto-update: Pull latest changes from git
cd "$PROJECT_ROOT"
echo "[INFO] Pulling latest changes from git..."
git pull origin main || echo "[WARNING] Git pull failed, continuing with current version."

while [[ $# -gt 0 ]]; do
    case "$1" in
        --test-only)
            RUN_BOT=false
            ;;
        --skip-tests)
            RUN_TESTS=false
            ;;
        --help|-h)
            cat <<'EOF'
Usage: ready_set_go.sh [--test-only] [--skip-tests]
  --test-only   Run smoke checks (compile + unit tests) but do not start the bot.
  --skip-tests  Launch the bot immediately without running smoke checks.
  -h, --help    Show this help message.
Environment overrides:
  VENV_PATH         Custom virtual environment directory (default ../.venv)
  SKIP_PIP_INSTALL  When set to 1, skip the dependency installation step.
EOF
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            exit 1
            ;;
    esac
    shift
done

if [[ ! -d "$VENV_PATH" ]]; then
    python3 -m venv "$VENV_PATH"
fi

# Always activate venv before running anything
source "$VENV_PATH/bin/activate"

if ! command -v pytest &> /dev/null; then
    echo "[INFO] Installing pytest in venv..."
    pip install pytest
fi

if [[ "${SKIP_PIP_INSTALL:-0}" != "1" ]]; then
    python3 -m pip install --upgrade pip >/dev/null
    python3 -m pip install -r "$LANG_ROOT/requirements.txt"
fi

if [[ "$RUN_TESTS" == true ]]; then
    python3 -m compileall "$LANG_ROOT"
    python3 -m pytest --maxfail=1 --disable-warnings -v "$LANG_ROOT/tests"
    if [[ $? -ne 0 ]]; then
        echo "[ERROR] Pytest failed. Aborting startup."
        exit 1
    fi
    # Run full simulation suite
    python3 -m pytest "$LANG_ROOT/tests/test_full_simulation.py" --maxfail=1 --disable-warnings -v
    if [[ $? -ne 0 ]]; then
        echo "[ERROR] Full simulation test failed. Aborting startup."
        exit 1
    fi
fi

if [[ "$RUN_BOT" == true ]]; then
    cd "$LANG_ROOT"
    while true; do
        python3 main.py
        status=$?
        if [ $status -eq 0 ]; then
            echo "[INFO] Bot exited normally."
            break
        else
            echo "[ERROR] Bot crashed with exit code $status. Restarting in 10 seconds..."
            sleep 10
        fi
        # Optional: Add a max restart count or notification here
    done
fi
