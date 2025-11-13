#!/usr/bin/env bash
# Blocks commits that include obvious secrets in staged changes.
# Usage: ln -sf ../../scripts/precommit_secret_guard.sh .git/hooks/pre-commit

set -euo pipefail

patterns=(
  'DISCORD_TOKEN='
  'OPENAI_API_KEY='
  'OPEN_AI_API_KEY='
  'DEEPL_API_KEY='
  'MY_MEMORY_API_KEY='
  'MYMEMORY_USER_EMAIL='
  'sk-[A-Za-z0-9]+'
  'AKIA[0-9A-Z]+'
  'AIza[0-9A-Za-z-_]+'
)

staged=$(git diff --cached -U0)
if [[ -z "$staged" ]]; then
  exit 0
fi

failed=0
for pat in "${patterns[@]}"; do
  if echo "$staged" | grep -E "^\+.*$pat" >/dev/null 2>&1; then
    echo "[SECRET GUARD] Detected potential secret in staged changes matching: $pat" >&2
    failed=1
  fi
done

if [[ $failed -eq 1 ]]; then
  echo "[SECRET GUARD] Commit aborted. Remove secrets from tracked files (use .env)." >&2
  exit 1
fi

exit 0

