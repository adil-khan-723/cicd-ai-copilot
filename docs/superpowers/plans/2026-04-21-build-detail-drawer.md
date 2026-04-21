# Build Detail Drawer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a slide-out right-panel drawer to the Pipeline Feed that shows full Jenkins console logs and tool crawler verification results when a failed build card is clicked.

**Architecture:** Backend emits `VerificationReport` data inside the existing `analysis_complete` SSE event (zero new processing) and adds a `GET /api/build-log` endpoint that fetches console output on demand from Jenkins. Frontend adds a `BuildDetailDrawer` component that renders a terminal-style log viewer and a three-section Tool Crawler tab from data already in the build card.

**Tech Stack:** FastAPI (python-jenkins for log fetch), React + Framer Motion + Tailwind CSS, TypeScript, pytest

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `webhook/server.py` | Modify | Serialize `VerificationReport` into `analysis_complete` event |
| `ui/routes.py` | Modify | Add `GET /api/build-log` endpoint |
| `frontend/src/types/index.ts` | Modify | Add `VerificationData`, `VerificationToolMismatch` types; extend `AnalysisCompleteEvent` |
| `frontend/src/components/BuildDetailDrawer.tsx` | Create | Slide-out drawer with Logs + Tool Crawler tabs |
| `frontend/src/components/BuildCard.tsx` | Modify | Add `onOpenDetail` prop; make job name clickable |
| `frontend/src/components/PipelineFeed.tsx` | Modify | Thread `onOpenDetail` prop to `BuildCard` |
| `frontend/src/App.tsx` | Modify | Add `selectedCard` state; render `BuildDetailDrawer` |
| `tests/test_ui_routes.py` | Modify | Add three tests for `/api/build-log` |
| `tests/test_webhook_server.py` | Create | Verify `analysis_complete` event includes `verification` field |

---

## Task 1: Extend `analysis_complete` SSE event with verification data

**Files:**
- Modify: `webhook/server.py` (around line 351 — the `analysis_complete` bus.publish call)
- Create: `tests/test_webhook_server.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_webhook_server.py
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from webhook.server import app

client = TestClient(app)

MOCK_PAYLOAD = {
    "job_name": "test-job",
    "build_number": "1",
    "failed_stage": "Build",
    "status": "FAILURE",
    "stages": [{"name": "Build", "status": "failed"}],
    "log": "error: command not found",
}


def test_analysis_complete_includes_verification():
    """analysis_complete SSE event must include a verification key."""
    from ui.event_bus import bus

    published = []
    original_publish = bus.publish

    def capture(event):
        published.append(event)
        original_publish(event)

    mock_provider = MagicMock()
    mock_provider.complete.return_value = '{"root_cause":"test","fix_suggestion":"retry","fix_type":"retry","confidence":0.9}'

    with patch.object(bus, "publish", side_effect=capture), \
         patch("analyzer.llm_client.get_provider", return_value=mock_provider), \
         patch("webhook.server._run_verification") as mock_verify:
        from verification.models import VerificationReport
        mock_verify.return_value = VerificationReport(
            platform="jenkins",
            missing_credentials=["MY_SECRET"],
        )
        from webhook.server import _process_failure_sync
        _process_failure_sync(MOCK_PAYLOAD, "jenkins")

    analysis_events = [e for e in published if e.get("type") == "analysis_complete"]
    assert len(analysis_events) == 1
    ev = analysis_events[0]
    assert "verification" in ev
    v = ev["verification"]
    assert "matched_tools" in v
    assert "mismatched_tools" in v
    assert "missing_plugins" in v
    assert "missing_credentials" in v
    assert "errors" in v
    assert "MY_SECRET" in v["missing_credentials"]
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/oggy/PlatformTool && python -m pytest tests/test_webhook_server.py::test_analysis_complete_includes_verification -v
```
Expected: `FAILED` — `AssertionError: assert "verification" in ev`

- [ ] **Step 3: Add verification serialization to `_process_failure_sync`**

In `webhook/server.py`, find the `analysis_complete` bus.publish call (around line 351). Add the `verification` key:

```python
        # Step 5: Always emit analysis_complete so the UI card renders
        bus.publish({
            "type": "analysis_complete",
            "job": ctx.job_name,
            "build": ctx.build_number,
            "failed_stage": ctx.failed_stage,
            "root_cause": analysis.get("root_cause", ""),
            "fix_suggestion": analysis.get("fix_suggestion", ""),
            "fix_type": analysis.get("fix_type"),
            "confidence": analysis.get("confidence", 0),
            "log_excerpt": cleaned[:400],
            "pipeline_stages": [
                {"name": name, "status": status}
                for name, status in ctx.pipeline_stages
            ],
            "verification": {
                "matched_tools": report.matched_tools,
                "mismatched_tools": [
                    {
                        "referenced": m.referenced,
                        "configured": m.configured,
                        "match_score": m.match_score,
                    }
                    for m in report.mismatched_tools
                ],
                "missing_plugins": report.missing_plugins,
                "missing_credentials": report.missing_credentials,
                "errors": report.errors,
            },
        })
```

