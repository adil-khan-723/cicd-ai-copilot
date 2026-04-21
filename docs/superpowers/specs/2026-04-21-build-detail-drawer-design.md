# Build Detail Drawer — Design Spec
**Date:** 2026-04-21  
**Status:** Approved

---

## Overview

When a user clicks a failed build card in the Pipeline Feed, a slide-out drawer opens from the right side. The feed remains visible and usable on the left. The drawer shows two tabs: **Logs** (full console output fetched live from Jenkins) and **Tool Crawler** (verification results already computed during failure analysis).

---

## Decisions

| Question | Decision | Reason |
|---|---|---|
| How does detail open? | Slide-out right drawer | Feed stays in context; standard GitHub/VS Code pattern |
| Log data source | Live fetch from Jenkins on demand | Full log any length; works for old builds; one API call |
| Crawler data source | Attach to existing `analysis_complete` SSE event | Crawler already ran; zero extra work; data already in memory |

---

## Architecture

### Backend — two changes

**1. Extend `analysis_complete` SSE event**  
In `webhook/server.py → _process_failure_sync`, the `VerificationReport` is already computed by `_run_verification`. Serialize it and include it in the `analysis_complete` bus publish:

```python
"verification": {
    "matched_tools":        report.matched_tools,
    "mismatched_tools":     [{"referenced": m.referenced, "configured": m.configured, "match_score": m.match_score} for m in report.mismatched_tools],
    "missing_plugins":      report.missing_plugins,
    "missing_credentials":  report.missing_credentials,
    "errors":               report.errors,
}
```

**2. New route: `GET /api/build-log`**  
Add to `ui/routes.py`. Query params: `job` (str), `build` (int). Fetches console output via `python-jenkins`. Returns `{"log": "..."}`. Requires Jenkins to be configured — returns 503 with `{"detail": "Jenkins not configured"}` if not. Returns 404 if build not found. No auth beyond existing Jenkins credentials in settings.

---

### Frontend — four changes

**1. Extend `AnalysisCompleteEvent` type** (`frontend/src/types/index.ts`)

Add optional `verification` field:
```ts
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
`AnalysisCompleteEvent` gains `verification?: VerificationData`.

**2. New component: `BuildDetailDrawer.tsx`** (`frontend/src/components/BuildDetailDrawer.tsx`)

See Component Design section below.

**3. `BuildCard.tsx`** — clicking the job name or build number badge calls `onOpenDetail(card)`. The existing expand/collapse chevron keeps its current behaviour.

**4. `App.tsx`** — add `selectedCard: BuildCard | null` state. Pass `onOpenDetail` down through `PipelineFeed → BuildCard`. Render `<BuildDetailDrawer>` alongside the feed.

---

## Component Design

### `BuildDetailDrawer`

**Props:**
```ts
interface BuildDetailDrawerProps {
  card: BuildCard | null   // null = closed
  onClose: () => void
}
```

**Layout:**
- Fixed right panel, `w-[45vw] min-w-[480px] max-w-[720px]`
- Full viewport height, overlaps feed with a subtle dimming backdrop (`bg-black/20`)
- Spring slide-in from right: `x: "100%" → 0`
- Header: job name (monospace, truncated) + build number badge + close button (X)
- Tab bar: **Logs** | **Tool Crawler** — same pill style as existing job tabs
- Tab content area: `flex-1 overflow-hidden`

**Backdrop:** semi-transparent, clicking it closes drawer. Does not block feed interaction visually — dim is subtle (20% opacity black).

---

### Logs Tab

- Dark terminal background: `bg-zinc-950` text `text-zinc-100`
- Monospace font, `text-[12px]`, `leading-[1.6]`
- Line numbers in left gutter: `text-zinc-600`, `select-none`, fixed width `w-10 text-right pr-3`
- Scrollable log area — virtualized if >2000 lines (use simple windowing)
- **Failed stage highlight:** scan log lines for `[Pipeline] { (<failed_stage_name>)`. Lines from that point until the next `[Pipeline] }` get a `border-l-2 border-error bg-error/5` treatment
- **"Jump to failed stage"** button in toolbar — scrolls to first highlighted line
- **Copy log** button (clipboard icon) top-right of toolbar — copies full log text
- **Loading state:** spinner centered in dark area with "Fetching log from Jenkins..."
- **Error state:** if fetch fails, show error message with retry button

**Toolbar (above log area):**
```
[Jump to failed stage]  [stage name pill]          [Copy]
```

---

### Tool Crawler Tab

Three collapsible sections. Each starts expanded if it has content, collapsed if empty.

**Section: Tools**
- Header: wrench icon + "Tools" label + count badge (green if 0 issues, red if issues)
- Each matched tool: `✓ tool-name` in green
- Each mismatched tool: amber row showing `"Maven3"  →  "maven3"  (92% match)` with a similarity bar
- If no tools referenced in Jenkinsfile: subtle grey row "No tools declared in Jenkinsfile"

**Section: Plugins**
- Header: puzzle icon + "Plugins"
- Each missing plugin: red row with plugin short name + "not installed" label
- If empty: `✓ All required plugins installed`

**Section: Credentials**
- Header: key icon + "Credentials"  
- Each missing credential: red row with credential ID + "not found in Jenkins" label
- If empty: `✓ All credentials found`

**Warning banner (top of tab):** if `verification.errors` is non-empty, show amber banner:
> "Tool crawler could not fully verify — Jenkins API returned errors. Results may be incomplete."

**All-clear empty state:** if `verification` is absent from the event (older event / no Jenkinsfile), show:
> "No verification data available for this build."

**Nothing-to-verify state:** if all three sections are empty and no errors:
> "No tools or credentials referenced in this Jenkinsfile — nothing to verify."  
> Shown with a checkmark icon, muted styling.

---

## Data Flow

```
Jenkins build fails
  → webhook → _process_failure_sync
    → _run_verification() → VerificationReport
    → analysis_complete event (now includes verification{})
      → EventBus → SSE → React App
        → BuildCard stores card.analysis.verification

