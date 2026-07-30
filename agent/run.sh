#!/bin/bash
# Wrapper for launchd / manual runs. Resolves repo root relative to this script.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_DIR="${HOME}/Library/Logs"
mkdir -p "$LOG_DIR"

cd "$REPO_ROOT"

if [[ -f "$REPO_ROOT/.venv/bin/python" ]]; then
  PYTHON="$REPO_ROOT/.venv/bin/python"
elif [[ -f "$REPO_ROOT/venv/bin/python" ]]; then
  PYTHON="$REPO_ROOT/venv/bin/python"
else
  PYTHON="$(command -v python3)"
fi

# Load .env if present (launchd does not source shell profiles)
if [[ -f "$REPO_ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$REPO_ROOT/.env"
  set +a
fi

exec "$PYTHON" "$REPO_ROOT/agent/run.py" "$@"
