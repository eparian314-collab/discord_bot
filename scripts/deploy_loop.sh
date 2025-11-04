#!/bin/bash
# Automated deployment loop for HippoBot
# Launches bot and monitors for stability, restarting on failures

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# Configuration
LOG_DIR="$PROJECT_ROOT/logs"
NOHUP_LOG="$LOG_DIR/nohup.out"
ERROR_LOG="$LOG_DIR/errors.log"
DEPLOY_LOG="$LOG_DIR/deployment.log"
PID_FILE="$LOG_DIR/hippobot.pid"
MAX_RESTARTS=3
STABLE_RUNTIME=300  # 5 minutes = stable
VENV_PATH="$PROJECT_ROOT/.venv"

# Colors
GREEN="\033[92m"
RED="\033[91m"
YELLOW="\033[93m"
BLUE="\033[94m"
RESET="\033[0m"

# Logging function
log() {
    echo -e "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$DEPLOY_LOG"
}

log_error() {
    echo -e "${RED}[ERROR]${RESET} $1" | tee -a "$DEPLOY_LOG" "$ERROR_LOG"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${RESET} $1" | tee -a "$DEPLOY_LOG"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${RESET} $1" | tee -a "$DEPLOY_LOG"
}

log_info() {
    echo -e "${BLUE}[INFO]${RESET} $1" | tee -a "$DEPLOY_LOG"
}

# Ensure log directory exists
mkdir -p "$LOG_DIR"

# Check if bot is already running
check_running() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            return 0  # Running
        fi
    fi
    return 1  # Not running
}

# Stop existing bot instance
stop_bot() {
    if check_running; then
        PID=$(cat "$PID_FILE")
        log_info "Stopping bot (PID: $PID)..."
        kill "$PID" 2>/dev/null || true
        sleep 2
        
        # Force kill if still running
        if ps -p "$PID" > /dev/null 2>&1; then
            log_warning "Force killing bot..."
            kill -9 "$PID" 2>/dev/null || true
        fi
        
        rm -f "$PID_FILE"
        log_success "Bot stopped"
    fi
}

# Run preflight checks
run_preflight() {
    log_info "Running preflight checks..."
    
    # Activate venv
    if [ -f "$VENV_PATH/bin/activate" ]; then
        source "$VENV_PATH/bin/activate"
    else
        log_error "Virtual environment not found: $VENV_PATH"
        return 1
    fi
    
    # Check environment
    if ! python3 "$PROJECT_ROOT/scripts/check_env.py"; then
        log_error "Environment check failed"
        return 1
    fi
    
    # Check module integrity
    if ! python3 "$PROJECT_ROOT/scripts/test_module_integrity.py"; then
        log_error "Module integrity check failed"
        return 1
    fi
    
    log_success "Preflight checks passed"
    return 0
}

# Start bot
start_bot() {
    log_info "Starting bot..."
    
    # Activate venv
    source "$VENV_PATH/bin/activate"
    
    # Clear old nohup log
    > "$NOHUP_LOG"
    
    # Start bot in background
    nohup python3 -m discord_bot.main > "$NOHUP_LOG" 2>&1 &
    BOT_PID=$!
    
    echo "$BOT_PID" > "$PID_FILE"
    log_success "Bot started (PID: $BOT_PID)"
    
    return 0
}

# Check if bot is stable
check_stability() {
    local runtime=$1
    
    if [ $runtime -lt $STABLE_RUNTIME ]; then
        return 1  # Not yet stable
    fi
    
    # Check for recent errors in log
    if grep -i "error\|exception\|traceback" "$NOHUP_LOG" | tail -20 | grep -q "$(date '+%Y-%m-%d')"; then
        log_warning "Recent errors detected in logs"
        return 1
    fi
    
    return 0  # Stable
}

# Main deployment loop
deploy() {
    local restart_count=0
    local stable_count=0
    
    log_info "Starting deployment loop..."
    log_info "Max restarts: $MAX_RESTARTS"
    log_info "Stable runtime threshold: ${STABLE_RUNTIME}s"
    
    # Stop any existing instance
    stop_bot
    
    # Run preflight checks
    if ! run_preflight; then
        log_error "Preflight checks failed. Aborting deployment."
        return 1
    fi
    
    while [ $restart_count -lt $MAX_RESTARTS ]; do
        log_info "Deployment attempt $((restart_count + 1))/$MAX_RESTARTS"
        
        # Start bot
        if ! start_bot; then
            log_error "Failed to start bot"
            return 1
        fi
        
        # Monitor bot
        START_TIME=$(date +%s)
        
        while check_running; do
            CURRENT_TIME=$(date +%s)
            RUNTIME=$((CURRENT_TIME - START_TIME))
            
            # Check if stable
            if check_stability $RUNTIME; then
                stable_count=$((stable_count + 1))
                log_success "Bot stable for ${RUNTIME}s (stability check: $stable_count)"
                
                if [ $stable_count -ge 3 ]; then
                    log_success "Bot achieved stable state after $stable_count checks!"
                    log_success "Deployment successful. Bot is running."
                    return 0
                fi
            fi
            
            # Show progress
            if [ $((RUNTIME % 60)) -eq 0 ]; then
                log_info "Runtime: ${RUNTIME}s"
            fi
            
            sleep 10
        done
        
        # Bot stopped unexpectedly
        RUNTIME=$(($(date +%s) - START_TIME))
        log_error "Bot stopped after ${RUNTIME}s"
        
        # Check logs for errors
        log_warning "Last 20 lines of log:"
        tail -20 "$NOHUP_LOG" | tee -a "$DEPLOY_LOG"
        
        restart_count=$((restart_count + 1))
        stable_count=0
        
        if [ $restart_count -lt $MAX_RESTARTS ]; then
            log_warning "Restarting bot (attempt $((restart_count + 1))/$MAX_RESTARTS)..."
            sleep 5
        fi
    done
    
    log_error "Max restarts reached ($MAX_RESTARTS). Deployment failed."
    return 1
}

# Command handling
case "${1:-deploy}" in
    deploy)
        deploy
        ;;
    start)
        if check_running; then
            log_warning "Bot is already running"
            exit 0
        fi
        run_preflight && start_bot
        ;;
    stop)
        stop_bot
        ;;
    restart)
        stop_bot
        sleep 2
        run_preflight && start_bot
        ;;
    status)
        if check_running; then
            PID=$(cat "$PID_FILE")
            log_info "Bot is running (PID: $PID)"
            ps -p "$PID" -o pid,etime,cmd
        else
            log_info "Bot is not running"
        fi
        ;;
    logs)
        tail -f "$NOHUP_LOG"
        ;;
    *)
        echo "Usage: $0 {deploy|start|stop|restart|status|logs}"
        exit 1
        ;;
esac
