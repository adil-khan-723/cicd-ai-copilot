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
ASSUME_YES=false

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
    -y|--yes)        ASSUME_YES=true; shift ;;
    -h|--help)
      echo "Usage: ./start.sh [--port 8000] [--no-browser] [--build-ui] [--workers N] [--yes]"
      echo "       ./start.sh --setup-jenkins   # wire Jenkins to send build events here"
      echo ""
      echo "  --yes / -y   Auto-accept all prereq install prompts (CI / unattended)"
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

# ── 1. Prereq validator ──────────────────────────────────────
# Detects host OS + package manager. For each missing prereq, prompts
# (default Y) to run the right install command. Skips silently if present.
# Non-interactive shells (CI) get clear error + exit; never auto-install
# without confirmation.

OS_TYPE="$(uname -s)"
PKG_MGR=""
PKG_INSTALL=""    # full prefix incl sudo where applicable
case "$OS_TYPE" in
  Darwin)
    if command -v brew &>/dev/null; then
      PKG_MGR="brew"; PKG_INSTALL="brew install"
    fi ;;
  Linux)
    if   command -v apt-get &>/dev/null; then PKG_MGR="apt";    PKG_INSTALL="sudo apt-get install -y"
    elif command -v dnf     &>/dev/null; then PKG_MGR="dnf";    PKG_INSTALL="sudo dnf install -y"
    elif command -v yum     &>/dev/null; then PKG_MGR="yum";    PKG_INSTALL="sudo yum install -y"
    elif command -v pacman  &>/dev/null; then PKG_MGR="pacman"; PKG_INSTALL="sudo pacman -S --noconfirm"
    elif command -v apk     &>/dev/null; then PKG_MGR="apk";    PKG_INSTALL="sudo apk add"
    fi ;;
esac

# Refresh package index once per run. Cloud VMs / fresh AMIs often have a
# stale or empty apt cache, which makes apt-cache + apt install fail to find
# packages that ARE in the repos. Run this lazily before the first install
# attempt and before any apt-cache lookup.
_PKG_INDEX_REFRESHED=false
_pkg_index_refresh() {
  [[ "$_PKG_INDEX_REFRESHED" == "true" ]] && return 0
  case "$PKG_MGR" in
    apt)    info "Refreshing apt package index..."; sudo apt-get update -qq 2>&1 | tail -2 ;;
    dnf)    info "Refreshing dnf package index...";  sudo dnf -q makecache 2>&1 | tail -2 || true ;;
    yum)    info "Refreshing yum package index...";  sudo yum -q makecache 2>&1 | tail -2 || true ;;
    pacman) info "Refreshing pacman package index..."; sudo pacman -Sy --noconfirm 2>&1 | tail -2 || true ;;
    apk)    info "Refreshing apk package index...";  sudo apk update 2>&1 | tail -2 || true ;;
    brew)   true ;;  # brew updates implicitly
  esac
  _PKG_INDEX_REFRESHED=true
}

# offer_install <human-name> <distro:packages> ...
# Each distro arg is "key:packages" — apt|dnf|yum|pacman|apk|brew
# Returns 0 if user accepted and install succeeded; 1 otherwise.
_offer_install() {
  local name="$1"; shift
  local pkgs=""
  for spec in "$@"; do
    if [[ "$spec" == "${PKG_MGR}:"* ]]; then pkgs="${spec#*:}"; break; fi
  done

  if [[ -z "$PKG_MGR" ]]; then
    warn "Cannot install '$name' automatically — no supported package manager detected on $OS_TYPE."
    return 1
  fi
  if [[ -z "$pkgs" ]]; then
    warn "No install recipe for '$name' on $PKG_MGR. Install it manually and re-run."
    return 1
  fi

  echo ""
  echo -e "  ${YLW}Missing:${RST} $name"
  echo -e "  ${DIM}Will run:${RST} $PKG_INSTALL $pkgs"
  if [[ "$ASSUME_YES" == "true" ]]; then
    info "Auto-accept (--yes flag) — installing $name"
  elif [[ ! -t 0 ]]; then
    warn "Non-interactive shell — cannot prompt. Run the command above manually, or re-run with --yes."
    return 1
  else
    read -r -p "  Install now? [Y/n] " _ans
    _ans="$(echo "${_ans:-Y}" | tr '[:upper:]' '[:lower:]')"
    if [[ "$_ans" != "y" && "$_ans" != "yes" ]]; then
      warn "Skipped install of '$name'. start.sh may fail later."
      return 1
    fi
  fi
  _pkg_index_refresh
  # shellcheck disable=SC2086
  if $PKG_INSTALL $pkgs; then
    ok "Installed $name"
    return 0
  else
    warn "Install of '$name' failed. Check output above."
    return 1
  fi
}

