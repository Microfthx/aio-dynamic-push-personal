#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="$PROJECT_DIR/aio-dynamic-push.log"
HTTP_PROXY_URL="${HTTP_PROXY_URL:-http://127.0.0.1:17890}"
HTTPS_PROXY_URL="${HTTPS_PROXY_URL:-http://127.0.0.1:17890}"
ALL_PROXY_URL="${ALL_PROXY_URL:-socks5://127.0.0.1:17891}"

if command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="$(command -v python3)"
elif [[ -x "$PROJECT_DIR/.venv/bin/python" ]]; then
  PYTHON_BIN="$PROJECT_DIR/.venv/bin/python"
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN="$(command -v python)"
else
  echo "Error: python interpreter not found." >&2
  exit 1
fi

cd "$PROJECT_DIR"
exec env \
  http_proxy="$HTTP_PROXY_URL" \
  https_proxy="$HTTPS_PROXY_URL" \
  all_proxy="$ALL_PROXY_URL" \
  "$PYTHON_BIN" -u main.py >>"$LOG_FILE" 2>&1
