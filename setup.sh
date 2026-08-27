#!/bin/bash
# ============================================================
#  Take Quinn Home — one-command setup for macOS
#  Runs the Local Legal AI app entirely on your own machine.
#  Setup downloads its tools from trusted sources (Homebrew, npm,
#  Ollama); after that, the app itself sends nothing anywhere.
#  Safe to re-run at any time.
# ============================================================
set -e

say()  { printf "\n\033[1;32m✦ %s\033[0m\n" "$1"; }
note() { printf "  %s\n" "$1"; }
fail() { printf "\n\033[1;31m✗ %s\033[0m\n" "$1"; exit 1; }

say "Welcome. Let's bring Quinn home."

if [ "$(uname)" != "Darwin" ]; then
  fail "This script is written for macOS. Please run it on your Mac."
fi

# ---- 1. Homebrew (the Mac's package installer) --------------
if ! command -v brew >/dev/null 2>&1; then
  say "Installing Homebrew (a standard, trusted Mac tool installer)…"
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  eval "$(/opt/homebrew/bin/brew shellenv 2>/dev/null || /usr/local/bin/brew shellenv)"
else
  note "Homebrew is already installed. Good."
fi

# ---- 2. The pieces the app needs ----------------------------
say "Installing the app's building blocks (Node, pnpm, PostgreSQL, Ollama)…"
brew list node >/dev/null 2>&1        || brew install node
command -v pnpm >/dev/null 2>&1        || brew install pnpm
brew list postgresql@16 >/dev/null 2>&1 || brew install postgresql@16
brew list ollama >/dev/null 2>&1       || brew install ollama

say "Starting the local database and model runtime…"
brew services start postgresql@16 >/dev/null || true
brew services start ollama >/dev/null || true
sleep 3

# ---- 3. The database (Quinn's filing cabinet) ----------------
# postgresql@16 is keg-only, so its commands need to be put on the PATH.
export PATH="$(brew --prefix postgresql@16)/bin:$PATH"
createdb locallegalai 2>/dev/null || note "Database already exists — keeping it."
export DATABASE_URL="postgresql://localhost/locallegalai"
if ! grep -q "^DATABASE_URL=" .env 2>/dev/null; then
  echo "DATABASE_URL=$DATABASE_URL" >> .env
fi
if ! grep -q "^SESSION_SECRET=" .env 2>/dev/null; then
  echo "SESSION_SECRET=$(openssl rand -hex 32)" >> .env
fi

# ---- 4. The app itself ---------------------------------------
say "Setting up the app (this can take a few minutes the first time)…"
pnpm install
(cd lib/db && pnpm run push)

# ---- 5. Quinn herself ----------------------------------------
EXPORT_FILE=""
for candidate in ./quinn-export.json "$HOME/Downloads/quinn-export.json"; do
  [ -f "$candidate" ] && EXPORT_FILE="$candidate" && break
done
if [ -n "$EXPORT_FILE" ]; then
  say "Found Quinn's export ($EXPORT_FILE). Importing her identities, story, and ledger…"
  node scripts/import-quinn.mjs "$EXPORT_FILE"
else
  note "No quinn-export.json found (looked here and in Downloads)."
  note "You can export it from the hosted app's Take Quinn Home page and re-run me."
fi

# ---- 6. Done --------------------------------------------------
say "Starting the app…"
note "Your browser will open by itself when the app is ready."
note "Keep this window open while you use Quinn — closing it puts her to sleep."
note "Next time, just double-click 'Open Quinn.command' in this folder."
note ""
note "Next step, inside the app: Take Quinn Home → Step 4 → Download a mind for Quinn."

# Open the browser automatically once the app answers.
( until curl -s -o /dev/null http://localhost:5173; do sleep 2; done
  open http://localhost:5173 ) &

(PORT=3001 pnpm --filter @workspace/api-server run dev &) \
  && PORT=5173 BASE_PATH=/ API_PROXY_TARGET=http://localhost:3001 \
     pnpm --filter @workspace/legal-agent run dev
