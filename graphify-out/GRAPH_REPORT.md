# Graph Report - /Users/oggy/PlatformTool  (2026-04-20)

## Corpus Check
- 86 files · ~212,139 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1496 nodes · 3474 edges · 53 communities detected
- Extraction: 83% EXTRACTED · 17% INFERRED · 0% AMBIGUOUS · INFERRED: 588 edges (avg confidence: 0.71)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 14|Community 14]]
- [[_COMMUNITY_Community 15|Community 15]]
- [[_COMMUNITY_Community 16|Community 16]]
- [[_COMMUNITY_Community 17|Community 17]]
- [[_COMMUNITY_Community 18|Community 18]]
- [[_COMMUNITY_Community 19|Community 19]]
- [[_COMMUNITY_Community 20|Community 20]]
- [[_COMMUNITY_Community 21|Community 21]]
- [[_COMMUNITY_Community 22|Community 22]]
- [[_COMMUNITY_Community 23|Community 23]]
- [[_COMMUNITY_Community 24|Community 24]]
- [[_COMMUNITY_Community 25|Community 25]]
- [[_COMMUNITY_Community 26|Community 26]]
- [[_COMMUNITY_Community 27|Community 27]]
- [[_COMMUNITY_Community 28|Community 28]]
- [[_COMMUNITY_Community 29|Community 29]]
- [[_COMMUNITY_Community 30|Community 30]]
- [[_COMMUNITY_Community 31|Community 31]]
- [[_COMMUNITY_Community 32|Community 32]]
- [[_COMMUNITY_Community 33|Community 33]]
- [[_COMMUNITY_Community 34|Community 34]]
- [[_COMMUNITY_Community 35|Community 35]]
- [[_COMMUNITY_Community 36|Community 36]]
- [[_COMMUNITY_Community 37|Community 37]]
- [[_COMMUNITY_Community 38|Community 38]]
- [[_COMMUNITY_Community 39|Community 39]]
- [[_COMMUNITY_Community 40|Community 40]]
- [[_COMMUNITY_Community 41|Community 41]]
- [[_COMMUNITY_Community 42|Community 42]]
- [[_COMMUNITY_Community 43|Community 43]]
- [[_COMMUNITY_Community 44|Community 44]]
- [[_COMMUNITY_Community 45|Community 45]]
- [[_COMMUNITY_Community 46|Community 46]]
- [[_COMMUNITY_Community 47|Community 47]]
- [[_COMMUNITY_Community 48|Community 48]]
- [[_COMMUNITY_Community 49|Community 49]]
- [[_COMMUNITY_Community 50|Community 50]]
- [[_COMMUNITY_Community 51|Community 51]]
- [[_COMMUNITY_Community 52|Community 52]]

## God Nodes (most connected - your core abstractions)
1. `get()` - 69 edges
2. `VerificationReport` - 66 edges
3. `E()` - 59 edges
4. `Mv()` - 44 edges
5. `Vs()` - 30 edges
6. `get_settings()` - 29 edges
7. `Po()` - 25 edges
8. `yh()` - 25 edges
9. `Re()` - 25 edges
10. `OllamaProvider` - 25 edges

## Surprising Connections (you probably didn't know these)
- `settings()` --calls--> `get_settings()`  [INFERRED]
  ui/routes.py → config/settings.py
- `commit()` --calls--> `get_settings()`  [INFERRED]
  ui/routes.py → config/settings.py
- `list_templates()` --calls--> `_post_template_list()`  [INFERRED]
  copilot/template_selector.py → slack/copilot_handler.py
- `ProviderUnavailableError` --uses--> `LLM Analyzer client (Increment 15).  Orchestrates: cache check → build prompt →`  [INFERRED]
  providers/factory.py → analyzer/llm_client.py
- `ProviderUnavailableError` --uses--> `Analyze a pipeline failure context string using the configured LLM provider.`  [INFERRED]
  providers/factory.py → analyzer/llm_client.py

