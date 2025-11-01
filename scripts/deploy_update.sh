#!/usr/bin/env bash
# ===========================================================
# HippoBot Deployment + Launcher Script
#  - Pulls latest code from GitHub
#  - Loads/sanitises environment variables
#  - Ensures virtual environment & dependencies are current
#  - Runs pytest pre-flight checks
#  - Launches the bot (exec)
# ===========================================================

set -euo pipefail

log() {
    printf '[%(%Y-%m-%dT%H:%M:%S%z)T] %s\n' -1 "$*"
}

PROJECT_DIR="${PROJECT_DIR:-$HOME/discord_bot}"
VENV_DIR="${VENV_DIR:-${PROJECT_DIR}/.venv}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
REQUIREMENTS_FILE="${REQUIREMENTS_FILE:-${PROJECT_DIR}/requirements.txt}"
ENV_FILE="${ENV_FILE:-${PROJECT_DIR}/.env}"
PYTEST_ARGS="${PYTEST_ARGS:-}"

log "Starting deploy_update pipeline (project: ${PROJECT_DIR})"

cd "${PROJECT_DIR}"

# Load env (if present) so DISCORD_TOKEN et al become available.
if [[ -f "${ENV_FILE}" ]]; then
    log "Loading environment variables from ${ENV_FILE}"
    # shellcheck disable=SC1090
    source "${ENV_FILE}"
else
    log "WARNING: ${ENV_FILE} missing; relying on system environment."
fi

if [[ -z "${DISCORD_TOKEN:-}" ]]; then
    log "ERROR: DISCORD_TOKEN environment variable is required."
    exit 1
fi

log "Fetching latest code from origin"
git fetch --all --prune
git pull --ff-only || {
    log "ERROR: git pull failed"
    exit 1
}

if [[ ! -d "${VENV_DIR}" ]]; then
    log "Creating virtual environment at ${VENV_DIR}"
    "${PYTHON_BIN}" -m venv "${VENV_DIR}"
fi

# shellcheck disable=SC1091
source "${VENV_DIR}/bin/activate"

if [[ -f "${REQUIREMENTS_FILE}" ]]; then
    log "Installing/upgrading dependencies"
    python -m pip install --upgrade pip
    python -m pip install -r "${REQUIREMENTS_FILE}"
else
    log "WARNING: requirements.txt not found, skipping dependency install"
fi

log "Running pytest pre-flight checks"
if ! python -m pytest ${PYTEST_ARGS}; then
    log "ERROR: pytest failed, aborting launch."
    exit 1
fi

log "Running final simulation test before launch"
if ! python "${PROJECT_DIR}/scripts/simulation_test.py"; then
    log "ERROR: Simulation tests failed, aborting launch."
    exit 1
fi

log "Launching HippoBot"
exec python "${PROJECT_DIR}/main.py"

