#!/usr/bin/env bash
# ============================================
# HippoBot Deployment Script
# - Pulls latest code
# - Updates dependencies
# - Runs tests
# - Does NOT launch (use deploy_loop.sh or the hippo service for launch)
# ============================================

set -euo pipefail

log() {
    printf '[%(%Y-%m-%dT%H:%M:%S%z)T] %s\n' -1 "$*"
}

PROJECT_DIR="${PROJECT_DIR:-/home/mars/projects/discord_bot}"
VENV_DIR="${VENV_DIR:-${PROJECT_DIR}/.venv}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
REQUIREMENTS_FILE="${REQUIREMENTS_FILE:-${PROJECT_DIR}/requirements.txt}"
ENV_FILE="${ENV_FILE:-${PROJECT_DIR}/.env}"
PYTEST_ARGS="${PYTEST_ARGS:--v --tb=short -x}"

log "Starting deployment pipeline (project: ${PROJECT_DIR})"

cd "${PROJECT_DIR}"

# Load env
if [[ -f "${ENV_FILE}" ]]; then
    log "Loading environment from ${ENV_FILE}"
    set -a
    # shellcheck disable=SC1090
    source "${ENV_FILE}"
    set +a
else
    log "WARNING: ${ENV_FILE} missing"
fi

if [[ -z "${DISCORD_TOKEN:-}" ]]; then
    log "ERROR: DISCORD_TOKEN required"
    exit 1
fi

# log "Fetching latest code from origin"
# git fetch --all --prune
# if git pull --ff-only; then
#     log "✅ Code updated successfully"
# else
#     log "⚠️  Git pull failed or conflicts detected"
#     exit 1
# fi

if [[ ! -d "${VENV_DIR}" ]]; then
    log "Creating virtual environment at ${VENV_DIR}"
    "${PYTHON_BIN}" -m venv "${VENV_DIR}"
fi

# shellcheck disable=SC1091
source "${VENV_DIR}/bin/activate"

if [[ -f "${REQUIREMENTS_FILE}" ]]; then
    log "Installing/upgrading dependencies"
    python -m pip install --upgrade pip -q
    python -m pip install -r "${REQUIREMENTS_FILE}" -q
else
    log "WARNING: requirements.txt not found"
fi

log "Running pytest pre-flight checks"
# Ensure the virtual environment's pytest is used
if "${VENV_DIR}/bin/pytest" ${PYTEST_ARGS}; then
    log "✅ All pytest tests passed"
else
    log "❌ Pytest failed - aborting"
    exit 1
fi

log "🎉 Deployment successful! Start the bot with ./scripts/deploy_loop.sh or via the hippo service."