## Hyperedges (group relationships)
- **Reactive Pipeline Core Flow — Parse, Verify, Analyze, Notify** — readme_jenkins_crawler, readme_context_builder, readme_selective_context_feeding, readme_deterministic_verification, readme_human_in_the_loop [EXTRACTED 0.95]
- **LLM Provider Ecosystem — Abstraction + Routing + Fallback** — readme_provider_abstraction, readme_model_routing, readme_fallback_chain, readme_model_llama31_8b, readme_model_claude_haiku [EXTRACTED 0.93]
- **Web UI SSE Integration — EventBus + Routes + Dashboard HTML** — web_ui_event_bus, web_ui_routes, ui_static_index_html [EXTRACTED 0.90]

## Communities

### Community 0 - "Community 0"
Cohesion: 0.01
Nodes (254): $(), $0(), a0(), ad(), am(), ao(), aS(), At() (+246 more)

### Community 1 - "Community 1"
Cohesion: 0.02
Nodes (130): _extract_action_refs(), _extract_runner_labels(), _extract_secrets(), _fetch_github_secrets(), GitHub Actions Verification Crawler (Increment 13)  Parses a workflow YAML file, Extract all secrets.X references from raw YAML text., Walk jobs and collect all runs-on values (string or list)., Extract all `uses:` action references from raw YAML text. (+122 more)

### Community 2 - "Community 2"
Cohesion: 0.03
Nodes (174): _a(), aa(), ac(), ah(), Ai(), Al(), an(), ap() (+166 more)

### Community 3 - "Community 3"
Cohesion: 0.05
Nodes (37): ABC, AnthropicProvider, Anthropic provider (Claude) — Phase 5.  Analysis tasks  → claude-haiku-4-5-20251, BaseLLMProvider, complete(), is_available(), Stream the response token-by-token (or chunk-by-chunk).         Default implemen, Abstract base for all LLM providers. Implement this to add a new provider. (+29 more)

### Community 4 - "Community 4"
Cohesion: 0.04
Nodes (36): ax(), Bx(), Ce(), cx(), Ec(), Ef(), hg(), ho() (+28 more)

### Community 5 - "Community 5"
Cohesion: 0.04
Nodes (37): _extract_yaml(), generate_workflow(), _is_valid_yaml(), GitHub Actions workflow generator (Increment 24).  NL description → workflow YAM, Generate a GitHub Actions workflow from a natural language description.      Arg, Strip markdown fences if the LLM wrapped the output., Validate that the content parses as YAML and has required workflow keys., _extract_groovy() (+29 more)

### Community 6 - "Community 6"
Cohesion: 0.05
Nodes (69): Local-First LLM Strategy (Ollama → Cloud via .env swap), Build Phase 1 — Foundation (Webhook + Parser + Notifier), Build Phase 2 — Tool Verification Crawler, Build Phase 3 — Approval Flow & Fix Execution, Build Phase 4 — Copilot Mode, Build Phase 5 — Secrets, Cloud LLMs & Production Polish, Build Phase 6 — Documentation & Publication, CLAUDE.md — Project AI Guidance & WAT Framework (+61 more)

### Community 7 - "Community 7"
Cohesion: 0.05
Nodes (17): Async generator — first replays history, then streams live events.         Safe, aw(), Fm, fu(), gw, hw, i0(), kd() (+9 more)

### Community 8 - "Community 8"
Cohesion: 0.06
Nodes (13): au(), bm, bu, E1(), jc(), md, oo(), r1() (+5 more)

### Community 9 - "Community 9"
Cohesion: 0.06
Nodes (24): log_fix(), Audit log (Increment 19).  Append-only JSONL file recording every fix execution, Append one fix execution record to the audit log.      Args:         fix_type: T, Return the last n entries from the audit log (most recent last).     Returns emp, read_recent(), clean_log(), Strip noise from extracted stage logs before sending to the LLM.     Removes: AN, extract_failed_logs() (+16 more)

### Community 10 - "Community 10"
Cohesion: 0.07
Nodes (21): cache_key(), clear(), MD5-keyed in-memory response cache for LLM analysis results. Key = MD5 hash of t, Clear all cache entries (useful for testing)., set(), analyze(), LLM Analyzer client (Increment 15).  Orchestrates: cache check → build prompt →, Analyze a pipeline failure context string using the configured LLM provider. (+13 more)

### Community 11 - "Community 11"
Cohesion: 0.09
Nodes (27): BaseModel, ChatMessage, ChatPayload, commit(), CommitPayload, FixPayload, _inject_webhook_blocks(), InjectWebhookPayload (+19 more)

