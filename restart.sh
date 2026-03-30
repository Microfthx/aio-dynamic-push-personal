#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_NAME="aio-dynamic-push"

cd "$PROJECT_DIR"

if command -v systemctl >/dev/null 2>&1 && systemctl list-unit-files | grep -q "^${SERVICE_NAME}\\.service"; then
  if systemctl restart "$SERVICE_NAME"; then
    echo "Restarted systemd service: $SERVICE_NAME"
    exit 0
  fi
fi

PIDS="$(pgrep -f "python(3)? .*${PROJECT_DIR}/main.py|python(3)? -u main.py" || true)"
if [[ -n "$PIDS" ]]; then
  echo "Stopping existing process: $(echo "$PIDS" | paste -sd ',' -)"
  echo "$PIDS" | xargs -r kill
  sleep 2
fi

nohup "$PROJECT_DIR/start.sh" >/dev/null 2>&1 &
echo "Restarted process with start.sh"
