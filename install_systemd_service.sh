#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_NAME="aio-dynamic-push"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
RUN_USER="${SUDO_USER:-$(id -un)}"
RUN_GROUP="$(id -gn "$RUN_USER")"

if [[ $EUID -ne 0 ]]; then
  echo "Please run this script with sudo:" >&2
  echo "  sudo bash $PROJECT_DIR/install_systemd_service.sh" >&2
  exit 1
fi

cat >"$SERVICE_FILE" <<EOF
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
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

chmod 644 "$SERVICE_FILE"
chmod +x "$PROJECT_DIR/start.sh"

systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
systemctl restart "$SERVICE_NAME"

echo "Installed service: $SERVICE_FILE"
echo "Check status with: systemctl status $SERVICE_NAME"
echo "View logs with: journalctl -u $SERVICE_NAME -f"