### Community 12 - "Community 12"
Cohesion: 0.08
Nodes (24): App(), _extract_confidence(), _extract_job_context(), Slack Bolt approval handler (Increment 17).  Handles button clicks from failure, Strip all actions blocks and append replacement blocks., Extract job_name and build_number from the Slack message text or header block., Extract confidence from analysis section text, e.g. '(88% confidence)'., Register all action handlers on the given Slack Bolt app. (+16 more)

### Community 13 - "Community 13"
Cohesion: 0.12
Nodes (24): execute_fix(), Fix executor (Increment 18).  Maps fix_type strings to concrete fix functions. N, Execute the approved fix.      Args:         fix_type: One of retry|clear_cache|, FixResult, clear_docker_cache(), clear_npm_cache(), _get_jenkins_server(), increase_timeout() (+16 more)

### Community 14 - "Community 14"
Cohesion: 0.15
Nodes (5): Fh(), g0(), m0(), Q0(), y0()

### Community 15 - "Community 15"
Cohesion: 0.21
Nodes (7): pipeline_cancelled_blocks(), pipeline_committed_blocks(), pipeline_preview_blocks(), Slack Block Kit templates for Copilot mode (pipeline preview + approval flow)., Build a Block Kit message showing a generated pipeline preview with action butto, Message shown after successful commit., TestCopilotMessageTemplates

### Community 16 - "Community 16"
Cohesion: 0.25
Nodes (6): create_job(), Jenkins Configurator (Increment 28).  Creates or updates a Jenkins job with a ge, Create or update a Jenkins Pipeline job with the given Jenkinsfile content., Escape special XML characters., _xml_escape(), TestJenkinsConfigurator

### Community 17 - "Community 17"
Cohesion: 0.31
Nodes (9): App Level Token, apps.connections.open API Endpoint, DevOps AI Agent Slack App, Event Subscriptions Feature, Interactivity and Shortcuts Feature, Slack API Developer Portal, Slack Socket Mode Settings Page, Slash Commands Feature (+1 more)

### Community 18 - "Community 18"
Cohesion: 0.29
Nodes (0): 

### Community 19 - "Community 19"
Cohesion: 0.67
Nodes (2): detectPipeline(), sendMessage()

### Community 20 - "Community 20"
Cohesion: 0.5
Nodes (0): 

### Community 21 - "Community 21"
Cohesion: 0.67
Nodes (0): 

### Community 22 - "Community 22"
Cohesion: 0.67
Nodes (0): 

### Community 23 - "Community 23"
Cohesion: 0.67
Nodes (0): 

### Community 24 - "Community 24"
Cohesion: 1.0
Nodes (0): 

### Community 25 - "Community 25"
Cohesion: 1.0
Nodes (0): 

### Community 26 - "Community 26"
Cohesion: 1.0
Nodes (0): 

### Community 27 - "Community 27"
Cohesion: 1.0
Nodes (0): 

### Community 28 - "Community 28"
Cohesion: 1.0
Nodes (0): 

### Community 29 - "Community 29"
Cohesion: 1.0
Nodes (0): 

### Community 30 - "Community 30"
Cohesion: 1.0
Nodes (0): 

### Community 31 - "Community 31"
Cohesion: 1.0
Nodes (0): 

### Community 32 - "Community 32"
Cohesion: 1.0
Nodes (0): 

### Community 33 - "Community 33"
Cohesion: 1.0
Nodes (0): 

### Community 34 - "Community 34"
Cohesion: 1.0
Nodes (0): 

### Community 35 - "Community 35"
Cohesion: 1.0
Nodes (0): 

### Community 36 - "Community 36"
Cohesion: 1.0
Nodes (0): 

### Community 37 - "Community 37"
Cohesion: 1.0
Nodes (0): 

### Community 38 - "Community 38"
Cohesion: 1.0
Nodes (0): 

### Community 39 - "Community 39"
Cohesion: 1.0
Nodes (0): 

### Community 40 - "Community 40"
Cohesion: 1.0
Nodes (0): 

### Community 41 - "Community 41"
Cohesion: 1.0
Nodes (0): 

