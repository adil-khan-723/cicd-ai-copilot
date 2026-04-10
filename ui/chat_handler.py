"""
Handles agent chat messages from the web UI.

Routes to the generation LLM provider (qwen2.5-coder / claude-sonnet).
Returns a generator of text chunks for streaming via StreamingResponse.
"""
import logging
from typing import Generator
from providers import get_provider

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are a DevOps AI assistant specializing in CI/CD pipelines.
You can generate Jenkinsfiles and GitHub Actions workflows, explain pipeline failures,
and answer DevOps questions. When generating pipeline files, output valid Groovy (Jenkins)
or valid YAML (GitHub Actions) only — no markdown fences unless asked.
Be concise and practical."""


def handle_chat(message: str) -> Generator[str, None, None]:
    """
    Takes a user message, calls the generation LLM, yields response chunks.
    Each chunk is a plain text string (not SSE-formatted).
    """
    if not message or not message.strip():
        yield "Please enter a message."
        return

    try:
        provider = get_provider("generation")
        response = provider.complete(message.strip(), system=_SYSTEM_PROMPT)
        yield response
    except Exception as e:
        logger.error("Chat handler error: %s", e)
        yield f"Error: {e}"
