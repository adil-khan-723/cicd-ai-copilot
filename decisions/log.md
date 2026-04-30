# Decision Log

Append-only. When a meaningful decision is made, log it here.

Format: [YYYY-MM-DD] DECISION: ... | REASONING: ... | CONTEXT: ...

---

[2026-04-30] DECISION: Defer copilot→credential handshake to post-publication | REASONING: Copilot commits Jenkinsfiles with credentialsId placeholders that don't exist in Jenkins yet — first run always fails with "No such credential." The credential modal (Phase 5) is the right fix primitive but wiring it into the copilot commit flow adds scope mid-Phase 5. Groovy interpolation warnings also deferred for same reason. | CONTEXT: After credential modal smoke test. Known gap: after commit, scan generated Jenkinsfile for credentialsId refs, surface missing ones in a post-commit banner that opens the credential modal per ID.

[2026-04-30] DECISION: Skip Groovy string interpolation detection as a fix type for now | REASONING: Interpolation warnings are not build failures — our trigger model is failure-only. Detection + single-quote substitution logic is non-trivial scope. | CONTEXT: miss_creds smoke test returned interpolation warning on a successful build, not a failure.
