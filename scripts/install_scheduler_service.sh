#!/usr/bin/env bash
set -euo pipefail

SERVICE_NAME="sensor-scheduler.service"
WORKDIR="$(cd "$(dirname "$0")/.." && pwd)"
ENV_PY="$WORKDIR/greenhouse-env/bin/python"
SERVICE_PATH="$HOME/.config/systemd/user/$SERVICE_NAME"

mkdir -p "$(dirname "$SERVICE_PATH")"

cat > "$SERVICE_PATH" <<EOF
[Unit]
Description=Greenhouse Sensor Scheduler Service
After=default.target

[Service]
Type=simple
WorkingDirectory=$WORKDIR
ExecStart=$ENV_PY $WORKDIR/sensor_scheduler_service.py
Restart=on-failure
RestartSec=5s
Environment=VERBOSE_SCHEDULER_LOGS=

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
systemctl --user enable --now "$SERVICE_NAME"
echo "Installed and started $SERVICE_NAME (user service). Use: systemctl --user status $SERVICE_NAME"