Note: `report` is already in scope — it's the return value of `_run_verification(ctx, payload)` assigned a few lines above. No other changes needed.

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /Users/oggy/PlatformTool && python -m pytest tests/test_webhook_server.py::test_analysis_complete_includes_verification -v
```
Expected: `PASSED`

- [ ] **Step 5: Run full test suite to check for regressions**

```bash
cd /Users/oggy/PlatformTool && python -m pytest tests/ -v --tb=short 2>&1 | tail -20
```
Expected: all existing tests pass.

- [ ] **Step 6: Commit**

```bash
git add webhook/server.py tests/test_webhook_server.py
git commit -m "feat(sse): include VerificationReport in analysis_complete event"
```

---

## Task 2: Add `GET /api/build-log` endpoint

**Files:**
- Modify: `ui/routes.py`
- Modify: `tests/test_ui_routes.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_ui_routes.py`:

```python
def test_build_log_returns_text():
    mock_server = MagicMock()
    mock_server.get_build_console_output.return_value = "Started by user admin\n[Pipeline] Start of Pipeline\n"

    with patch("ui.routes.jenkins.Jenkins", return_value=mock_server), \
         patch("ui.routes.get_settings") as mock_settings:
        mock_settings.return_value.jenkins_url = "http://localhost:8080"
        mock_settings.return_value.jenkins_user = "admin"
        mock_settings.return_value.jenkins_token = "token"
        response = client.get("/api/build-log?job=my-job&build=42")

    assert response.status_code == 200
    data = response.json()
    assert "log" in data
    assert "Started by user admin" in data["log"]


def test_build_log_jenkins_not_configured():
    with patch("ui.routes.get_settings") as mock_settings:
        mock_settings.return_value.jenkins_url = ""
        mock_settings.return_value.jenkins_token = ""
        response = client.get("/api/build-log?job=my-job&build=42")
    assert response.status_code == 503


def test_build_log_not_found():
    import jenkins as jenkins_lib
    mock_server = MagicMock()
    mock_server.get_build_console_output.side_effect = jenkins_lib.NotFoundException()

    with patch("ui.routes.jenkins.Jenkins", return_value=mock_server), \
         patch("ui.routes.get_settings") as mock_settings:
        mock_settings.return_value.jenkins_url = "http://localhost:8080"
        mock_settings.return_value.jenkins_user = "admin"
        mock_settings.return_value.jenkins_token = "token"
        response = client.get("/api/build-log?job=my-job&build=42")

    assert response.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/oggy/PlatformTool && python -m pytest tests/test_ui_routes.py::test_build_log_returns_text tests/test_ui_routes.py::test_build_log_jenkins_not_configured tests/test_ui_routes.py::test_build_log_not_found -v
```
Expected: all three `FAILED` — `404 Not Found` (route doesn't exist yet)

- [ ] **Step 3: Implement the endpoint**

Add to `ui/routes.py`, after the existing `@router.get("/api/jobs")` block. Also add `import jenkins` near the top of the file (alongside other imports):

```python
# near top of ui/routes.py, add:
import jenkins
```

```python
# Add new endpoint after /api/jobs block:

@router.get("/api/build-log")
async def build_log(job: str, build: int):
    from config import get_settings
    s = get_settings()
    if not s.jenkins_url or not s.jenkins_token:
        raise HTTPException(status_code=503, detail="Jenkins not configured")

    def _fetch():
        server = jenkins.Jenkins(
            s.jenkins_url,
            username=s.jenkins_user or "",
            password=s.jenkins_token,
        )
        try:
            return server.get_build_console_output(job, build)
        except jenkins.NotFoundException:
            return None
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Could not fetch log from Jenkins: {e}")

    loop = asyncio.get_event_loop()
    try:
        log = await loop.run_in_executor(None, _fetch)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Could not fetch log from Jenkins: {e}")

    if log is None:
        raise HTTPException(status_code=404, detail="Build not found")

    return {"log": log}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/oggy/PlatformTool && python -m pytest tests/test_ui_routes.py -v --tb=short