# Pick first viable Python (3.11-3.13). Cap at 3.13 — pydantic-core wheels for 3.14+ are unreliable.
_pick_python() {
  PYBIN=""; PYVER=""
  for c in python3.12 python3.13 python3.11 python3; do
    if command -v "$c" &>/dev/null; then
      local v maj min
      v=$("$c" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "0.0")
      maj=$(echo "$v" | cut -d. -f1); min=$(echo "$v" | cut -d. -f2)
      if [[ "$maj" -eq 3 && "$min" -ge 11 && "$min" -le 13 ]]; then
        PYBIN="$c"; PYVER="$v"; return 0
      fi
    fi
  done
  return 1
}

info "Validating prereqs (will prompt for any missing)..."

# ── Python 3.11-3.13 ──

# Add the deadsnakes PPA so old Ubuntu releases (20.04, 22.04, etc.) can install
# python3.11+ when their default universe repos lack it. No-op on non-apt systems.
_add_deadsnakes_ppa() {
  [[ "$PKG_MGR" != "apt" ]] && return 1
  echo ""
  echo -e "  ${YLW}Note:${RST} Neither python3.12 nor python3.11 are in this Ubuntu's default repos."
  echo -e "  ${DIM}Will add the deadsnakes PPA (https://launchpad.net/~deadsnakes) to install a newer Python.${RST}"
  if [[ "$ASSUME_YES" != "true" && -t 0 ]]; then
    read -r -p "  Add deadsnakes PPA now? [Y/n] " _ans
    _ans="$(echo "${_ans:-Y}" | tr '[:upper:]' '[:lower:]')"
    if [[ "$_ans" != "y" && "$_ans" != "yes" ]]; then
      warn "Skipped PPA — install python3.11 manually and re-run."
      return 1
    fi
  fi
  if ! command -v add-apt-repository &>/dev/null; then
    info "Installing software-properties-common (provides add-apt-repository)..."
    sudo apt-get install -y -qq software-properties-common || {
      warn "Could not install software-properties-common."
      return 1
    }
  fi
  info "Adding ppa:deadsnakes/ppa..."
  # add-apt-repository writes to /etc/apt/sources.list.d/. Run apt-get update
  # explicitly afterwards so the PPA's index lands in /var/lib/apt/lists/.
  # Stream output (no pipe) so failures surface and don't mask the real error.
  if sudo add-apt-repository -y ppa:deadsnakes/ppa; then
    info "Refreshing apt index after PPA add..."
    sudo apt-get update 2>&1 | grep -E "^(Hit|Get|Err|W:|E:)" | tail -10 || true
    _PKG_INDEX_REFRESHED=true
    return 0
  fi
  return 1
}

# Check whether a package has at least one installable version.
# apt-cache show returns 0 for any package the cache knows about, including
# 'no installation candidate' phantoms. apt-cache madison only lists rows
# when an installable version actually exists.
_apt_pkg_installable() {
  apt-cache madison "$1" 2>/dev/null | grep -q .
}

