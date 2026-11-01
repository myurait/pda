#!/bin/bash
# ミニ PC の ~/pda で実行する。中継を常駐させ、OpenClaw の常駐が入口を通るようにして、OpenClaw を起動し直す。
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
UNIT_DIR=$HOME/.config/systemd/user
mkdir -p "$UNIT_DIR/v03-openclaw.service.d" "$HOME/.local/state/openclaw-tool-defer"
chmod 755 "$HERE/bin/claude" "$HERE/relay.py"
cp "$HERE/openclaw-tool-defer-relay.service" "$UNIT_DIR/"
cp "$HERE/tool-defer.conf" "$UNIT_DIR/v03-openclaw.service.d/tool-defer.conf"
systemctl --user daemon-reload
systemctl --user enable --now openclaw-tool-defer-relay.service
for _ in 1 2 3 4 5 6 7 8 9 10; do
  if python3 -c 'import socket;socket.create_connection(("127.0.0.1",37191),timeout=0.5)' 2>/dev/null; then break; fi
  sleep 1
done
systemctl --user restart v03-openclaw.service
echo "installed: relay $(systemctl --user is-active openclaw-tool-defer-relay.service), openclaw $(systemctl --user is-active v03-openclaw.service)"
