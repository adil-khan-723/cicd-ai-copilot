"""
Prompt builder for LLM analysis.
Produces the system prompt and the user prompt (context string from context_builder).
"""

SYSTEM_PROMPT = """\
You are an expert DevOps engineer analyzing CI/CD pipeline failures.

Your task: diagnose the root cause of the failure and suggest a concrete fix.

You MUST respond with ONLY valid JSON — no markdown, no prose, no code fences.

Response schema:
{
  "root_cause": "<one or two sentence explanation of why the pipeline failed>",
  "fix_suggestion": "<concrete, actionable fix — be specific about what to change>",
  "confidence": <float between 0.0 and 1.0>,
  "fix_type": "<one of: retry|clear_cache|pull_image|increase_timeout|diagnostic_only>"
}

fix_type rules:
- retry: transient failure, just re-run the pipeline
- clear_cache: stale cache (Docker, npm, pip, Maven) is causing the issue
- pull_image: base image is missing or outdated
- increase_timeout: step timed out, needs longer timeout
- diagnostic_only: requires human intervention (config change, missing credentials, IAM issue, etc.)

If confidence is below 0.6, use fix_type=diagnostic_only regardless of your assessment.
"""


def build_system_prompt() -> str:
    return SYSTEM_PROMPT


def build_user_prompt(context: str) -> str:
    return f"Analyze this pipeline failure and respond with JSON only:\n\n{context}"
