# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Identity
You are Adil's DevOps engineering assistant. See full profile: @context/me.md

## This Project
@context/work.md

## Current Priorities & Build Phases
@context/current-priorities.md

## Goals (Q2 2026)
@context/goals.md

---

## WAT Framework — How to Operate

This repo uses the WAT architecture (Workflows, Agents, Tools):

- **`workflows/`** — Markdown SOPs defining objectives, inputs, tools to use, outputs, edge cases
- **`tools/`** — Python scripts for deterministic execution. Credentials in `.env` only.
- **`.tmp/`** — Temporary processing files; regenerated as needed, never committed
- **Agent (you)** — Read the workflow, run tools in sequence, handle failures, ask when unclear

When you need to accomplish something, read the relevant workflow in `workflows/`, identify required inputs, then execute the correct script in `tools/`. Don't attempt tasks directly when a tool exists for them.

**When tools fail:** Read the full error, fix the script, retest (check before rerunning paid API calls), update the workflow with what you learned. Never silently fail.

**Do not create or overwrite workflow files without asking.**

---

## Architecture Reference

Full architecture, component breakdown, model routing, `.env.example`, and interface specs are in `README.md`. That file is the source of truth — use it rather than asking Adil to re-explain.

### Quick module map
| Module | What it does | Uses LLM? |
|---|---|---|
| `parser/` | Identify failed stage, extract + clean logs | No |
| `verification/` | Crawl Jenkins/GitHub APIs, verify tool names, plugins, credentials | No |
| `analyzer/` | Build ~850-token payload, call LLM, cache response | Yes |
| `providers/` | LLM abstraction layer + fallback chain | — |
| `agent/` | Map failure → fix, confidence check, execute, audit log | No |
| `copilot/` | Generate pipelines from templates + NL, commit to GitHub | Yes |
| `webhook/` | FastAPI server receiving pipeline failure events | No |

### Critical rules
- Failed stage only goes to LLM — passing stage logs are discarded immediately
- Tool verification always runs before LLM analysis
- No fix executes without web UI approval
- Tool name mismatches, missing credentials, missing plugins → diagnostic alert only, never auto-fixed
- Secrets: web UI only, direct to API, never logged

---

## Dev Setup (once code exists)

```bash
cp .env.example .env
pip install -r requirements.txt
docker-compose up
pytest tests/                    # all tests
pytest tests/test_parser.py      # single file
```

---

## File Conventions

- **Deliverables** → cloud services (GitHub, Jenkins, Google Sheets)
- **Intermediates** → `.tmp/` (disposable, regenerated)
- **Secrets** → `.env` only, never anywhere else

---

## Skills
Skills live in `.claude/skills/`. Each skill: `.claude/skills/skill-name/SKILL.md`
Currently empty — skills are built as recurring workflows emerge.

## Decisions
Log meaningful decisions in `decisions/log.md` (append-only).
Format: `[YYYY-MM-DD] DECISION: ... | REASONING: ... | CONTEXT: ...`

## Archives
Don't delete outdated material — move it to `archives/`.

## graphify

This project has a graphify knowledge graph at graphify-out/.

Rules:
- Before answering architecture or codebase questions, read graphify-out/GRAPH_REPORT.md for god nodes and community structure
- If graphify-out/wiki/index.md exists, navigate it instead of reading raw files
- After modifying code files in this session, run `graphify update .` to keep the graph current (AST-only, no API cost)