```
Expected: all tests including the three new ones pass.

- [ ] **Step 5: Commit**

```bash
git add ui/routes.py tests/test_ui_routes.py
git commit -m "feat(api): add GET /api/build-log endpoint for Jenkins console output"
```

---

## Task 3: Extend TypeScript types

**Files:**
- Modify: `frontend/src/types/index.ts`

- [ ] **Step 1: Add verification types and extend `AnalysisCompleteEvent`**

Open `frontend/src/types/index.ts`. Add the two new interfaces and update `AnalysisCompleteEvent`:

```typescript
// Add before AnalysisCompleteEvent:
export interface VerificationToolMismatch {
  referenced: string
  configured: string
  match_score: number
}

export interface VerificationData {
  matched_tools: string[]
  mismatched_tools: VerificationToolMismatch[]
  missing_plugins: string[]
  missing_credentials: string[]
  errors: string[]
}
```

In `AnalysisCompleteEvent`, add the optional field:
```typescript
export interface AnalysisCompleteEvent {
  type: 'analysis_complete'
  job: string
  build: string | number
  failed_stage: string
  root_cause: string
  fix_suggestion: string
  fix_type: string
  confidence: number
  log_excerpt: string
  pipeline_stages: PipelineStage[]
  verification?: VerificationData   // ← add this line
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /Users/oggy/PlatformTool/frontend && npx tsc --noEmit 2>&1 | head -30
```
Expected: no errors output.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/types/index.ts
git commit -m "feat(types): add VerificationData types, extend AnalysisCompleteEvent"
```

---

## Task 4: Build `BuildDetailDrawer` component

**Files:**
- Create: `frontend/src/components/BuildDetailDrawer.tsx`

- [ ] **Step 1: Create the component**

Create `frontend/src/components/BuildDetailDrawer.tsx` with this full implementation:

```tsx
import { useState, useEffect, useRef, useCallback } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import {
  X, Copy, Check, ChevronDown, ChevronRight,
  Wrench, Puzzle, KeyRound, AlertTriangle, CheckCircle2,
  Loader2, ArrowDown, Terminal,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import type { BuildCard, VerificationData, VerificationToolMismatch } from '@/types'

interface BuildDetailDrawerProps {
  card: BuildCard | null
  onClose: () => void
}

type DrawerTab = 'logs' | 'crawler'

export function BuildDetailDrawer({ card, onClose }: BuildDetailDrawerProps) {
  const [tab, setTab] = useState<DrawerTab>('logs')

  // Reset to logs tab when a new card is selected
  useEffect(() => { if (card) setTab('logs') }, [card?.key])

  // Close on Escape key
  useEffect(() => {
    function onKey(e: KeyboardEvent) { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <AnimatePresence>
      {card && (
        <>
          {/* Backdrop */}
          <motion.div
            key="backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            className="fixed inset-0 z-40 bg-black/20"
            onClick={onClose}
          />

          {/* Drawer panel */}
          <motion.div
            key="drawer"
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ type: 'spring', stiffness: 400, damping: 38 }}
            className="fixed right-0 top-0 bottom-0 z-50 flex flex-col bg-surface border-l border-accent-border/60 shadow-2xl"
            style={{ width: 'clamp(480px, 45vw, 720px)' }}
          >
            {/* Header */}
            <div className="flex items-center gap-3 px-5 py-3.5 border-b border-accent-border/40 shrink-0 bg-white">
              <Terminal className="h-4 w-4 text-text-dim shrink-0" strokeWidth={1.5} />
              <span className="font-mono text-[14px] font-semibold text-text-primary truncate flex-1">
                {card.job}
              </span>
              <span className="flex items-center gap-1 text-[11px] font-mono text-text-muted bg-overlay/60 border border-accent-border/40 rounded-lg px-2 py-1 shrink-0">
                #{card.build}
              </span>
              {card.analysis?.failed_stage && (
                <span className="text-[11px] font-mono bg-error-dim text-error border border-error-border rounded-lg px-2 py-1 shrink-0 max-w-[160px] truncate">
                  failed: {card.analysis.failed_stage}
                </span>
              )}
              <button
                onClick={onClose}
                className="ml-1 text-text-dim hover:text-text-primary transition-colors cursor-pointer shrink-0"
                aria-label="Close drawer"
              >
                <X className="h-4 w-4" strokeWidth={1.5} />
              </button>
            </div>

            {/* Tab bar */}
            <div className="flex items-center gap-1 px-4 py-2 border-b border-accent-border/40 shrink-0 bg-surface/80">
              {(['logs', 'crawler'] as DrawerTab[]).map(t => (
                <button
                  key={t}
                  onClick={() => setTab(t)}
                  className={cn(
                    'px-3.5 py-1.5 rounded-lg text-[12px] font-mono border transition-all duration-150 cursor-pointer',
                    tab === t
                      ? 'border-accent-border bg-white text-accent font-semibold shadow-sm'
                      : 'border-accent-border/30 bg-white/40 text-text-muted hover:text-text-base hover:bg-white/70 hover:border-accent-border/60',
                  )}
                >
                  {t === 'logs' ? 'Logs' : 'Tool Crawler'}
                </button>
              ))}
            </div>

            {/* Tab content */}
            <div className="flex-1 overflow-hidden">
              {tab === 'logs' && (
                <LogsTab
                  job={String(card.job)}
                  build={Number(card.build)}
                  failedStage={card.analysis?.failed_stage}
                />
              )}
              {tab === 'crawler' && (
                <CrawlerTab verification={card.analysis?.verification} />
              )}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}

// ─── Logs Tab ────────────────────────────────────────────────────────────────

interface LogsTabProps {
  job: string
  build: number
  failedStage?: string
}

function LogsTab({ job, build, failedStage }: LogsTabProps) {
  const [log, setLog]       = useState<string | null>(null)
  const [error, setError]   = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [copied, setCopied] = useState(false)
  const failedLineRef       = useRef<HTMLDivElement>(null)
  const scrollRef           = useRef<HTMLDivElement>(null)

  const fetchLog = useCallback(() => {
    setLoading(true)
    setError(null)
    fetch(`/api/build-log?job=${encodeURIComponent(job)}&build=${build}`)
      .then(async r => {
        if (!r.ok) {
          const data = await r.json().catch(() => ({}))
          throw new Error(data.detail ?? `HTTP ${r.status}`)
        }
        return r.json()
      })
      .then(data => setLog(data.log ?? ''))
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [job, build])

  useEffect(() => { fetchLog() }, [fetchLog])

  function jumpToFailed() {
    failedLineRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }

  function copyLog() {
    if (!log) return
    navigator.clipboard.writeText(log).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-full bg-zinc-950 gap-3">
        <Loader2 className="h-6 w-6 text-zinc-400 animate-spin" strokeWidth={1.5} />
        <p className="text-[12px] font-mono text-zinc-500">Fetching log from Jenkins...</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-full bg-zinc-950 gap-4">
        <AlertTriangle className="h-8 w-8 text-red-500" strokeWidth={1.5} />
        <p className="text-[13px] font-mono text-zinc-300">Failed to load log</p>
        <p className="text-[11px] font-mono text-zinc-500 max-w-xs text-center">{error}</p>
        <button
          onClick={fetchLog}
          className="mt-2 px-4 py-2 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-[12px] font-mono border border-zinc-700 transition-colors cursor-pointer"
        >
          Retry
        </button>
      </div>
    )
  }

  const lines = (log ?? '').split('\n')

  // Detect failed stage line range
  let failedStart = -1
  let failedEnd   = lines.length
  if (failedStage) {
    const startPattern = `[Pipeline] { (${failedStage})`
    for (let i = 0; i < lines.length; i++) {
      if (lines[i].includes(startPattern)) { failedStart = i; break }
    }
    if (failedStart >= 0) {
      for (let i = failedStart + 1; i < lines.length; i++) {
        if (lines[i].includes('[Pipeline] }')) { failedEnd = i; break }
      }
    }
  }

  const inFailedRange = (i: number) => failedStart >= 0 && i >= failedStart && i <= failedEnd

  return (
    <div className="flex flex-col h-full bg-zinc-950">
      {/* Toolbar */}
      <div className="flex items-center gap-2 px-3 py-2 border-b border-zinc-800 shrink-0">
        {failedStage && failedStart >= 0 && (
          <button
            onClick={jumpToFailed}
            className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-red-950/60 hover:bg-red-950/80 border border-red-900/60 text-red-400 text-[11px] font-mono transition-colors cursor-pointer"
          >
            <ArrowDown className="h-3 w-3" strokeWidth={2} />
            Jump to failed stage
          </button>
        )}
        {failedStage && (
          <span className="text-[11px] font-mono text-red-400 bg-red-950/40 border border-red-900/40 rounded-md px-2 py-1 truncate max-w-[200px]">
            {failedStage}
          </span>
        )}
        <div className="flex-1" />
        <button
          onClick={copyLog}
          className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-zinc-800 hover:bg-zinc-700 border border-zinc-700 text-zinc-400 hover:text-zinc-200 text-[11px] font-mono transition-colors cursor-pointer"
        >
          {copied ? <Check className="h-3 w-3 text-green-400" strokeWidth={2} /> : <Copy className="h-3 w-3" strokeWidth={1.5} />}
          {copied ? 'Copied' : 'Copy'}
        </button>
      </div>

      {/* Log lines */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto">
        <div className="py-2">
          {lines.map((line, i) => {
            const isFirst = failedStart >= 0 && i === failedStart
            return (
              <div
                key={i}
                ref={isFirst ? failedLineRef : undefined}
                className={cn(
                  'flex items-start group',
                  inFailedRange(i)
                    ? 'bg-red-950/20 border-l-2 border-red-500/70'
                    : 'border-l-2 border-transparent',
                )}
              >
                <span className="select-none w-10 text-right pr-3 text-[11px] font-mono text-zinc-600 shrink-0 leading-[1.6] pt-px">
                  {i + 1}
                </span>
                <span className={cn(
                  'flex-1 text-[12px] font-mono leading-[1.6] whitespace-pre-wrap break-all pr-4',
                  inFailedRange(i) ? 'text-zinc-200' : 'text-zinc-400',
                )}>
                  {line || ' '}
                </span>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}

// ─── Tool Crawler Tab ─────────────────────────────────────────────────────────

function CrawlerTab({ verification }: { verification?: VerificationData }) {
  if (!verification) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-3 text-center px-8">
        <AlertTriangle className="h-8 w-8 text-text-dim" strokeWidth={1.5} />
        <p className="text-[13px] font-semibold text-text-base">No verification data available</p>
        <p className="text-[12px] font-mono text-text-muted">This build was processed before tool crawling was enabled.</p>
      </div>
    )
  }

  const hasTools   = verification.matched_tools.length > 0 || verification.mismatched_tools.length > 0
  const hasPlugins = verification.missing_plugins.length > 0
  const hasCreds   = verification.missing_credentials.length > 0
  const hasErrors  = verification.errors.length > 0
  const allClean   = !hasTools && !hasPlugins && !hasCreds && !hasErrors

  if (allClean) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-3 text-center px-8">
        <CheckCircle2 className="h-10 w-10 text-success" strokeWidth={1.5} />
        <p className="text-[13px] font-semibold text-text-base">Nothing to verify</p>
        <p className="text-[12px] font-mono text-text-muted">No tools or credentials referenced in this Jenkinsfile.</p>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full overflow-y-auto">
      {hasErrors && (
        <div className="mx-4 mt-4 flex items-start gap-2.5 px-3.5 py-3 rounded-xl bg-warning-dim border border-warning/40">
          <AlertTriangle className="h-4 w-4 text-warning shrink-0 mt-0.5" strokeWidth={2} />
          <p className="text-[12px] font-mono text-warning leading-relaxed">
            Tool crawler could not fully verify — Jenkins API returned errors. Results may be incomplete.
          </p>
        </div>
      )}

      <div className="flex flex-col gap-3 p-4">
        <CrawlerSection
          icon={<Wrench className="h-3.5 w-3.5" strokeWidth={2} />}
          label="Tools"
          issueCount={verification.mismatched_tools.length}
        >
          {!hasTools ? (
            <EmptyRow text="No tools declared in Jenkinsfile" />
          ) : (
            <>
              {verification.matched_tools.map(name => (
                <ToolRow key={name} status="ok" label={name} />
              ))}
              {verification.mismatched_tools.map((m, i) => (
                <MismatchRow key={i} mismatch={m} />
              ))}
            </>
          )}
        </CrawlerSection>

        <CrawlerSection
          icon={<Puzzle className="h-3.5 w-3.5" strokeWidth={2} />}
          label="Plugins"
          issueCount={verification.missing_plugins.length}
        >
          {!hasPlugins ? (
            <ToolRow status="ok" label="All required plugins installed" />
          ) : (
            verification.missing_plugins.map(p => (
              <ToolRow key={p} status="missing" label={p} sublabel="not installed" />
            ))
          )}
        </CrawlerSection>

        <CrawlerSection
          icon={<KeyRound className="h-3.5 w-3.5" strokeWidth={2} />}
          label="Credentials"
          issueCount={verification.missing_credentials.length}
        >
          {!hasCreds ? (
            <ToolRow status="ok" label="All credentials found" />
          ) : (
            verification.missing_credentials.map(c => (
              <ToolRow key={c} status="missing" label={c} sublabel="not found in Jenkins" />
            ))
          )}
        </CrawlerSection>
      </div>
    </div>
  )
}

// ─── Crawler sub-components ───────────────────────────────────────────────────

function CrawlerSection({
  icon, label, issueCount, children,
}: {
  icon: React.ReactNode
  label: string
  issueCount: number
  children: React.ReactNode
}) {
  const [open, setOpen] = useState(true)
  const hasIssues = issueCount > 0

  return (
    <div className="rounded-xl border border-accent-border/40 overflow-hidden bg-white">
      <button
        onClick={() => setOpen(v => !v)}
        className="flex items-center gap-2.5 w-full px-4 py-3 hover:bg-overlay/30 transition-colors cursor-pointer"
      >
        <span className={cn('text-text-dim', hasIssues && 'text-error')}>{icon}</span>
        <span className="text-[12px] font-mono font-semibold text-text-base flex-1 text-left">{label}</span>
        {hasIssues ? (
          <span className="text-[10px] font-mono bg-error-dim text-error border border-error-border rounded-full px-2 py-0.5">
            {issueCount} issue{issueCount !== 1 ? 's' : ''}
          </span>
        ) : (
          <span className="text-[10px] font-mono bg-success-dim text-success border border-success-border rounded-full px-2 py-0.5">
            ok
          </span>
        )}
        <span className="text-text-dim ml-1">
          {open
            ? <ChevronDown className="h-3.5 w-3.5" strokeWidth={2} />
            : <ChevronRight className="h-3.5 w-3.5" strokeWidth={2} />}
        </span>
      </button>
      {open && (
        <div className="border-t border-accent-border/30 divide-y divide-accent-border/20">
          {children}
        </div>
      )}
    </div>
  )
}

function ToolRow({ status, label, sublabel }: { status: 'ok' | 'missing'; label: string; sublabel?: string }) {
  return (
    <div className="flex items-center gap-3 px-4 py-2.5">
      {status === 'ok' ? (
        <CheckCircle2 className="h-3.5 w-3.5 text-success shrink-0" strokeWidth={2} />
      ) : (
        <AlertTriangle className="h-3.5 w-3.5 text-error shrink-0" strokeWidth={2} />
      )}
      <span className={cn('text-[12px] font-mono flex-1', status === 'ok' ? 'text-text-base' : 'text-error')}>
        {label}
      </span>
      {sublabel && (
        <span className="text-[11px] font-mono text-text-dim">{sublabel}</span>
      )}
    </div>
  )
}

function MismatchRow({ mismatch }: { mismatch: VerificationToolMismatch }) {
  const pct = Math.round(mismatch.match_score * 100)
  return (
    <div className="flex items-center gap-3 px-4 py-2.5">
      <AlertTriangle className="h-3.5 w-3.5 text-warning shrink-0" strokeWidth={2} />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 text-[12px] font-mono">
          <span className="text-warning">&quot;{mismatch.referenced}&quot;</span>
          <span className="text-text-dim">→</span>
          <span className="text-text-base">&quot;{mismatch.configured}&quot;</span>
        </div>
        <div className="mt-1.5 flex items-center gap-2">
          <div className="flex-1 h-1 rounded-full bg-accent-border/30 overflow-hidden">
            <div
              className="h-full rounded-full bg-warning"
              style={{ width: `${pct}%` }}
            />
          </div>
          <span className="text-[10px] font-mono text-text-dim shrink-0">{pct}% match</span>
        </div>
      </div>
    </div>
  )
}

function EmptyRow({ text }: { text: string }) {
  return (
    <div className="px-4 py-2.5 text-[12px] font-mono text-text-dim">{text}</div>
  )
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /Users/oggy/PlatformTool/frontend && npx tsc --noEmit 2>&1 | head -30
```
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/BuildDetailDrawer.tsx
git commit -m "feat(ui): add BuildDetailDrawer with Logs + Tool Crawler tabs"
```

---

## Task 5: Wire drawer into App, PipelineFeed, and BuildCard

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/PipelineFeed.tsx`
- Modify: `frontend/src/components/BuildCard.tsx`

- [ ] **Step 1: Update `App.tsx`**

Add import and state. Find the imports block at top of `frontend/src/App.tsx` and add:
```tsx
import { BuildDetailDrawer } from '@/components/BuildDetailDrawer'
```

Add `selectedCard` state after the existing `wireStatus` state:
```tsx
const [selectedCard, setSelectedCard] = useState<BuildCard | null>(null)
```

Update the `PipelineFeed` render to pass `onOpenDetail`:
```tsx
<PipelineFeed
  cards={cardList}
  onDismiss={dismissCard}
  onClearAll={clearFeed}
  onDiscardJob={discardJob}
  onOpenDetail={setSelectedCard}
/>
```

Add `BuildDetailDrawer` render right before the closing `</div>` of the outermost `<div className="flex h-screen ...">`:
```tsx
      <BuildDetailDrawer card={selectedCard} onClose={() => setSelectedCard(null)} />
    </div>
  )
}
```

- [ ] **Step 2: Update `PipelineFeed.tsx`**

Add `onOpenDetail` to the `PipelineFeedProps` interface:
```tsx
interface PipelineFeedProps {
  cards:          BuildCardType[]
  onDismiss:      (k: string) => void
  onClearAll:     () => void
  onDiscardJob:   (job: string) => void
  onOpenDetail:   (card: BuildCardType) => void
}
```

Update the function signature:
```tsx
export function PipelineFeed({ cards, onDismiss, onClearAll, onDiscardJob, onOpenDetail }: PipelineFeedProps) {
```

Pass `onOpenDetail` down to each `BuildCard` render (there is one `<BuildCard>` call around line 125):
```tsx
<BuildCard key={card.key} card={card} onDismiss={onDismiss} onOpenDetail={onOpenDetail} />
```

- [ ] **Step 3: Update `BuildCard.tsx`**

Add `onOpenDetail` to the `BuildCard` function props. Find the function signature:
```tsx
export function BuildCard({ card, onDismiss }: { card: BuildCardType; onDismiss: (k: string) => void }) {
```
Change to:
```tsx
export function BuildCard({ card, onDismiss, onOpenDetail }: {
  card: BuildCardType
  onDismiss: (k: string) => void
  onOpenDetail: (card: BuildCardType) => void
}) {
```

In the card header, make the job name span clickable. Find:
```tsx
<span className="text-[14px] font-semibold text-text-primary font-mono truncate flex-1">{card.job}</span>
```
Replace with:
```tsx
<span
  className="text-[14px] font-semibold text-text-primary font-mono truncate flex-1 cursor-pointer hover:text-accent transition-colors"
  onClick={e => { e.stopPropagation(); onOpenDetail(card) }}
  title="View logs and tool crawler"
>
  {card.job}
</span>
```

- [ ] **Step 4: Verify TypeScript compiles**

```bash
cd /Users/oggy/PlatformTool/frontend && npx tsc --noEmit 2>&1 | head -30
```
Expected: no errors.

- [ ] **Step 5: Build frontend**

```bash
cd /Users/oggy/PlatformTool/frontend && npm run build 2>&1 | tail -15
```
Expected: `✓ built in ...` with no errors. Output goes to `ui/static/assets/`.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/App.tsx frontend/src/components/PipelineFeed.tsx frontend/src/components/BuildCard.tsx
git commit -m "feat(ui): wire BuildDetailDrawer into App, PipelineFeed, BuildCard"
```

---

## Task 6: Create two test Jenkins jobs and end-to-end verification

This task creates two intentionally failing Jenkins pipeline jobs to verify the drawer works end-to-end. One job fails due to a **stage error** (command not found). The other fails due to a **missing credential**.

Prerequisites: Jenkins is running and configured in the app settings (`/api/settings` returns `configured: true`).

- [ ] **Step 1: Verify app is running**

```bash
cd /Users/oggy/PlatformTool && docker-compose up -d
# Wait ~5s, then:
curl -s http://localhost:8000/health
```
Expected: `{"status":"ok"}`

- [ ] **Step 2: Create Job 1 — `stage-fail-test` (command fails in Build stage)**

Open Jenkins UI → New Item → Pipeline → name: `stage-fail-test`. In Pipeline script, enter:

```groovy
pipeline {
    agent any
    stages {
        stage('Checkout') {
            steps {
                echo 'Checking out code...'
                sh 'echo "checkout done"'
            }
        }
        stage('Build') {
            steps {
                echo 'Building...'
                sh 'nonexistent-command --version'
            }
        }
        stage('Test') {
            steps {
                echo 'Testing...'
                sh 'echo "tests done"'
            }
        }
    }
}
```

Save. Run the job once — it will fail in the `Build` stage. Verify the failure appears in the Pipeline Feed UI.

- [ ] **Step 3: Wire the job to the webhook**

In the app UI → Jobs panel → find `stage-fail-test` → click "Wire Up". This adds the Jenkins notification plugin to the job so failures are sent to our webhook.

Or via API:
```bash
curl -s -X POST http://localhost:8000/api/inject-webhook \
  -H 'Content-Type: application/json' \
  -d '{"job_name": "stage-fail-test"}'
```
Expected: `{"ok":true,...}`

- [ ] **Step 4: Create Credential `MY_DOCKER_TOKEN` in Jenkins (intentionally wrong value)**

Jenkins UI → Manage Jenkins → Credentials → System → Global → Add Credentials:
- Kind: Secret text
- Secret: `wrong-value-intentional`
- ID: `MY_DOCKER_TOKEN`
- Description: Test credential

- [ ] **Step 5: Create Job 2 — `cred-fail-test` (uses credential + fails)**

New Item → Pipeline → name: `cred-fail-test`. Pipeline script:

```groovy
pipeline {
    agent any
    stages {
        stage('Login') {
            steps {
                withCredentials([string(credentialsId: 'MY_DOCKER_TOKEN', variable: 'TOKEN')]) {
                    sh 'echo "Token starts with: ${TOKEN:0:3}"'
                    sh 'docker login -u myuser -p $TOKEN registry.example.com || echo "Login failed as expected"'
                }
            }
        }
        stage('Push') {
            steps {
                sh 'docker push registry.example.com/myapp:latest'
            }
        }
    }
}
```

Save. Run the job — it will fail (docker push fails, or docker not available). Verify failure appears in feed.

Wire it up:
```bash
curl -s -X POST http://localhost:8000/api/inject-webhook \
  -H 'Content-Type: application/json' \
  -d '{"job_name": "cred-fail-test"}'
```

- [ ] **Step 6: Trigger both jobs and verify drawer behaviour**

Run `stage-fail-test` again (with webhook wired). In the UI:
1. Feed shows the failure card for `stage-fail-test`
2. Click the job name → drawer slides open
3. **Logs tab:** log loads, `Build` stage lines are highlighted in red, "Jump to failed stage" button works, Copy works
4. **Tool Crawler tab:** shows "No tools declared in Jenkinsfile" (no tools{} block) and "All credentials found" (no credentials used)

Run `cred-fail-test`. In the UI:
1. Feed shows failure card for `cred-fail-test`
2. Click job name → drawer opens
3. **Logs tab:** log loads, `Push` stage (or `Login`) highlighted
4. **Tool Crawler tab:** `MY_DOCKER_TOKEN` shows under Credentials section — should show as **found** (it exists in Jenkins). If the credential ID is misspelled in Jenkinsfile it will show as **missing**. Verify the credential row appears and status is correct.

- [ ] **Step 7: Test missing credential scenario**

Create Job 3 — `missing-cred-test` — with a credential ID that does NOT exist in Jenkins:

```groovy
pipeline {
    agent any
    stages {
        stage('Deploy') {
            steps {
                withCredentials([string(credentialsId: 'NONEXISTENT_SECRET', variable: 'SEC')]) {
                    sh 'echo deploying'
                }
            }
        }
    }
}
```

Wire it and run. In the UI:
1. Open drawer → Tool Crawler tab
2. Credentials section shows `NONEXISTENT_SECRET` → red row → "not found in Jenkins"
3. This is the credential issue visible in the tool crawler ✓

- [ ] **Step 8: Commit final state and rebuild**

```bash
cd /Users/oggy/PlatformTool/frontend && npm run build 2>&1 | tail -5
git add -A
git commit -m "feat: build detail drawer complete — logs, tool crawler, e2e verified"
```

---

## Self-Review

### Spec coverage check

| Spec requirement | Task |
|---|---|
| Slide-out right drawer, feed stays visible | Task 4 (drawer component), Task 5 (wired) |
| Click build card opens drawer | Task 5 (BuildCard job name click) |
| Logs tab — live fetch from Jenkins | Task 2 (API endpoint), Task 4 (LogsTab) |
| Failed stage highlighted in log | Task 4 (line range detection + red highlight) |
| Jump to failed stage button | Task 4 (LogsTab toolbar) |
| Copy log button | Task 4 (LogsTab toolbar) |
| Loading + error states in Logs tab | Task 4 |
| Verification in analysis_complete event | Task 1 |
| Tool Crawler tab — 3 sections | Task 4 (CrawlerTab) |
| Mismatch rows with similarity bar | Task 4 (MismatchRow) |
| Missing plugins/credentials red rows | Task 4 (ToolRow status=missing) |
| Errors → amber warning banner | Task 4 (CrawlerTab) |
| Nothing-to-verify empty state | Task 4 (allClean check) |
| No verification data empty state | Task 4 (no verification prop) |
| Tests for /api/build-log | Task 2 |
| Tests for verification in SSE event | Task 1 |
| E2E test with real Jenkins jobs | Task 6 |

All spec requirements covered. No placeholders. Types consistent (`VerificationData`, `VerificationToolMismatch` defined in Task 3, used in Task 4). `onOpenDetail` prop defined in Task 5 step 2, consumed in Tasks 5 steps 1+3.
