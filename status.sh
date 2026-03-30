#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_NAME="aio-dynamic-push"
LOG_FILE="$PROJECT_DIR/aio-dynamic-push.log"

cd "$PROJECT_DIR"

echo "== Runtime Status =="
if command -v systemctl >/dev/null 2>&1 && systemctl list-unit-files | grep -q "^${SERVICE_NAME}\\.service"; then
  if systemctl is-active --quiet "$SERVICE_NAME"; then
    echo "systemd service: running ($SERVICE_NAME)"
  else
    echo "systemd service: not running ($SERVICE_NAME)"
  fi
else
  PIDS="$(pgrep -f "$PROJECT_DIR/.*/main.py|$PROJECT_DIR/main.py|python.*$PROJECT_DIR/main.py" || true)"
  if [[ -n "$PIDS" ]]; then
    echo "process: running"
    echo "pid: $(echo "$PIDS" | paste -sd ',' -)"
  else
    echo "process: not running"
  fi
fi

echo
echo "== Latest 2 Log Lines =="
if [[ -f "$LOG_FILE" ]]; then
  tail -n 2 "$LOG_FILE"
else
  echo "log file not found: $LOG_FILE"
fi
