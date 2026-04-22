"""
Handles agent chat messages from the web UI.

Supports full conversation history. Routes to the generation LLM provider
(claude-sonnet or qwen2.5-coder) and streams the response back.
"""
import logging
from typing import Generator
from providers import get_provider

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are a DevOps AI assistant and CI/CD copilot built into a pipeline monitoring dashboard.

You help with:
- Answering DevOps, Jenkins, GitHub Actions, Docker, and cloud questions
- Generating Jenkinsfiles and GitHub Actions workflows from natural language
- Explaining CI/CD pipeline failures and suggesting root cause fixes
- Reviewing and improving existing pipeline configurations

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

        yield from provider.stream_complete(full_prompt, system=_SYSTEM_PROMPT)

    except Exception as e:
        logger.error("Chat handler error: %s", e)
        err = str(e)
        hint = ""
        if any(kw in err.lower() for kw in ("unavailable", "cannot reach", "connect")):
            hint = "\n\nTip: Make sure Ollama is running (`ollama serve`) or set ANTHROPIC_API_KEY in .env."
        yield f"Error: {err}{hint}"
