#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_NAME="aio-dynamic-push"

cd "$PROJECT_DIR"

find_project_pids() {
  local pids pid cwd cmd
  pids="$(pgrep -f "python(3)? .* -u main.py|python(3)? -u main.py|python(3)? .*${PROJECT_DIR}/main.py" || true)"
  for pid in $pids; do
    [[ "$pid" == "$$" ]] && continue
    [[ -r "/proc/$pid/cmdline" ]] || continue
    cmd="$(tr '\0' ' ' <"/proc/$pid/cmdline")"
    [[ "$cmd" == *"python"* && "$cmd" == *"main.py"* ]] || continue
    cwd="$(readlink "/proc/$pid/cwd" 2>/dev/null || true)"
    [[ "$cwd" == "$PROJECT_DIR" ]] || continue
    echo "$pid"
  done
}

stop_extra_project_pids() {
  local keep_pid="${1:-}"
  local pids pid still_running
  pids="$(find_project_pids | awk -v keep="$keep_pid" '$0 != keep')"
  [[ -z "$pids" ]] && return 0

  echo "Stopping extra project process(es): $(echo "$pids" | paste -sd ',' -)"
  echo "$pids" | xargs -r kill
  sleep 2

  still_running="$(find_project_pids | awk -v keep="$keep_pid" '$0 != keep')"
  if [[ -n "$still_running" ]]; then
    echo "Force stopping extra project process(es): $(echo "$still_running" | paste -sd ',' -)"
    echo "$still_running" | xargs -r kill -9
  fi
}

wait_system_main_pid() {
  local pid
  for _ in {1..20}; do
    pid="$(systemctl show "$SERVICE_NAME" -p MainPID --value 2>/dev/null || true)"
    if [[ -n "$pid" && "$pid" != "0" ]]; then
      echo "$pid"
      return 0
    fi
    sleep 0.2
  done
  echo ""
}

wait_user_main_pid() {
  local pid
  for _ in {1..20}; do
    pid="$(systemctl --user show "$SERVICE_NAME" -p MainPID --value 2>/dev/null || true)"
    if [[ -n "$pid" && "$pid" != "0" ]]; then
      echo "$pid"
      return 0
    fi
    sleep 0.2
  done
  echo ""
}

restart_system_service_if_exists() {
  if ! command -v systemctl >/dev/null 2>&1; then
    return 1
  fi
  if ! systemctl list-unit-files 2>/dev/null | grep -q "^${SERVICE_NAME}\\.service"; then
    return 1
  fi
  systemctl restart "$SERVICE_NAME"
  local main_pid
  main_pid="$(wait_system_main_pid)"
  stop_extra_project_pids "$main_pid"
  echo "Restarted systemd service: $SERVICE_NAME"
  return 0
}

restart_user_service_if_exists() {
  if ! command -v systemctl >/dev/null 2>&1; then
    return 1
  fi
  if ! systemctl --user list-unit-files 2>/dev/null | grep -q "^${SERVICE_NAME}\\.service"; then
    return 1
  fi
  systemctl --user restart "$SERVICE_NAME"
  local main_pid
  main_pid="$(wait_user_main_pid)"
  stop_extra_project_pids "$main_pid"
  echo "Restarted user systemd service: $SERVICE_NAME"
  return 0
}

# 尝试在重启前更新微博 cookie（如果脚本存在且可执行）
if [[ -x "$PROJECT_DIR/scripts/update_cookie.sh" ]]; then
  "$PROJECT_DIR/scripts/update_cookie.sh" || echo "update_cookie.sh failed or canceled; continuing restart"
fi

if restart_system_service_if_exists; then
  exit 0
fi

if restart_user_service_if_exists; then
  exit 0
fi

PIDS="$(find_project_pids)"
if [[ -n "$PIDS" ]]; then
  echo "Stopping existing process: $(echo "$PIDS" | paste -sd ',' -)"
  echo "$PIDS" | xargs -r kill
  sleep 2
  PIDS="$(find_project_pids)"
  if [[ -n "$PIDS" ]]; then
    echo "Force stopping existing process: $(echo "$PIDS" | paste -sd ',' -)"
    echo "$PIDS" | xargs -r kill -9
  fi
fi

nohup "$PROJECT_DIR/start.sh" >/dev/null 2>&1 &
echo "Restarted process with start.sh"
