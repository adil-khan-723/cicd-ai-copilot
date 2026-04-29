#!/usr/bin/env bash
# ============================================================
# DevOps AI Agent — Entrypoint
# Usage: ./start.sh [--port 8000] [--no-browser] [--build-ui]
#        ./start.sh --setup-jenkins   # one-time Jenkins wiring
# ============================================================
set -euo pipefail

# ── Defaults ────────────────────────────────────────────────
PORT=8000
OPEN_BROWSER=true
FORCE_UI_BUILD=false
WORKERS=1
SETUP_JENKINS=false

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
    --port)          PORT="$2"; shift 2 ;;
    --no-browser)    OPEN_BROWSER=false; shift ;;
    --build-ui)      FORCE_UI_BUILD=true; shift ;;
    --workers)       WORKERS="$2"; shift 2 ;;
    --setup-jenkins) SETUP_JENKINS=true; shift ;;
    -h|--help)
      echo "Usage: ./start.sh [--port 8000] [--no-browser] [--build-ui] [--workers N]"
      echo "       ./start.sh --setup-jenkins   # wire Jenkins to send build events here"
      exit 0 ;;
    *) die "Unknown argument: $1" ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo -e "${DIM}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RST}"
echo -e "  DevOps AI Agent"
echo -e "${DIM}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RST}"
echo ""