# Bootstrap Python via uv when apt/dnf/etc. cannot supply 3.11+.
# uv ships standalone, statically-linked Python builds that work on any Linux
# regardless of distro version. Used as a last-resort fallback when:
#   - Ubuntu codename is too new/old for deadsnakes
#   - User on bleeding-edge non-LTS Ubuntu (resolute, oracular, etc.)
# After install, uv-managed Python is symlinked into ~/.local/bin so the
# normal _pick_python loop finds it.
_install_python_via_uv() {
  local target_ver="${1:-3.12}"

  echo ""
  echo -e "  ${YLW}Fallback:${RST} Installing Python ${target_ver} via uv (https://github.com/astral-sh/uv)"
  echo -e "  ${DIM}Why: deadsnakes PPA has no python3.11/3.12 build for your Ubuntu codename.${RST}"
  if [[ "$ASSUME_YES" != "true" && -t 0 ]]; then
    read -r -p "  Use uv to install Python ${target_ver}? [Y/n] " _ans
    _ans="$(echo "${_ans:-Y}" | tr '[:upper:]' '[:lower:]')"
    if [[ "$_ans" != "y" && "$_ans" != "yes" ]]; then
      return 1
    fi
  fi

  if ! command -v uv &>/dev/null; then
    info "Installing uv (single-binary Python installer)..."
    if ! curl -LsSf https://astral.sh/uv/install.sh | sh 2>&1 | tail -5; then
      warn "uv install failed."
      return 1
    fi
    export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
  fi

  info "Installing Python ${target_ver} via uv..."
  if ! uv python install "${target_ver}" 2>&1 | tail -5; then
    warn "uv python install failed."
    return 1
  fi

  # Symlink the uv-managed Python into ~/.local/bin so the validator finds it.
  local uv_py
  uv_py="$(uv python find "${target_ver}" 2>/dev/null || true)"
  if [[ -z "$uv_py" || ! -x "$uv_py" ]]; then
    warn "uv reported success but no python ${target_ver} binary found."
    return 1
  fi
  mkdir -p "$HOME/.local/bin"
  ln -sf "$uv_py" "$HOME/.local/bin/python${target_ver}"
  ln -sf "$uv_py" "$HOME/.local/bin/python3.${target_ver#3.}"
  export PATH="$HOME/.local/bin:$PATH"
  ok "Python ${target_ver} installed via uv at $uv_py"
  return 0
}

_PY_INSTALLED_VIA_UV=false
if ! _pick_python; then
  # Distro recipes — apt prefers python3.12, falls back to 3.11
  _PY_PKG_APT="python3.12 python3.12-venv python3-pip"
  if [[ "$PKG_MGR" == "apt" ]]; then
    # Refresh cache first — fresh cloud VMs often have empty apt lists
    _pkg_index_refresh
    if ! _apt_pkg_installable python3.12; then
      if _apt_pkg_installable python3.11; then
        _PY_PKG_APT="python3.11 python3.11-venv python3-pip"
        info "python3.12 not installable — using python3.11 instead"
      else
        # Neither installable from default repos. Try deadsnakes PPA.
        if _add_deadsnakes_ppa; then
          if _apt_pkg_installable python3.12; then
            _PY_PKG_APT="python3.12 python3.12-venv python3-pip"
            info "python3.12 available via deadsnakes PPA"
          elif _apt_pkg_installable python3.11; then
            _PY_PKG_APT="python3.11 python3.11-venv python3-pip"
            info "python3.11 available via deadsnakes PPA"
          else
            UBUNTU_CODENAME=$(lsb_release -cs 2>/dev/null || echo unknown)
            warn "deadsnakes PPA has no python3.11/3.12 build for Ubuntu '$UBUNTU_CODENAME' (likely too new or too old)."
            # Last-resort: install Python via uv standalone builds. Works on any glibc Linux.
            if _install_python_via_uv "3.12" && _pick_python; then
              ok "Python $PYVER ($PYBIN) — installed via uv"
              _PY_INSTALLED_VIA_UV=true
            else
              die "Could not install Python 3.11+ via apt or uv.
  Manual options:
    1. pyenv (build Python from source): https://github.com/pyenv/pyenv
    2. Switch to a supported Ubuntu LTS (22.04, 24.04) and re-run.
    3. Install Python yourself, ensure it's in PATH, and re-run."
            fi
          fi
        else
          # PPA add itself failed — try uv as a final fallback
          warn "Could not add deadsnakes PPA. Trying uv as a fallback..."
          if _install_python_via_uv "3.12" && _pick_python; then
            ok "Python $PYVER ($PYBIN) — installed via uv"
            _PY_INSTALLED_VIA_UV=true
          else
            die "Python 3.11+ not in apt repos and uv fallback failed. Manual install required:
    sudo add-apt-repository -y ppa:deadsnakes/ppa
    sudo apt-get update
    sudo apt-get install -y python3.11 python3.11-venv python3-pip
  Then re-run ./start.sh"
          fi
        fi
      fi
    fi
  fi

  # Skip the apt/dnf install if we already got Python from uv.
  if [[ "$_PY_INSTALLED_VIA_UV" != "true" ]]; then
    _offer_install "Python 3.11+" \
      "apt:$_PY_PKG_APT" \
      "dnf:python3.12 python3.12-pip" \
      "yum:python3.12 python3.12-pip" \
      "pacman:python python-pip" \
      "apk:python3 py3-pip py3-virtualenv" \
      "brew:python@3.12" || die "Python 3.11+ is required."
    if ! _pick_python; then
      die "Python 3.11-3.13 still not detected after install. Try installing manually."
    fi
  fi
