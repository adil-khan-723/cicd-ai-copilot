#!/usr/bin/env bash
# launch.sh — DevOps AI Agent launcher
# Checks prerequisites, installs deps if needed, then starts the server.

set -euo pipefail

# ── Colours ────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

ok()   { echo -e "${GREEN}  ✓ ${1}${RESET}"; }
warn() { echo -e "${YELLOW}  ⚠ ${1}${RESET}"; }
err()  { echo -e "${RED}  ✗ ${1}${RESET}"; }
info() { echo -e "${CYAN}  → ${1}${RESET}"; }
hdr()  { echo -e "\n${BOLD}${1}${RESET}"; }

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

PORT="${WEBHOOK_PORT:-8000}"
VENV="$DIR/.venv"
PYTHON="$VENV/bin/python"
UVICORN="$VENV/bin/uvicorn"

# ── 1. Python ──────────────────────────────────────────────────────────────
hdr "[ 1 / 6 ]  Python"
if ! command -v python3 &>/dev/null; then
  err "python3 not found. Install Python 3.11+."
  exit 1
fi
PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
REQUIRED="3.11"
if python3 -c "import sys; exit(0 if sys.version_info >= (3,11) else 1)"; then
  ok "Python $PY_VER"
else
  err "Python $PY_VER found — need $REQUIRED+."
  exit 1
fi

# ── 2. Virtual environment ─────────────────────────────────────────────────
hdr "[ 2 / 6 ]  Virtual environment"
if [ ! -d "$VENV" ]; then
  info "Creating .venv …"
  python3 -m venv "$VENV"
  ok "Created .venv"
else
  ok ".venv exists"
fi

# ── 3. Dependencies ────────────────────────────────────────────────────────
hdr "[ 3 / 6 ]  Dependencies"
if [ ! -f "$UVICORN" ]; then
  info "Installing from requirements.txt …"
  "$PYTHON" -m pip install -q --upgrade pip
  "$PYTHON" -m pip install -q -r requirements.txt
  ok "Dependencies installed"
else
  # Quick check — reinstall only if requirements.txt is newer than uvicorn
  if [ requirements.txt -nt "$UVICORN" ]; then
    info "requirements.txt changed — syncing …"
    "$PYTHON" -m pip install -q -r requirements.txt
    ok "Dependencies updated"
  else
    ok "Dependencies up to date"
  fi
fi

# ── 4. .env file ───────────────────────────────────────────────────────────
hdr "[ 4 / 6 ]  Environment (.env)"
if [ ! -f "$DIR/.env" ]; then
  if [ -f "$DIR/.env.example" ]; then
    warn ".env not found — copying from .env.example"
    cp "$DIR/.env.example" "$DIR/.env"
    warn "Edit .env and re-run this script."
    exit 1
  else
    err ".env not found and no .env.example to copy from."
    exit 1
  fi
fi

# Load .env
set -o allexport
source "$DIR/.env"
set +o allexport
ok ".env loaded"

# Key checks (non-fatal — app still starts, features just disabled)
LLM_PROVIDER="${LLM_PROVIDER:-ollama}"
info "LLM provider: $LLM_PROVIDER"

case "$LLM_PROVIDER" in
  ollama)
    OLLAMA_URL="${OLLAMA_BASE_URL:-http://localhost:11434}"
    if curl -sf --max-time 3 "$OLLAMA_URL/api/tags" &>/dev/null; then
      ok "Ollama reachable at $OLLAMA_URL"
    else
      warn "Ollama not reachable at $OLLAMA_URL — LLM analysis will be skipped"
    fi
    ;;
  anthropic)
    if [ -n "${ANTHROPIC_API_KEY:-}" ]; then ok "ANTHROPIC_API_KEY set"
    else warn "ANTHROPIC_API_KEY not set — LLM analysis will fail"; fi
    ;;
  groq)
    if [ -n "${GROQ_API_KEY:-}" ]; then ok "GROQ_API_KEY set"
    else warn "GROQ_API_KEY not set — LLM analysis will fail"; fi
    ;;
  gemini)
    if [ -n "${GEMINI_API_KEY:-}" ]; then ok "GEMINI_API_KEY set"
    else warn "GEMINI_API_KEY not set — LLM analysis will fail"; fi
    ;;
esac

if [ -n "${JENKINS_URL:-}" ]; then ok "Jenkins URL: $JENKINS_URL"
else warn "JENKINS_URL not set — configure via Settings in the UI"; fi

if [ -n "${GITHUB_TOKEN:-}" ]; then ok "GitHub token set"
else warn "GITHUB_TOKEN not set — Copilot mode disabled"; fi

# ── 5. Port check ──────────────────────────────────────────────────────────
hdr "[ 5 / 6 ]  Port $PORT"
if lsof -ti tcp:"$PORT" &>/dev/null; then
  OCCUPANT=$(lsof -ti tcp:"$PORT" | head -1)
  warn "Port $PORT in use by PID $OCCUPANT"
  read -rp "  Kill it and continue? [y/N] " ans
  if [[ "${ans,,}" == "y" ]]; then
    kill -9 "$OCCUPANT" 2>/dev/null || true
    sleep 1
    ok "Killed PID $OCCUPANT"
  else
    err "Aborted — port $PORT occupied."
    exit 1
  fi
else
  ok "Port $PORT free"
fi

# ── 6. Launch ──────────────────────────────────────────────────────────────
hdr "[ 6 / 6 ]  Launch"
echo ""
echo -e "${BOLD}  DevOps AI Agent${RESET}"
echo -e "  ${CYAN}http://localhost:${PORT}${RESET}"
echo -e "  Ctrl+C to stop\n"

exec "$UVICORN" webhook.server:app \
  --host 0.0.0.0 \
  --port "$PORT" \
  --reload \
  --reload-dir "$DIR" \
  --log-level info
