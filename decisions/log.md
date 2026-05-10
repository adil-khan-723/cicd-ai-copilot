# Decision Log

Append-only. When a meaningful decision is made, log it here.

Format: [YYYY-MM-DD] DECISION: ... | REASONING: ... | CONTEXT: ...

---

[2026-04-30] DECISION: Defer copilot→credential handshake to post-publication | REASONING: Copilot commits Jenkinsfiles with credentialsId placeholders that don't exist in Jenkins yet — first run always fails with "No such credential." The credential modal (Phase 5) is the right fix primitive but wiring it into the copilot commit flow adds scope mid-Phase 5. Groovy interpolation warnings also deferred for same reason. | CONTEXT: After credential modal smoke test. Known gap: after commit, scan generated Jenkinsfile for credentialsId refs, surface missing ones in a post-commit banner that opens the credential modal per ID.

[2026-04-30] DECISION: Skip Groovy string interpolation detection as a fix type for now | REASONING: Interpolation warnings are not build failures — our trigger model is failure-only. Detection + single-quote substitution logic is non-trivial scope. | CONTEXT: miss_creds smoke test returned interpolation warning on a successful build, not a failure.

[2026-05-08] DECISION: Make profile add idempotent on (jenkins_url, jenkins_user) | REASONING: Each setup-wizard save was generating a fresh uuid4 → new profile.id → orphaned all browser-side chat history (keyed on profile.id in localStorage). Re-saving with same URL+user must reuse the same id and rotate the token in place. Different user on same URL still creates a new profile (e.g. admin vs ci-bot accounts). | CONTEXT: User reported chat history disappeared after re-saving credentials.

[2026-05-09] DECISION: Hot-reload settings via @property in providers, drop snapshot in __init__ | REASONING: AnthropicProvider snapshotted self._settings = get_settings() in __init__. Even after _settings cache cleared post-Save, the provider held a stale binding → Save+chat round-trip still hit "providers unavailable". Re-reading via @property each access + rebuilding cached SDK client when key changes makes UI key save take effect immediately. | CONTEXT: Live debug — user saved Anthropic key in Settings, chat still failed.

[2026-05-09] DECISION: Validator soft-warns instead of SystemExit when ANTHROPIC_API_KEY missing | REASONING: Hard-exit blocked server boot which blocked UI which blocked configuring the key via Settings UI. Chicken-and-egg. Server now boots with warning; LLM calls fail with clear error if key truly missing at call time. | CONTEXT: User on cloud VM tried to start fresh, hit SystemExit on first boot.

[2026-05-10] DECISION: Add Jenkins failure poller as fallback to Notification Plugin | REASONING: Notification Plugin v1.18 silently fails on cloud Jenkins installs (junit dep missing, wrong event/branch values). 30s background poller scans /api/json for new failures, dedups by (job, build), routes through same handler. Webhook still fast path; poller is reliable backup. | CONTEXT: Live diagnosis on EC2 Jenkins — webhook never fired despite plugin "active".

[2026-05-10] DECISION: Auto-install + auto-configure Jenkins on profile activate | REASONING: Three silent killers in Notification Plugin v1.18: missing junit dep, <event>=phase-name (wrong field), null <branch> on jobs without SCM. All silent — no logs at any level. Manual setup is fragile and undocumented; auto-config eliminates the entire class of "webhook silently dropped" issues. Background fire-and-forget so activate response stays fast. | CONTEXT: Cloud Jenkins debug spent 2 hours pinning these down via tcpdump + bytecode decompile.

[2026-05-10] DECISION: Multi-key API manager keyed by name, provider-tagged | REASONING: User has multiple Anthropic keys (work / personal / project-X). Need cost attribution per analysis. Provider-agnostic schema future-proofs for OpenAI/etc. Delete-active blocked unless user picks replacement first — prevents accidental loss of LLM access. | CONTEXT: User explicitly asked for multi-key UI with name-based switching + per-event tracking.
