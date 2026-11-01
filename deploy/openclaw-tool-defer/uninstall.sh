#!/bin/bash
# ミニ PC で実行する。OpenClaw の常駐を入口を通らない元の形に戻し、中継を止めて外す。
set -euo pipefail
UNIT_DIR=$HOME/.config/systemd/user
rm -f "$UNIT_DIR/v03-openclaw.service.d/tool-defer.conf"
rmdir "$UNIT_DIR/v03-openclaw.service.d" 2>/dev/null || true
systemctl --user disable --now openclaw-tool-defer-relay.service 2>/dev/null || true
rm -f "$UNIT_DIR/openclaw-tool-defer-relay.service"
systemctl --user daemon-reload
systemctl --user restart v03-openclaw.service
echo "uninstalled: openclaw $(systemctl --user is-active v03-openclaw.service)"
