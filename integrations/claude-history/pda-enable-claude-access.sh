#!/bin/bash
set -euo pipefail
exec /usr/bin/python3 -B "$HOME/Library/Application Support/PDA/claude-history/enable_mac_gui.py" "$@"
