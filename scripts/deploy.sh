#!/bin/bash
###############################################################################
# HippoBot Deployment Script
# This script pulls latest code, runs tests, and deploys the bot safely
###############################################################################

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration

REPO_DIR="/home/ec2-user/discord_bot"
VENV_PATH="$REPO_DIR/venv"
if [ -d "$VENV_PATH" ]; then
    source "$VENV_PATH/bin/activate"
    PYTHON="$VENV_PATH/bin/python"
else
    PYTHON="/usr/bin/python3"
    log_warn "Virtual environment not found, using system Python."
fi
MAX_RETRIES=3
RETRY_COUNT_FILE="/tmp/hippobot_retry_count"
COOLDOWN_FILE="/tmp/hippobot_cooldown"
COOLDOWN_DURATION=300  # 5 minutes in seconds

###############################################################################
# Helper Functions
###############################################################################

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_cooldown() {
    if [ -f "$COOLDOWN_FILE" ]; then
        cooldown_start=$(cat "$COOLDOWN_FILE")
        current_time=$(date +%s)
        elapsed=$((current_time - cooldown_start))
        
        if [ $elapsed -lt $COOLDOWN_DURATION ]; then
            remaining=$((COOLDOWN_DURATION - elapsed))
            log_error "Deployment in cooldown. Wait $remaining seconds."
            exit 1
        else
            rm -f "$COOLDOWN_FILE"
            rm -f "$RETRY_COUNT_FILE"
        fi
    fi
}

increment_retry_count() {
    if [ -f "$RETRY_COUNT_FILE" ]; then
        retry_count=$(cat "$RETRY_COUNT_FILE")
        retry_count=$((retry_count + 1))
    else
        retry_count=1
    fi
    
    echo "$retry_count" > "$RETRY_COUNT_FILE"
    
    if [ $retry_count -ge $MAX_RETRIES ]; then
        log_error "Max retries ($MAX_RETRIES) reached. Entering cooldown."
        date +%s > "$COOLDOWN_FILE"
        exit 1
    fi
    
    log_warn "Retry count: $retry_count/$MAX_RETRIES"
}

reset_retry_count() {
    rm -f "$RETRY_COUNT_FILE"
    rm -f "$COOLDOWN_FILE"
}

###############################################################################
# Deployment Steps
###############################################################################

deploy() {
    log_info "Starting HippoBot deployment..."
    
    # Check cooldown
    check_cooldown
    
    # Change to repo directory
    cd "$REPO_DIR" || exit 1
    
    # Pull latest code
    log_info "Pulling latest code from GitHub..."
    if ! git pull origin main; then
        log_error "Git pull failed"
        increment_retry_count
        exit 1
    fi
    
    # Run preflight checks
    log_info "Running preflight checks..."
    if ! $PYTHON scripts/preflight_check.py; then
        log_error "Preflight checks failed"
        increment_retry_count
        exit 1
    fi
    
    # Install/update dependencies
    log_info "Checking dependencies..."
    if ! pip3 install -r requirements.txt --quiet; then
        log_error "Dependency installation failed"
        increment_retry_count
        exit 1
    fi
    
    # Run tests (if pytest is available)
    if command -v pytest &> /dev/null; then
        log_info "Running tests..."
        if ! pytest tests/ -v --tb=short; then
            log_error "Tests failed"
            increment_retry_count
            exit 1
        fi
    else
        log_warn "pytest not found, skipping tests"
    fi
    
    # Run health check
    log_info "Running health check..."
    if ! $PYTHON health_check.py; then
        log_error "Health check failed"
        increment_retry_count
        exit 1
    fi
    
    # All checks passed
    log_info "All deployment checks passed!"
    reset_retry_count
    
    return 0
}

###############################################################################
# Main
###############################################################################

# Trap errors
trap 'log_error "Deployment failed at line $LINENO"' ERR

# Run deployment
if deploy; then
    log_info "✅ Deployment successful! Bot is ready to start."
    exit 0
else
    log_error "❌ Deployment failed!"
    exit 1
fi
