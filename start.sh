#!/usr/bin/env bash
# ============================================================
# DevOps AI Agent — Entrypoint
# Usage: ./start.sh [--port 8000] [--no-browser] [--build-ui]
# ============================================================
set -euo pipefail

# ── Defaults ────────────────────────────────────────────────
PORT=8000
OPEN_BROWSER=true
FORCE_UI_BUILD=false
WORKERS=1

# ── Colours ─────────────────────────────────────────────────
RED='\033[0;31m'
GRN='\033[0;32m'
YLW='\033[1;33m'
BLU='\033[0;34m'
DIM='\033[2m'
RST='\033[0m'

ok()   { echo -e "${GRN}✓${RST}  $*"; }
info() { echo -e "${BLU}→${RST}  $*"; }
warn() { echo -e "${YLW}⚠${RST}  $*"; }
die()  { echo -e "${RED}✗${RST}  $*" >&2; exit 1; }

# ── Parse args ──────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case $1 in
    --port)       PORT="$2"; shift 2 ;;
    --no-browser) OPEN_BROWSER=false; shift ;;
    --build-ui)   FORCE_UI_BUILD=true; shift ;;
    --workers)    WORKERS="$2"; shift 2 ;;
    -h|--help)
      echo "Usage: ./start.sh [--port 8000] [--no-browser] [--build-ui] [--workers N]"
      exit 0 ;;
    *) die "Unknown argument: $1" ;;
  esac
done

echo ""
echo -e "${DIM}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RST}"
echo -e "  DevOps AI Agent"
echo -e "${DIM}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RST}"
echo ""

# ── 1. Python version ────────────────────────────────────────
info "Checking Python..."
if ! command -v python3 &>/dev/null; then
  die "python3 not found. Install Python 3.11+."
fi
PYVER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PYMAJ=$(echo "$PYVER" | cut -d. -f1)
PYMIN=$(echo "$PYVER" | cut -d. -f2)
if [[ "$PYMAJ" -lt 3 || ("$PYMAJ" -eq 3 && "$PYMIN" -lt 11) ]]; then
  die "Python 3.11+ required, found $PYVER"
fi
ok "Python $PYVER"

# ── 2. Virtualenv / pip ──────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VENV_DIR=".venv"
if [[ ! -d "$VENV_DIR" ]]; then
  info "Creating virtualenv in .venv ..."
  python3 -m venv "$VENV_DIR"
fi

# Activate venv
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

# ── 3. Python deps ───────────────────────────────────────────
info "Checking Python dependencies..."
# Fast check: see if uvicorn is importable (sentinel for all deps being installed)
if ! python -c "import uvicorn" &>/dev/null || ! python -c "import fastapi" &>/dev/null; then
  info "Installing Python dependencies from requirements.txt ..."
  pip install -q --upgrade pip
  pip install -q -r requirements.txt
  ok "Python dependencies installed"
else
  ok "Python dependencies present"
fi

# ── 4. .env file ────────────────────────────────────────────
if [[ ! -f ".env" ]]; then
  if [[ -f ".env.example" ]]; then
    info "No .env found — copying from .env.example"
    cp .env.example .env
    warn ".env created from template. Open http://localhost:${PORT} to run the setup wizard."
  else
    warn "No .env or .env.example found. You can configure via the setup wizard at http://localhost:${PORT}"
    touch .env
  fi
else
  ok ".env present"
fi

# ── 5. Node / npm (for UI builds) ────────────────────────────
HAS_NODE=false
if command -v node &>/dev/null && command -v npm &>/dev/null; then
  HAS_NODE=true
  ok "Node $(node --version) / npm $(npm --version)"
else
  warn "Node/npm not found — UI will use pre-built assets (run --build-ui manually after installing Node)"
fi

# ── 6. UI build ──────────────────────────────────────────────
UI_STATIC="ui/static/index.html"
FRONTEND_DIR="frontend"

if [[ "$FORCE_UI_BUILD" == "true" ]]; then
  if [[ "$HAS_NODE" == "true" && -d "$FRONTEND_DIR" ]]; then
    info "Building React UI (--build-ui flag set)..."
    cd "$FRONTEND_DIR"
    npm install --silent
    npm run build --silent
    cd "$SCRIPT_DIR"
    ok "React UI built"
  else
    [[ "$HAS_NODE" == "false" ]] && die "Cannot build UI: Node/npm not found"
    die "frontend/ directory not found"
  fi
elif [[ ! -f "$UI_STATIC" ]]; then
  if [[ "$HAS_NODE" == "true" && -d "$FRONTEND_DIR" ]]; then
    info "No built UI found — building React UI..."
    cd "$FRONTEND_DIR"
    npm install --silent
    npm run build --silent
    cd "$SCRIPT_DIR"
    ok "React UI built"
  else
    die "No built UI found at $UI_STATIC and Node/npm unavailable. Run 'cd frontend && npm run build' first."
  fi
else
  ok "React UI present (use --build-ui to force rebuild)"
fi

# ── 7. Ollama check (non-fatal) ──────────────────────────────
LLM_PROVIDER=$(grep -E '^LLM_PROVIDER=' .env 2>/dev/null | cut -d= -f2 | tr -d '[:space:]"' || echo "ollama")
if [[ "$LLM_PROVIDER" == "ollama" ]]; then
  if curl -sf http://localhost:11434/api/tags &>/dev/null; then
    ok "Ollama reachable"
  else
    warn "Ollama not reachable at localhost:11434. Start it with: ollama serve"
    warn "Chat and analysis features will fall back to error messages until Ollama is running."
  fi
fi

# ── 8. Port availability ─────────────────────────────────────
if lsof -iTCP:"$PORT" -sTCP:LISTEN &>/dev/null; then
  warn "Port $PORT is already in use — attempting to stop existing server..."
  PID=$(lsof -ti TCP:"$PORT" -sTCP:LISTEN | head -1)
  if [[ -n "$PID" ]]; then
    kill "$PID" 2>/dev/null && sleep 1 && ok "Stopped PID $PID"
  fi
fi

# ── 9. Launch ────────────────────────────────────────────────
echo ""
echo -e "${DIM}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RST}"
info "Starting server on http://localhost:${PORT}"
echo -e "${DIM}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RST}"
echo ""

# Open browser after a short delay (macOS)
if [[ "$OPEN_BROWSER" == "true" ]]; then
  ( sleep 2 && open "http://localhost:${PORT}" 2>/dev/null || true ) &
fi

# Run uvicorn (blocking)
exec python -m uvicorn webhook.server:app \
  --host 0.0.0.0 \
  --port "$PORT" \
  --workers "$WORKERS" \
  --log-level info