fi
ok "Python $PYVER ($PYBIN)"

# ── venv module ──
# import venv works even if ensurepip is missing (pip-less venv stdlib),
# but `python -m venv` needs ensurepip too. Test full path with a throwaway venv.
_VENV_TEST_DIR="$(mktemp -d -t venvchk.XXXXXX)"
if ! $PYBIN -m venv "$_VENV_TEST_DIR" &>/tmp/_venv_probe; then
  rm -rf "$_VENV_TEST_DIR"
  if grep -q "ensurepip" /tmp/_venv_probe 2>/dev/null; then
    _offer_install "Python venv module" \
      "apt:${PYBIN}-venv" \
      "dnf:python3-virtualenv" \
      "yum:python3-virtualenv" \
      "pacman:python" \
      "apk:py3-virtualenv" \
      "brew:python@3.12" || die "Python venv module is required."
  else
    cat /tmp/_venv_probe >&2
    die "venv probe failed for $PYBIN"
  fi
else
  rm -rf "$_VENV_TEST_DIR"
fi
rm -f /tmp/_venv_probe

# ── pip ──
if ! $PYBIN -m pip --version &>/dev/null; then
  _offer_install "pip" \
    "apt:python3-pip" \
    "dnf:python3-pip" \
    "yum:python3-pip" \
    "pacman:python-pip" \
    "apk:py3-pip" \
    "brew:python@3.12" || die "pip is required."
fi

# ── curl (used by webhook health check + Jenkins setup) ──
if ! command -v curl &>/dev/null; then
  _offer_install "curl" \
    "apt:curl" "dnf:curl" "yum:curl" "pacman:curl" "apk:curl" "brew:curl" \
    || warn "curl missing — health checks will not work."
fi

# ── 2. Virtualenv ────────────────────────────────────────────
VENV_DIR=".venv"
if [[ ! -d "$VENV_DIR" ]]; then
  info "Creating virtualenv in .venv ..."
  set +e
  VENV_OUT=$($PYBIN -m venv "$VENV_DIR" 2>&1)
  VENV_RC=$?
  set -e
  if [[ $VENV_RC -ne 0 ]]; then
    echo "$VENV_OUT" >&2
    die "Failed to create virtualenv with $PYBIN"
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

