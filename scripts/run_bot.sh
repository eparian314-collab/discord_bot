#!/usr/bin/env bash
# ============================================
# HippoBot Runner (No Deploy Logic)
# Just runs the bot - safe for systemd restart
# ============================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

log() {
    printf '[%(%Y-%m-%dT%H:%M:%S%z)T] %s\n' -1 "$*"
}

PROJECT_DIR="${PROJECT_DIR:-/home/mars/projects/discord_bot}"
VENV_DIR="${VENV_DIR:-${PROJECT_DIR}/.venv}"
ENV_FILE="${ENV_FILE:-${PROJECT_DIR}/.env}"

log "Starting HippoBot from ${PROJECT_DIR}"

cd "${PROJECT_DIR}"

# Load environment variables
if [[ -f "${ENV_FILE}" ]]; then
    if [[ -x "${SCRIPT_DIR}/validate_env.sh" ]]; then
        "${SCRIPT_DIR}/validate_env.sh" "${ENV_FILE}"
    fi

    log "Loading environment from ${ENV_FILE}"
    # shellcheck disable=SC1090
    set -a
    source "${ENV_FILE}"
    set +a
else
    log "WARNING: ${ENV_FILE} not found"
fi

if [[ -z "${DISCORD_TOKEN:-}" ]]; then
    log "ERROR: DISCORD_TOKEN not set"
    exit 1
fi

# Activate venv
if [[ -f "${VENV_DIR}/bin/activate" ]]; then
    # shellcheck disable=SC1091
    source "${VENV_DIR}/bin/activate"
else
    log "ERROR: Virtual environment not found at ${VENV_DIR}"
    exit 1
fi

log "Launching bot..."
exec python3 main.py
