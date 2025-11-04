#!/bin/bash
###############################################################################
# HippoBot Push & Deploy Script
# Pushes local changes to GitHub, runs local validation, and triggers deploy.
###############################################################################

set -euo pipefail

# Detect repository paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="${REPO_DIR_OVERRIDE:-$(dirname "$SCRIPT_DIR")}"

# Logging helpers
log_info()  { echo -e "\033[0;32m[INFO]\033[0m $1"; }
log_warn()  { echo -e "\033[1;33m[WARN]\033[0m $1"; }
log_error() { echo -e "\033[0;31m[ERROR]\033[0m $1"; }

# Python environment
VENV_PATH="$REPO_DIR/.venv"
if [ -d "$VENV_PATH" ]; then
    # shellcheck disable=SC1090
    source "$VENV_PATH/bin/activate"
    PYTHON="$VENV_PATH/bin/python"
else
    PYTHON="/usr/bin/python3"
    log_warn "Virtual environment not found, using system Python."
fi

# ---------------------------------------------------------------------------
# Guard rails
# ---------------------------------------------------------------------------
cd "$REPO_DIR"

if ! git rev-parse --git-dir >/dev/null 2>&1; then
    log_error "This script must be run inside a Git repository."
    exit 1
fi

current_branch="$(git rev-parse --abbrev-ref HEAD)"
if [ "$current_branch" = "HEAD" ]; then
    log_error "Detached HEAD state detected. Please checkout a branch before pushing."
    exit 1
fi

if ! git diff --quiet --ignore-submodules --exit-code; then
    log_error "Working tree has unstaged changes. Commit or stash them before deploying."
    git status --short
    exit 1
fi

if ! git diff --cached --quiet --ignore-submodules --exit-code; then
    log_error "You have staged but uncommitted changes. Commit them before deploying."
    git status --short
    exit 1
fi

# ---------------------------------------------------------------------------
# Push current branch
# ---------------------------------------------------------------------------
log_info "Pushing branch '$current_branch' to origin..."
git push origin "$current_branch"

# ---------------------------------------------------------------------------
# Local validation layers
# ---------------------------------------------------------------------------
log_info "Running local preflight checks..."
"$PYTHON" scripts/preflight_check.py

if "$PYTHON" -m pytest --version >/dev/null 2>&1; then
    log_info "Running pytest suite..."
    "$PYTHON" -m pytest tests/ -v --tb=short
else
    log_warn "pytest not available; skipping test suite."
fi

# ---------------------------------------------------------------------------
# Trigger deploy script (includes dependency install, health check, etc.)
# ---------------------------------------------------------------------------
DEPLOY_SCRIPT="$SCRIPT_DIR/deploy.sh"
if [ ! -x "$DEPLOY_SCRIPT" ]; then
    log_error "Deployment script '$DEPLOY_SCRIPT' is missing or not executable."
    exit 1
fi

log_info "Triggering deployment script for additional validation..."
"$DEPLOY_SCRIPT"

log_info "✔ Push and deployment pipeline completed successfully."
