#!/bin/bash
# Constellation Relay — one-time installer for macOS.
# Double-click this file. If macOS says it can't be opened, right-click it
# and choose "Open" instead (only needed the first time).
set -e
cd "$(dirname "$0")"

echo "🌌 Constellation Relay — installer"
echo ""

# uv manages Python and all dependencies for us — no separate Python install needed.
export PATH="$HOME/.local/bin:$PATH"
if ! command -v uv >/dev/null 2>&1; then
    echo "Step 1/2: Installing uv (a Python package manager)..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
else
    echo "Step 1/2: uv is already installed ✓"
fi

echo ""
echo "Step 2/2: Installing Python and the app (the first run can take a few minutes)..."
uv sync --extra desktop

echo ""
echo "✅ All set!"
echo "Double-click 'Constellation Relay.command' to start the app."
echo ""
read -n 1 -s -r -p "Press any key to close this window..."
echo ""
