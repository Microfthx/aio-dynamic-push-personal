#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_NAME="aio-dynamic-push"
RUN_USER="${SUDO_USER:-$(id -un)}"
RUN_GROUP="$(id -gn "$RUN_USER")"
USER_SERVICE_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
USER_SERVICE_FILE="$USER_SERVICE_DIR/${SERVICE_NAME}.service"
SYSTEM_SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

chmod +x "$PROJECT_DIR/start.sh"

if [[ $EUID -eq 0 ]]; then
  cat >"$SYSTEM_SERVICE_FILE" <<EOF
[Unit]
Description=aio-dynamic-push
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$RUN_USER
Group=$RUN_GROUP
WorkingDirectory=$PROJECT_DIR
ExecStart=$PROJECT_DIR/start.sh
Restart=no

[Install]
WantedBy=multi-user.target
EOF
  chmod 644 "$SYSTEM_SERVICE_FILE"
  systemctl daemon-reload
  systemctl disable "$SERVICE_NAME" >/dev/null 2>&1 || true
  systemctl stop "$SERVICE_NAME" >/dev/null 2>&1 || true
  echo "Installed system service: $SYSTEM_SERVICE_FILE"
  echo "The service is disabled and stopped. Start manually with: systemctl start $SERVICE_NAME"
  echo "Check status with: systemctl status $SERVICE_NAME"
  echo "View logs with: journalctl -u $SERVICE_NAME -f"
else
  mkdir -p "$USER_SERVICE_DIR"
  cat >"$USER_SERVICE_FILE" <<EOF
[Unit]
Description=aio-dynamic-push
After=network.target

[Service]
Type=simple
WorkingDirectory=$PROJECT_DIR
ExecStart=$PROJECT_DIR/start.sh
Restart=no

[Install]
WantedBy=default.target
EOF
  chmod 644 "$USER_SERVICE_FILE"
  systemctl --user daemon-reload
  systemctl --user disable "$SERVICE_NAME" >/dev/null 2>&1 || true
  systemctl --user stop "$SERVICE_NAME" >/dev/null 2>&1 || true
  echo "Installed user service: $USER_SERVICE_FILE"
  echo "The service is disabled and stopped. Start manually with: systemctl --user start $SERVICE_NAME"
  echo "Check status with: systemctl --user status $SERVICE_NAME"
  echo "View logs with: journalctl --user -u $SERVICE_NAME -f"
fi
