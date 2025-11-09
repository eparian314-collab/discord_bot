#!/usr/bin/env bash
# Validate the environment file and required variables before launching HippoBot.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-${0}}")" && pwd)"

ENV_FILE="${1:-${PROJECT_DIR:-}/.env}"

if [[ ! -f "${ENV_FILE}" ]]; then
    printf '❌ Environment file not found: %s\n' "${ENV_FILE}"
    exit 1
fi

REQUIRED_VARS=(
    DISCORD_TOKEN
    RANKINGS_CHANNEL_ID
    DATABASE_PATH
    EVENT_DB_PATH
)

missing_vars=()
for var in "${REQUIRED_VARS[@]}"; do
    if ! grep -Eq "^${var}=" "${ENV_FILE}"; then
        missing_vars+=("${var}")
    fi
done

if [[ ${#missing_vars[@]} -gt 0 ]]; then
    printf '❌ Missing required environment variables: %s\n' "${missing_vars[*]}"
    exit 1
fi

perms="$(stat -c '%a' "${ENV_FILE}")"
if [[ "${perms}" != "600" ]]; then
    printf '⚠️ Adjusting permissions on %s to 600\n' "${ENV_FILE}"
    chmod 600 "${ENV_FILE}"
    perms=600
fi

printf '✅ Environment (%s) looks good (%s)\n' "${ENV_FILE}" "${perms}"
