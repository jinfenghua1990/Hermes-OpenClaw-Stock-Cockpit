#!/bin/bash
# Auto-sync to GitHub every day at 1:00 AM
# Retry after 1 hour if failed

REPO_DIR="/Users/gino/project_ai_trading"
LOG_FILE="$REPO_DIR/.git/auto_sync.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

cd "$REPO_DIR" || exit 1

log "Starting auto-sync..."

# Check for uncommitted changes
if [[ -n $(git status --porcelain) ]]; then
    git add -A
    git commit -m "auto-sync: $(date '+%Y-%m-%d %H:%M:%S')"
    log "Uncommitted changes committed"
fi

# Try to push
MAX_RETRIES=2
RETRY_DELAY=3600  # 1 hour in seconds

for i in $(seq 1 $MAX_RETRIES); do
    if git push origin main 2>&1 | tee -a "$LOG_FILE"; then
        log "SUCCESS: Pushed to GitHub"
        exit 0
    else
        log "FAILED: Attempt $i/$MAX_RETRIES"
        if [ $i -lt $MAX_RETRIES ]; then
            log "Retrying in $RETRY_DELAY seconds..."
            sleep $RETRY_DELAY
        fi
    fi
done

log "ERROR: All retry attempts failed"
exit 1
