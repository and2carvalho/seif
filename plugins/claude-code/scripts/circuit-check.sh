#!/bin/bash
# SEIF Circuit Check — lightweight PreToolUse hook.
# Reads the alerts file and outputs any new alerts since last check.
# Designed to add <50ms overhead per tool call.

ALERTS_FILE="$HOME/.seif/circuit/alerts.txt"
LAST_CHECK_FILE="$HOME/.seif/circuit/last-alert-check"

# No alerts file = no alerts
if [ ! -f "$ALERTS_FILE" ]; then
  exit 0
fi

# Check if alerts file has content
ALERT_SIZE=$(stat -f%z "$ALERTS_FILE" 2>/dev/null || echo "0")
if [ "$ALERT_SIZE" = "0" ]; then
  exit 0
fi

# Get last check position
LAST_POS=0
if [ -f "$LAST_CHECK_FILE" ]; then
  LAST_POS=$(cat "$LAST_CHECK_FILE" 2>/dev/null || echo "0")
fi

# If file has grown since last check, show new alerts
CURRENT_SIZE=$(stat -f%z "$ALERTS_FILE" 2>/dev/null || echo "0")
if [ "$CURRENT_SIZE" -gt "$LAST_POS" ]; then
  # Show new alerts (tail from last position)
  tail -c +"$((LAST_POS + 1))" "$ALERTS_FILE" 2>/dev/null
  echo "$CURRENT_SIZE" > "$LAST_CHECK_FILE"
fi

exit 0
