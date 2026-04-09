# Ollama Setup — M4 MacBook Air

Hardware target: M4 MacBook Air, 32GB unified memory, 2TB Crucial external SSD

---

## Step 1 — Install Ollama

```bash
brew install ollama
```

Verify: `ollama --version`

---

## Step 2 — Configure External SSD Storage

Models are large (5–9GB each). Store them on the external SSD to keep internal 256GB free.

**2a. Set the env var for the current session:**
```bash
export OLLAMA_MODELS=/Volumes/SSD/ollama-models
mkdir -p /Volumes/SSD/ollama-models
```

**2b. Persist across reboots via launchd:**
```bash
launchctl setenv OLLAMA_MODELS /Volumes/SSD/ollama-models
```

**2c. Add to your shell profile (~/.zshrc):**
```bash
echo 'export OLLAMA_MODELS=/Volumes/SSD/ollama-models' >> ~/.zshrc
source ~/.zshrc
```

**2d. Edit the Ollama launchd plist to persist for the Ollama service:**
```bash
# Find the plist
ls ~/Library/LaunchAgents/ | grep ollama

# Edit it (replace with your actual path if different)
nano ~/Library/LaunchAgents/com.ollama.ollama.plist
```

Add this inside the `<dict>` section before `</dict>`:
```xml
<key>EnvironmentVariables</key>
<dict>
    <key>OLLAMA_MODELS</key>
    <string>/Volumes/SSD/ollama-models</string>
</dict>
```

Reload:
```bash
launchctl unload ~/Library/LaunchAgents/com.ollama.ollama.plist
launchctl load ~/Library/LaunchAgents/com.ollama.ollama.plist
```

---

## Step 3 — Pull Models

```bash
# Analysis model — fast log analysis (5GB)
ollama pull llama3.1:8b

# Generation model — code generation, Jenkinsfiles, YAML (9GB)
ollama pull qwen2.5-coder:14b
```

Total storage: ~14GB on external SSD.

---

## Step 4 — Verify

```bash
# List models
ollama list

# Expected output:
# NAME                         SIZE
# llama3.1:8b                  4.9 GB
# qwen2.5-coder:14b             9.0 GB

# Test API
curl http://localhost:11434/api/tags
# Should return JSON with both models listed

# Quick generation test
ollama run llama3.1:8b "Say hello in one sentence"
```

---

## Step 5 — Update .env

```bash
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODELS=/Volumes/SSD/ollama-models
OLLAMA_TIMEOUT=120
ANALYSIS_MODEL=llama3.1:8b
GENERATION_MODEL=qwen2.5-coder:14b
```

---

## Performance Notes (M4 Air)

- Both models run simultaneously: 5GB + 9GB + 8GB OS = ~22GB — 10GB buffer, no throttling
- M4 GPU cores accelerate inference automatically via Metal (no config needed)
- External SSD (Crucial) is fast enough — models load into unified memory at startup, SSD only used for initial load
- Sustained generation: Air will stay cool with these model sizes (no fan needed)

## Optional — Future Upgrade

If you later want to try `qwen3-coder:30b` or similar:
```bash
ollama show qwen3-coder:30b  # check size before pulling
ollama pull qwen3-coder:30b
# Then update .env: GENERATION_MODEL=qwen3-coder:30b
# Zero code changes needed
```
