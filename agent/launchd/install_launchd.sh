#!/bin/bash
# Install / update the AI Tracking launchd agent for the current user.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
PLIST_SRC="$SCRIPT_DIR/com.happyxy.ai-tracking.plist"
PLIST_DST="${HOME}/Library/LaunchAgents/com.happyxy.ai-tracking.plist"
LABEL="com.happyxy.ai-tracking"

mkdir -p "${HOME}/Library/LaunchAgents" "${HOME}/Library/Logs"
chmod +x "$REPO_ROOT/agent/run.sh"

# Substitute paths into a user-local copy
sed \
  -e "s|__REPO_ROOT__|${REPO_ROOT}|g" \
  -e "s|__HOME__|${HOME}|g" \
  "$PLIST_SRC" > "$PLIST_DST"

# Reload if already loaded
if launchctl list "$LABEL" >/dev/null 2>&1; then
  launchctl unload "$PLIST_DST" 2>/dev/null || true
fi
launchctl load "$PLIST_DST"

echo "Installed $PLIST_DST"
echo "Schedule: daily 11:00 local time"
echo "Logs: ${HOME}/Library/Logs/ai-tracking.log"
echo "Manual run: $REPO_ROOT/agent/run.sh"
echo "Unload: launchctl unload $PLIST_DST"
