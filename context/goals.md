# Goals

Update this file at the start of each quarter.

## Q2 2026

### Primary Goal
Complete and publish the DevOps AI Agent as a portfolio project and real-world tool.

### End State (Definition of Done)
- Full reactive pipeline: webhook → parse → verify → LLM → Slack approval → fix execution → report
- Full copilot pipeline: Slack command → LLM generation → preview → approve → commit/apply
- All 6 build phases complete
- Project live on GitHub with comprehensive README
- Dev.to article and LinkedIn post published
- System running fully locally on M4 MacBook (Ollama) OR via cloud API (Anthropic) via `.env` switch

### Milestones
1. Pipeline fails → clean analysis in Slack (Phase 1)
2. Tool mismatches detected deterministically before LLM (Phase 2)
3. Approve/reject flow working end to end (Phase 3)
4. Natural language → Jenkinsfile/YAML in Slack (Phase 4)
5. Full stack running locally (Phase 5)
6. Published on GitHub + Dev.to + LinkedIn (Phase 6)

### Why This Matters
- Portfolio piece demonstrating production AI system design (not a tutorial toy)
- Real problem solved: CI/CD failures cost engineering teams hours weekly
- Interview differentiation: deterministic-first + human-in-the-loop + 90% token optimization
- Demonstrates provider-agnostic architecture and responsible AI deployment patterns

### Secondary Goals
- Get strong at Slack Bolt SDK
- Deep understanding of Jenkins REST API and GitHub API
- Practical experience with local LLM deployment (Ollama)
- Publish first Dev.to technical article