# Fallback: load Anthropic key from macOS Keychain if not set in .env (no-op on Linux/Windows)
if [[ -z "${ANTHROPIC_API_KEY:-}" && "$(uname -s)" == "Darwin" ]] && command -v security &>/dev/null; then
  _kc_key=$(security find-generic-password -s "anthropic" -w 2>/dev/null || true)
  if [[ -n "$_kc_key" ]]; then
    export ANTHROPIC_API_KEY="$_kc_key"
    ok "ANTHROPIC_API_KEY loaded from macOS Keychain"
  fi
  unset _kc_key
fi

# ── 4a. Data directory (profiles, audit log) ─────────────────
DATA_DIR="${DATA_DIR:-$HOME/.devops-ai}"
mkdir -p "$DATA_DIR"
export DATA_DIR
ok "Data directory: $DATA_DIR"

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

# ── 4b. Redis cache (optional) ───────────────────────────────
# Already-running Redis -> use it. Else offer install via unified validator
# (default N — purely optional). Falls back to in-memory cache silently.
REDIS_URL="${REDIS_URL:-}"
if [[ -z "$REDIS_URL" ]]; then
  if command -v redis-cli &>/dev/null && redis-cli -t 2 ping &>/dev/null 2>&1; then
    ok "Redis already running"
    export REDIS_URL="redis://localhost:6379"
  elif [[ ! -t 0 ]]; then
    info "Skipping Redis (non-interactive) — using in-memory cache"
  else
    echo ""
    echo -e "  ${YLW}Optional:${RST} Redis (persistent LLM response cache, 24hr TTL)"
    echo -e "  ${DIM}Without Redis: in-memory cache only (lost on restart)${RST}"
    read -r -p "  Install Redis? [y/N] " _ans
    _ans="$(echo "${_ans:-N}" | tr '[:upper:]' '[:lower:]')"
    if [[ "$_ans" == "y" || "$_ans" == "yes" ]]; then
      _redis_pkg=""
      case "$PKG_MGR" in
        apt|dnf|yum) _redis_pkg="redis" ;;
        brew)        _redis_pkg="redis" ;;
        pacman)      _redis_pkg="redis" ;;
        apk)         _redis_pkg="redis" ;;
      esac
      if [[ -n "$PKG_MGR" && -n "$_redis_pkg" ]]; then
        # apt package is named redis-server
        [[ "$PKG_MGR" == "apt" ]] && _redis_pkg="redis-server"
        # shellcheck disable=SC2086
        if $PKG_INSTALL $_redis_pkg; then
          ok "Installed Redis"
          if command -v redis-server &>/dev/null; then
            redis-server --daemonize yes --loglevel warning &>/dev/null && sleep 1
            if redis-cli -t 2 ping &>/dev/null 2>&1; then
              export REDIS_URL="redis://localhost:6379"
              ok "Redis started"
            fi
          fi
        else
          warn "Redis install failed — using in-memory cache"
        fi
      else
        warn "No package manager support for Redis on $OS_TYPE — using in-memory cache"
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
# lsof is the most reliable on macOS/Linux. Skip silently if not available
# (e.g. minimal Linux containers, Windows Git Bash) — uvicorn will fail loudly
# below if the port is taken, which is acceptable in that environment.
if command -v lsof &>/dev/null && lsof -iTCP:"$PORT" -sTCP:LISTEN &>/dev/null; then
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

_open_browser() {
  local url="$1"
  case "$(uname -s)" in
    Darwin)         open "$url" 2>/dev/null ;;
    Linux)          xdg-open "$url" 2>/dev/null ;;
    MINGW*|CYGWIN*|MSYS*) start "$url" 2>/dev/null ;;
    *)              true ;;  # silent on unknown OS
  esac
}

if [[ "$OPEN_BROWSER" == "true" ]]; then
  ( sleep 2 && _open_browser "http://localhost:${PORT}" || true ) &
fi

exec python -m uvicorn webhook.server:app \
  --host 0.0.0.0 \
  --port "$PORT" \
  --workers "$WORKERS" \
  --log-level info