User clicks build card job name / build number
  → App sets selectedCard
    → BuildDetailDrawer opens (spring animation)
      → Logs tab (default): fetch GET /api/build-log?job=X&build=N
        → show terminal log, highlight failed stage
      → Tool Crawler tab: read card.analysis.verification
        → render sections inline, no fetch
```

---

## API

### `GET /api/build-log`

**Query params:** `job` (string), `build` (integer)

**Success 200:**
```json
{ "log": "Started by user admin\n[Pipeline] Start of Pipeline\n..." }
```

**Error 503:**
```json
{ "detail": "Jenkins not configured" }
```

**Error 404:**
```json
{ "detail": "Build not found" }
```

**Error 502:**
```json
{ "detail": "Could not fetch log from Jenkins: <reason>" }
```

---

## Error Handling

| Scenario | Behaviour |
|---|---|
| Jenkins unreachable when log fetched | Error state in Logs tab with retry button |
| Build not found (deleted) | "Build log not available" message |
| Verification ran but Jenkins API failed during crawl | Amber warning banner in Tool Crawler tab |
| `verification` field missing from event (old build) | "No verification data available" empty state |
| No tools/creds in Jenkinsfile | "Nothing to verify" clean empty state |

---

## Testing

- `tests/test_ui_routes.py`: add `test_build_log_returns_text`, `test_build_log_jenkins_not_configured`, `test_build_log_not_found`
- `tests/test_webhook_server.py`: verify `analysis_complete` event payload now includes `verification` field with correct structure
- Frontend: manual test — trigger failure webhook, open drawer, verify log loads and failed stage is highlighted, verify Tool Crawler tab shows verification data

---

## Files Changed

| File | Change |
|---|---|
| `webhook/server.py` | Add `verification` to `analysis_complete` publish |
| `ui/routes.py` | Add `GET /api/build-log` endpoint |
| `frontend/src/types/index.ts` | Add `VerificationData`, `VerificationToolMismatch`, extend `AnalysisCompleteEvent` |
| `frontend/src/components/BuildDetailDrawer.tsx` | New component |
| `frontend/src/components/BuildCard.tsx` | Add `onOpenDetail` prop + click handler |
| `frontend/src/components/PipelineFeed.tsx` | Thread `onOpenDetail` prop through |
| `frontend/src/App.tsx` | Add `selectedCard` state, render drawer |
| `tests/test_ui_routes.py` | Add build-log endpoint tests |
