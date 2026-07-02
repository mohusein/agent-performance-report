#!/bin/bash
# ─────────────────────────────────────────────
# Setup daily 6am cron job for Agent Performance Report
# Run once with: bash setup_scheduler.sh
# ─────────────────────────────────────────────

# Path to the email fetcher script — update this to match your Linux path
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FETCHER_SCRIPT="$SCRIPT_DIR/email_fetcher.py"
LOG_FILE="$SCRIPT_DIR/email_fetcher.log"
PYTHON_BIN="$(which python3)"

if [ -z "$PYTHON_BIN" ]; then
    echo "ERROR: python3 not found. Please install Python 3."
    exit 1
fi

echo "Using Python: $PYTHON_BIN"
echo "Script path: $FETCHER_SCRIPT"

# Build the cron line — runs every day at 6:00 AM
CRON_JOB="0 6 * * * $PYTHON_BIN $FETCHER_SCRIPT >> $LOG_FILE 2>&1"

# Check if cron job already exists
(crontab -l 2>/dev/null | grep -qF "$FETCHER_SCRIPT") && {
    echo "Cron job already exists. No changes made."
    exit 0
}

# Add the cron job
(crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -

if [ $? -eq 0 ]; then
    echo ""
    echo "SUCCESS: Cron job scheduled to run every day at 6:00 AM."
    echo "Entry added: $CRON_JOB"
    echo ""
    echo "To verify, run: crontab -l"
    echo "To remove it, run: crontab -e  (and delete the line)"
else
    echo "ERROR: Failed to install cron job."
    exit 1
fi
