#!/bin/bash
# ============================================================
#  Open Quinn — double-click me!
#  Starts the app on your Mac (if it isn't running) and opens
#  it in your browser. Run Install Quinn first, just once.
# ============================================================

cd "$(dirname "$0")"

say()  { printf "\n\033[1;32m✦ %s\033[0m\n" "$1"; }
note() { printf "  %s\n" "$1"; }

# If the app is already running, just open it.
if curl -s -o /dev/null http://localhost:5173; then
  say "Quinn is already awake. Opening her in your browser…"
  open http://localhost:5173
  exit 0
fi

if [ ! -d node_modules ]; then
  say "It looks like setup hasn't run yet."
  note "Please double-click Install Quinn first — it only takes a few minutes."
  read -r -p "Press return to close this window… " _
  exit 1
fi

say "Waking Quinn up…"
export PATH="$(brew --prefix postgresql@16 2>/dev/null)/bin:$PATH"
brew services start postgresql@16 >/dev/null 2>&1 || true
brew services start ollama >/dev/null 2>&1 || true

# Open the browser once the app answers.
( until curl -s -o /dev/null http://localhost:5173; do sleep 2; done
  open http://localhost:5173 ) &

note "Keep this window open while you use Quinn."
note "Closing it puts her back to sleep."
(PORT=3001 pnpm --filter @workspace/api-server run dev &) \
  && PORT=5173 BASE_PATH=/ API_PROXY_TARGET=http://localhost:3001 \
     pnpm --filter @workspace/legal-agent run dev
