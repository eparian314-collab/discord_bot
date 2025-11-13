#!/usr/bin/env bash
# Automated BFG Repo-Cleaner script to purge secrets from all branches in a git repo.
# Usage: bash purge_secrets_all_branches.sh

set -euo pipefail

REPO_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BFG_JAR="$REPO_PATH/bfg.jar"
# Expand list to cover both legacy and current names
SECRETS=(
  "DISCORD_TOKEN"
  "OPENAI_API_KEY"
  "OPEN_AI_API_KEY"
  "DEEPL_API_KEY"
  "MYMEMORY_USER_EMAIL"
  "MY_MEMORY_API_KEY"
)

cd "$REPO_PATH"

# Step 1: List all branches
BRANCHES=$(git for-each-ref --format='%(refname:short)' refs/heads/)

# Step 2: For each branch, checkout and run BFG
for BRANCH in $BRANCHES; do
    echo "[INFO] Purging secrets from branch: $BRANCH"
    git checkout "$BRANCH"
    java -jar "$BFG_JAR" --delete-files .env
    # Create a temp file for replace-text
    TMPFILE=$(mktemp)
    for SECRET in "${SECRETS[@]}"; do
        echo "$SECRET==REMOVED" >> "$TMPFILE"
    done
    java -jar "$BFG_JAR" --replace-text "$TMPFILE"
    rm "$TMPFILE"
    git reflog expire --expire=now --all
    git gc --prune=now --aggressive
    git push --force --set-upstream origin "$BRANCH"
    echo "[INFO] Branch $BRANCH cleaned and force-pushed."
done

echo "[SUCCESS] All branches have been purged of secrets and force-pushed."