### Community 42 - "Community 42"
Cohesion: 1.0
Nodes (1): Send a prompt and return the text response.

### Community 43 - "Community 43"
Cohesion: 1.0
Nodes (1): Return True if the provider is reachable and configured.

### Community 44 - "Community 44"
Cohesion: 1.0
Nodes (1): Human-readable provider name for logging.

### Community 45 - "Community 45"
Cohesion: 1.0
Nodes (0): 

### Community 46 - "Community 46"
Cohesion: 1.0
Nodes (0): 

### Community 47 - "Community 47"
Cohesion: 1.0
Nodes (0): 

### Community 48 - "Community 48"
Cohesion: 1.0
Nodes (0): 

### Community 49 - "Community 49"
Cohesion: 1.0
Nodes (0): 

### Community 50 - "Community 50"
Cohesion: 1.0
Nodes (0): 

### Community 51 - "Community 51"
Cohesion: 1.0
Nodes (1): CLAUDE.local.md — Local Personal Overrides

### Community 52 - "Community 52"
Cohesion: 1.0
Nodes (1): Session Summary Template

## Knowledge Gaps
- **91 isolated node(s):** `Validate Jenkins webhook HMAC signature if secret is configured.`, `Validate GitHub Actions webhook HMAC signature if secret is configured.`, `Handles agent chat messages from the web UI.  Supports full conversation history`, `Takes a user message + optional conversation history, calls the LLM,     yields`, `Fetches Jenkins jobs list via python-jenkins. Returns a list of dicts safe to se` (+86 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 24`** (2 nodes): `PipelineFeed.tsx`, `cn()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 25`** (2 nodes): `SettingsPanel.tsx`, `SettingsPanel()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 26`** (2 nodes): `Badge()`, `badge.tsx`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 27`** (2 nodes): `input.tsx`, `cn()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 28`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 29`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 30`** (1 nodes): `tailwind.config.ts`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 31`** (1 nodes): `vite.config.ts`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 32`** (1 nodes): `postcss.config.js`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 33`** (1 nodes): `main.tsx`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 34`** (1 nodes): `index.ts`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 35`** (1 nodes): `Topbar.tsx`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 36`** (1 nodes): `Sidebar.tsx`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 37`** (1 nodes): `button.tsx`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 38`** (1 nodes): `textarea.tsx`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 39`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 40`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 41`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 42`** (1 nodes): `Send a prompt and return the text response.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 43`** (1 nodes): `Return True if the provider is reachable and configured.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 44`** (1 nodes): `Human-readable provider name for logging.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 45`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 46`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 47`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 48`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 49`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 50`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 51`** (1 nodes): `CLAUDE.local.md — Local Personal Overrides`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 52`** (1 nodes): `Session Summary Template`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `get()` connect `Community 1` to `Community 3`, `Community 5`, `Community 7`, `Community 10`, `Community 11`, `Community 12`, `Community 13`, `Community 15`?**
  _High betweenness centrality (0.301) - this node is a cross-community bridge._
- **Why does `get_settings()` connect `Community 1` to `Community 3`, `Community 5`, `Community 9`, `Community 11`, `Community 12`, `Community 13`, `Community 16`?**
  _High betweenness centrality (0.099) - this node is a cross-community bridge._
- **Why does `md` connect `Community 8` to `Community 0`, `Community 10`, `Community 7`?**
  _High betweenness centrality (0.092) - this node is a cross-community bridge._
- **Are the 67 inferred relationships involving `get()` (e.g. with `jenkins_notification()` and `_process_notification_success_sync()`) actually correct?**
  _`get()` has 67 INFERRED edges - model-reasoned connections that need verification._
- **Are the 64 inferred relationships involving `VerificationReport` (e.g. with `_run_verification()` and `.test_has_issues_property()`) actually correct?**
  _`VerificationReport` has 64 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Validate Jenkins webhook HMAC signature if secret is configured.`, `Validate GitHub Actions webhook HMAC signature if secret is configured.`, `Handles agent chat messages from the web UI.  Supports full conversation history` to the rest of the system?**
  _91 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Community 0` be split into smaller, more focused modules?**
  _Cohesion score 0.01 - nodes in this community are weakly interconnected._