# ── Jenkins setup (runs standalone, skips server checks) ─────
if [[ "$SETUP_JENKINS" == "true" ]]; then
  if [[ ! -f ".env" ]]; then
    [[ -f ".env.example" ]] && cp .env.example .env
    die "No .env found. Copy .env.example to .env and fill in JENKINS_URL, JENKINS_USER, JENKINS_TOKEN."
  fi

  info "Setting up Jenkins integration..."

  JENKINS_URL=$(grep -E '^JENKINS_URL=' .env 2>/dev/null | cut -d= -f2- | tr -d '"' || echo "")
  JENKINS_USER=$(grep -E '^JENKINS_USER=' .env 2>/dev/null | cut -d= -f2- | tr -d '"' || echo "")
  JENKINS_TOKEN=$(grep -E '^JENKINS_TOKEN=' .env 2>/dev/null | cut -d= -f2- | tr -d '"' || echo "")

  if [[ -z "$JENKINS_URL" || -z "$JENKINS_USER" || -z "$JENKINS_TOKEN" ]]; then
    die "JENKINS_URL, JENKINS_USER, and JENKINS_TOKEN must all be set in .env"
  fi

  JENKINS_URL="${JENKINS_URL%/}"

  if ! curl -sf -u "$JENKINS_USER:$JENKINS_TOKEN" "$JENKINS_URL/api/json" &>/dev/null; then
    die "Cannot reach Jenkins at $JENKINS_URL — check URL and credentials in .env"
  fi
  ok "Jenkins reachable at $JENKINS_URL"

  # Detect the right callback URL for Jenkins to reach this server.
  # Override by setting AGENT_URL in .env.
  AGENT_URL=$(grep -E '^AGENT_URL=' .env 2>/dev/null | cut -d= -f2- | tr -d '"' || echo "")
  if [[ -z "$AGENT_URL" ]]; then
    JENKINS_CONTAINER=$(docker ps --format '{{.Names}}' 2>/dev/null | grep -i jenkins | head -1 || echo "")
    if [[ -n "$JENKINS_CONTAINER" ]]; then
      AGENT_URL="http://host.docker.internal:${PORT}/webhook/jenkins-notification"
    else
      AGENT_URL="http://localhost:${PORT}/webhook/jenkins-notification"
    fi
  fi
  info "Listener will POST to: $AGENT_URL"

  GROOVY_SCRIPT=$(cat <<GROOVY
import hudson.model.listeners.RunListener
import hudson.model.Run
import groovy.json.JsonOutput
import java.net.http.HttpClient
import java.net.http.HttpRequest
import java.net.http.HttpResponse
import java.net.URI
import java.time.Duration
import jenkins.model.Jenkins

class DevOpsAgentListener extends RunListener<Run> {
    static final String ENDPOINT = "${AGENT_URL}"

    void onFinalized(Run run) {
        Thread.start("devops-notifier") {
            try {
                def buildUrl = ""
                try { buildUrl = run.absoluteUrl } catch (e) { buildUrl = "" }
                def payload = [
                    name : run.parent.fullName,
                    build: [number: run.number, phase: "FINALIZED",
                            status: run.result?.toString() ?: "UNKNOWN", full_url: buildUrl]
                ]
                def body = JsonOutput.toJson(payload)
                def client = HttpClient.newBuilder()
                    .version(HttpClient.Version.HTTP_1_1)
                    .connectTimeout(Duration.ofSeconds(5)).build()
                def request = HttpRequest.newBuilder()
                    .uri(URI.create(ENDPOINT))
                    .header("Content-Type", "application/json")
                    .timeout(Duration.ofSeconds(10))
                    .POST(HttpRequest.BodyPublishers.ofString(body)).build()
                def response = client.send(request, HttpResponse.BodyHandlers.ofString())
                println "[DevOpsAgent] \${run.parent.fullName} #\${run.number} \${run.result} -> HTTP \${response.statusCode()}"
            } catch (Exception e) {
                println "[DevOpsAgent] Failed: \${e.class.simpleName}: \${e.message}"
            }
        }
    }
}

def extList = Jenkins.get().getExtensionList(RunListener.class)
extList.findAll { it.class.simpleName == "DevOpsAgentListener" }.each { extList.remove(it) }
extList.add(new DevOpsAgentListener())
println "DevOpsAgentListener registered"
GROOVY
)

  info "Registering Groovy listener in Jenkins..."
  RESULT=$(curl -sf -X POST \
    -u "$JENKINS_USER:$JENKINS_TOKEN" \
    --data-urlencode "script=$GROOVY_SCRIPT" \
    "$JENKINS_URL/scriptText" 2>&1) || {
    die "Failed to run script in Jenkins. Ensure your API token has 'Overall/Administer' permission."
  }

  if echo "$RESULT" | grep -q "DevOpsAgentListener registered"; then
    ok "Groovy listener registered in Jenkins"
  else
    warn "Unexpected response from Jenkins Script Console:"
    echo "$RESULT"
    die "Listener may not have registered — check the output above"
  fi

  JENKINS_CONTAINER=$(docker ps --format '{{.Names}}' 2>/dev/null | grep -i jenkins | head -1 || echo "")
  if [[ -n "$JENKINS_CONTAINER" ]]; then
    info "Persisting listener to ${JENKINS_CONTAINER}:/var/jenkins_home/init.groovy.d/ ..."
    echo "$GROOVY_SCRIPT" | docker exec -i "$JENKINS_CONTAINER" bash -c \
      "mkdir -p /var/jenkins_home/init.groovy.d && cat > /var/jenkins_home/init.groovy.d/devops_agent_listener.groovy"
    ok "Listener will auto-register after every Jenkins restart"
  else
    warn "No local Jenkins Docker container found — listener is active for this session only."
    warn "To persist across restarts, copy the script manually:"
    warn "  scripts/devops_agent_listener.groovy → JENKINS_HOME/init.groovy.d/"
  fi

  echo ""
  ok "Jenkins setup complete. Trigger any job to see it appear in the UI."
  echo ""
  exit 0
fi

# ── 1. Python ────────────────────────────────────────────────
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

# ── 2. Virtualenv ────────────────────────────────────────────
VENV_DIR=".venv"
if [[ ! -d "$VENV_DIR" ]]; then
  info "Creating virtualenv in .venv ..."
  # Use python3.13 explicitly — python3.14+ breaks pydantic-core
  if command -v python3.13 &>/dev/null; then
    python3.13 -m venv "$VENV_DIR"
  elif command -v python3.12 &>/dev/null; then
    python3.12 -m venv "$VENV_DIR"
  else
    python3 -m venv "$VENV_DIR"
  fi
fi
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

# ── 3. Python dependencies ───────────────────────────────────
info "Checking Python dependencies..."
if ! python -c "import uvicorn" &>/dev/null || ! python -c "import fastapi" &>/dev/null; then
  info "Installing from requirements.txt ..."
  pip install -q --upgrade pip
  pip install -q -r requirements.txt
  ok "Python dependencies installed"
