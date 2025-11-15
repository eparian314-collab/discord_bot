#!/usr/bin/env bash
# Hippo FunBot startup script with optional smoke checks (EC2/systemd friendly)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
FUN_ROOT="$PROJECT_ROOT/fun_bot"
VENV_PATH="${VENV_PATH:-$FUN_ROOT/.venv}"
RUN_TESTS=true
RUN_BOT=true
AUTO_GIT_PULL="${AUTO_GIT_PULL:-0}"

cd "$PROJECT_ROOT"
if [[ "$AUTO_GIT_PULL" == "1" ]]; then
  echo "[INFO] Pulling latest changes from git..."
  git pull --ff-only || echo "[WARNING] Git pull failed, continuing with current version."
fi

while [[ $# -gt 0 ]]; do
  case "$1" in
    --test-only) RUN_BOT=false ;;
    --skip-tests) RUN_TESTS=false ;;
    --help|-h)
      cat <<'EOF'
Usage: ready_set_go.sh [--test-only] [--skip-tests]
  --test-only   Run compile + unit tests but do not start the bot.
  --skip-tests  Launch the bot immediately without running tests.
Env:
  VENV_PATH       Custom venv directory (default ../.venv)
  SKIP_PIP_INSTALL  When set to 1, skip dependency installation.
  AUTO_GIT_PULL   When set to 1, git pull before starting (off by default).
EOF
      exit 0
      ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
  shift
done

if [[ ! -d "$VENV_PATH" ]]; then
  python3 -m venv "$VENV_PATH"
fi
source "$VENV_PATH/bin/activate"

if [[ "${SKIP_PIP_INSTALL:-0}" != "1" ]]; then
  python3 -m pip install --upgrade pip >/dev/null
  # FunBot has minimal deps; keep budget low
  if [[ -f "$FUN_ROOT/requirements.txt" ]]; then
    python3 -m pip install -r "$FUN_ROOT/requirements.txt"
  else
    python3 -m pip install discord.py python-dotenv
  fi
fi

if [[ "$RUN_TESTS" == true ]]; then
  python3 -m compileall "$FUN_ROOT"
  if command -v pytest >/dev/null 2>&1 && [[ -d "$FUN_ROOT/tests" ]]; then
    python3 -m pytest --maxfail=1 --disable-warnings -v "$FUN_ROOT/tests" || {
      echo "[ERROR] Pytest failed. Aborting startup."; exit 1; }
  fi
fi

if [[ "$RUN_BOT" == true ]]; then
  cd "$FUN_ROOT"
  while true; do
    python3 main.py
    status=$?
    if [[ $status -eq 0 ]]; then
      echo "[INFO] FunBot exited normally."; break
    else
      echo "[ERROR] FunBot crashed with exit code $status. Restarting in 10 seconds..."; sleep 10
    fi
  done
fi
