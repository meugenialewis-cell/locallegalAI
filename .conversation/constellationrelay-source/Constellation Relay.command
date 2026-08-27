#!/bin/bash
# Constellation Relay — desktop app launcher for macOS.
# Run install_mac.command once before using this.
cd "$(dirname "$0")"
export PATH="$HOME/.local/bin:$PATH"

if ! command -v uv >/dev/null 2>&1; then
    echo "It looks like the app isn't installed yet."
    echo "Please double-click install_mac.command first."
    read -n 1 -s -r -p "Press any key to close this window..."
    exit 1
fi

uv run python desktop.py