else
  # Reinstall if requirements.txt is newer than uvicorn binary
  UVICORN_BIN="$VENV_DIR/bin/uvicorn"
  if [[ requirements.txt -nt "$UVICORN_BIN" ]]; then
    info "requirements.txt changed — syncing ..."
    pip install -q -r requirements.txt
    ok "Python dependencies updated"
  else
    ok "Python dependencies up to date"
  fi
fi

# ── 4. Environment (.env) ────────────────────────────────────
if [[ ! -f ".env" ]]; then
  if [[ -f ".env.example" ]]; then
    info "No .env found — copying from .env.example"
    cp .env.example .env
    warn ".env created from template. Edit it and re-run, or use the setup wizard at http://localhost:${PORT}"
    exit 1
  else
    die ".env not found and no .env.example to copy from."
  fi
fi
ok ".env present"

# Load .env into environment
set -o allexport
source ".env"
set +o allexport

# Fallback: load Anthropic key from macOS Keychain if not set in .env
if [[ -z "${ANTHROPIC_API_KEY:-}" ]]; then
  _kc_key=$(security find-generic-password -s "anthropic" -w 2>/dev/null || true)
  if [[ -n "$_kc_key" ]]; then
    export ANTHROPIC_API_KEY="$_kc_key"
    ok "ANTHROPIC_API_KEY loaded from macOS Keychain"
  fi
  unset _kc_key
fi

# Provider checks (non-fatal)
LLM_PROVIDER="${LLM_PROVIDER:-ollama}"
info "LLM provider: $LLM_PROVIDER"
case "$LLM_PROVIDER" in
  ollama)
    OLLAMA_URL="${OLLAMA_BASE_URL:-http://localhost:11434}"
    if curl -sf --max-time 3 "$OLLAMA_URL/api/tags" &>/dev/null; then
      ok "Ollama reachable at $OLLAMA_URL"
    else
      warn "Ollama not reachable at $OLLAMA_URL — start it with: ollama serve"
    fi
    ;;
  anthropic)
    if [[ -n "${ANTHROPIC_API_KEY:-}" ]]; then ok "ANTHROPIC_API_KEY set"
    else warn "ANTHROPIC_API_KEY not set — LLM features will fail"; fi
    ;;
esac

if [[ -n "${JENKINS_URL:-}" ]]; then ok "Jenkins URL: $JENKINS_URL"
else warn "JENKINS_URL not set — configure via Settings in the UI"; fi

if [[ -n "${GITHUB_TOKEN:-}" ]]; then ok "GitHub token set"
else warn "GITHUB_TOKEN not set — Copilot commit mode disabled"; fi

# ── 4b. Redis cache (optional, persistent LLM response cache) ────────────────
_try_start_redis() {
  if command -v redis-server &>/dev/null; then
    redis-server --daemonize yes --loglevel warning &>/dev/null && sleep 1
    if redis-cli ping &>/dev/null 2>&1; then
      ok "Redis started (local install)"
      export REDIS_URL="redis://localhost:6379"
      return 0
    fi
  fi
  return 1
}

_install_redis() {
  OS_TYPE="$(uname -s)"
  case "$OS_TYPE" in
    Darwin)
      if command -v brew &>/dev/null; then
        info "Installing Redis via Homebrew..."
        brew install redis -q && return 0
      fi ;;
    Linux)
      if command -v apt-get &>/dev/null; then
        info "Installing Redis via apt..."
        sudo apt-get install -y -q redis-server && return 0
      elif command -v yum &>/dev/null; then
        info "Installing Redis via yum..."
        sudo yum install -y -q redis && return 0
      fi ;;
  esac
  return 1
}

