"""
Handles agent chat messages from the web UI.

Supports full conversation history. Routes to the generation LLM provider
(claude-sonnet or qwen2.5-coder) and streams the response back.
"""
import logging
import re
from typing import Generator
from providers import get_provider

_CHECKOUT_SCM_RE = re.compile(r'\bcheckout\s+scm\b')
_CHECKOUT_SCM_REPLACEMENT = "git(url: 'YOUR_REPO_URL', branch: 'YOUR_BRANCH', credentialsId: 'YOUR_GIT_CREDENTIALS_ID')"

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are a DevOps AI assistant and CI/CD copilot built into a pipeline monitoring dashboard.

You help with:
- Answering DevOps, Jenkins, GitHub Actions, Docker, and cloud questions
- Generating Jenkinsfiles and GitHub Actions workflows from natural language
- Explaining CI/CD pipeline failures and suggesting root cause fixes
- Reviewing and improving existing pipeline configurations

CRITICAL for Jenkinsfile generation:
- NEVER write `checkout scm` — it only works in Multibranch Pipelines and will fail in standard pipelines.
  Always use: git(url: 'YOUR_REPO_URL', branch: 'YOUR_BRANCH', credentialsId: 'YOUR_GIT_CREDENTIALS_ID')
- Use SCREAMING_SNAKE_CASE placeholders prefixed with YOUR_ for any value the user must supply.
  Example: YOUR_REPO_URL, YOUR_DOCKERHUB_USERNAME, YOUR_SERVER_IP. Never lowercase-kebab.

Formatting rules:
- When generating a Jenkinsfile always wrap it in a ```groovy code block
- When generating a GitHub Actions workflow always wrap it in a ```yaml code block
- Be concise, practical and direct — no filler text
- Use bullet points for lists, not walls of text"""


def handle_chat(
    message: str,
    history: list[dict] | None = None,
) -> Generator[str, None, None]:
    """
    Takes a user message + optional conversation history, calls the LLM,
    yields response chunks for streaming.

    history: list of {"role": "user"|"assistant", "content": str}
    """
    if not message or not message.strip():
        yield "Please enter a message."
        return

    try:
        provider = get_provider("generation")

        turns: list[str] = []
        if history:
            for h in history[-8:]:
                role = "User" if h["role"] == "user" else "Assistant"
                turns.append(f"{role}: {h['content']}")

        turns.append(f"User: {message.strip()}")
        turns.append("Assistant:")

        full_prompt = "\n".join(turns)

        # Stream with line-buffered checkout scm scrub
        line_buf = ""
        for chunk in provider.stream_complete(full_prompt, system=_SYSTEM_PROMPT):
            line_buf += chunk
            while "\n" in line_buf:
                line, line_buf = line_buf.split("\n", 1)
                yield _CHECKOUT_SCM_RE.sub(_CHECKOUT_SCM_REPLACEMENT, line) + "\n"
        if line_buf:
            yield _CHECKOUT_SCM_RE.sub(_CHECKOUT_SCM_REPLACEMENT, line_buf)

    except Exception as e:
        logger.error("Chat handler error: %s", e)
        err = str(e)
        hint = ""
        if any(kw in err.lower() for kw in ("unavailable", "cannot reach", "connect")):
            hint = "\n\nTip: Make sure Ollama is running (`ollama serve`) or set ANTHROPIC_API_KEY in .env."
        yield f"Error: {err}{hint}"
