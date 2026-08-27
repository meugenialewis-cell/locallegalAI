#!/bin/bash
# Constellation Relay — update to the latest version, then launch.
# Double-click this instead of the plain launcher when you want updates.
# Your personal data (continuity/, transcripts/, saved_conversations/,
# relay_memory.db, backups/) is never touched by an update.
cd "$(dirname "$0")"
export PATH="$HOME/.local/bin:$PATH"

BRANCH="claude/multi-model-desktop-app-70jk69"
REPO="meugenialewis-cell/constellationrelaybackupv1.0"
ZIP_URL="https://codeload.github.com/$REPO/zip/refs/heads/$BRANCH"

echo "🌌 Checking for updates..."

if [ -d .git ] && command -v git >/dev/null 2>&1; then
    git fetch origin "$BRANCH" 2>/dev/null && git pull --ff-only origin "$BRANCH" \
        || echo "Couldn't pull updates — launching the current version."
else
    TMP=$(mktemp -d)
    if curl -fsSL "$ZIP_URL" -o "$TMP/app.zip" 2>/dev/null; then
        unzip -q "$TMP/app.zip" -d "$TMP"
        SRC=$(find "$TMP" -mindepth 1 -maxdepth 1 -type d | head -1)
        if [ -n "$SRC" ]; then
            # Update the code, but never overwrite personal data
            rsync -a \
                --exclude 'continuity/' \
                --exclude 'transcripts/' \
                --exclude 'saved_conversations/' \
                --exclude 'backups/' \
                --exclude '*.db' \
                "$SRC"/ ./
            # Add any brand-new continuity documents without touching existing ones
            rsync -a --ignore-existing "$SRC/continuity/" ./continuity/ 2>/dev/null
            echo "✅ Updated to the latest version."
        fi
    else
        echo "Couldn't reach GitHub (offline?) — launching the current version."
    fi
    rm -rf "$TMP"
fi

if command -v uv >/dev/null 2>&1; then
    echo "Checking dependencies..."
    uv sync --extra desktop --quiet 2>/dev/null
    uv run python desktop.py
else
    echo "It looks like the app isn't installed yet."
    echo "Please double-click install_mac.command first."
    read -n 1 -s -r -p "Press any key to close this window..."
    exit 1
fi