REDIS_URL="${REDIS_URL:-}"
if [[ -z "$REDIS_URL" ]]; then
  # Check if Redis already running
  if redis-cli ping &>/dev/null 2>&1; then
    ok "Redis already running"
    export REDIS_URL="redis://localhost:6379"
  else
    echo ""
    echo -e "${YLW}Redis not found.${RST} Install it for persistent LLM response caching (24hr TTL)?"
    echo -e "${DIM}  Without Redis: in-memory cache only (lost on restart)${RST}"
    read -r -p "  Install Redis? [y/N] " _redis_ans
    if [[ "$(echo "$_redis_ans" | tr '[:upper:]' '[:lower:]')" == "y" ]]; then
      if _install_redis && _try_start_redis; then
        ok "Redis ready — persistent cache enabled"
      else
        warn "Redis install failed — using in-memory cache"
      fi
    else
      info "Skipping Redis — using in-memory cache"
    fi
  fi
fi

# ── 4d. Docker socket permissions for Jenkins-in-Docker ──────
# When Jenkins runs inside a Docker container, the Docker socket is bind-mounted
# from the host (macOS/Windows: Docker Desktop VM; Linux: host directly).
# The Jenkins process needs read/write access to run docker build commands.
# chmod 666 on the socket is intentional for local dev — do not use in production.
_fix_jenkins_docker_socket() {
  local container="$1"
  if docker exec -u root "$container" test -S /var/run/docker.sock 2>/dev/null; then
    docker exec -u root "$container" chmod 666 /var/run/docker.sock 2>/dev/null && \
      ok "Docker socket permissions set for Jenkins container '$container'" || \
      warn "Could not set Docker socket permissions in '$container' — docker build may fail"
  fi
}

if command -v docker &>/dev/null && docker info &>/dev/null 2>&1; then
  JENKINS_CONTAINER=$(docker ps --format '{{.Names}}' 2>/dev/null | grep -i jenkins | head -1 || true)
  if [[ -n "$JENKINS_CONTAINER" ]]; then
    OS_TYPE="$(uname -s)"
    case "$OS_TYPE" in
      Darwin)
        # macOS — Docker Desktop VM owns the socket; fix via docker exec
        _fix_jenkins_docker_socket "$JENKINS_CONTAINER"
        ;;
      Linux)
        # Linux — socket owned by host docker group; add jenkins user to docker group
        if docker exec "$JENKINS_CONTAINER" id jenkins &>/dev/null 2>&1; then
          docker exec -u root "$JENKINS_CONTAINER" \
            bash -c "getent group docker || groupadd docker; usermod -aG docker jenkins" 2>/dev/null && \
            ok "Jenkins user added to docker group in '$JENKINS_CONTAINER'" || \
            _fix_jenkins_docker_socket "$JENKINS_CONTAINER"
        fi
        ;;
      MINGW*|CYGWIN*|MSYS*)
        # Windows — Docker Desktop VM, same approach as macOS
        _fix_jenkins_docker_socket "$JENKINS_CONTAINER"
        ;;
    esac
  fi
fi

# ── 5. Node / npm (for UI builds) ────────────────────────────
HAS_NODE=false
if command -v node &>/dev/null && command -v npm &>/dev/null; then
  HAS_NODE=true
  ok "Node $(node --version) / npm $(npm --version)"
else
  warn "Node/npm not found — UI will use pre-built assets (run --build-ui after installing Node)"
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
    die "No built UI at $UI_STATIC and Node/npm unavailable. Run 'cd frontend && npm run build' first."
  fi
else
  ok "React UI present (use --build-ui to force rebuild)"
fi

# ── 7. Port check ────────────────────────────────────────────
if lsof -iTCP:"$PORT" -sTCP:LISTEN &>/dev/null; then
  warn "Port $PORT in use — stopping existing process..."
  PID=$(lsof -ti TCP:"$PORT" -sTCP:LISTEN | head -1)
  if [[ -n "$PID" ]]; then
    kill "$PID" 2>/dev/null && sleep 1 && ok "Stopped PID $PID"
  fi
fi

# ── 8. Launch ────────────────────────────────────────────────
echo ""
echo -e "${DIM}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RST}"
info "Starting server on http://localhost:${PORT}"
echo -e "${DIM}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RST}"
echo ""

if [[ "$OPEN_BROWSER" == "true" ]]; then
  ( sleep 2 && open "http://localhost:${PORT}" 2>/dev/null || true ) &
fi

exec python -m uvicorn webhook.server:app \
  --host 0.0.0.0 \
  --port "$PORT" \
  --workers "$WORKERS" \
  --log-level info
