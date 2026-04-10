"""
Handles agent chat messages from the web UI.

Supports full conversation history so the agent can hold context across
turns. Routes to the generation LLM provider (qwen2.5-coder / claude-sonnet
/ ollama) and streams the response back.
"""
import logging
from typing import Generator
from providers import get_provider

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are a DevOps AI assistant and CI/CD copilot built into a pipeline monitoring dashboard.

You help with:
- Answering DevOps, Jenkins, GitHub Actions, Docker, Kubernetes, and cloud questions
- Generating Jenkinsfiles and GitHub Actions workflows from natural language descriptions
- Explaining CI/CD pipeline failures and suggesting root cause fixes
- Reviewing and improving existing pipeline configurations
- General software engineering, infrastructure, and tooling questions

Formatting rules:
- When generating a Jenkinsfile always wrap it in a ```groovy code block
- When generating a GitHub Actions workflow always wrap it in a ```yaml code block
- For all other responses be concise, practical and direct — no filler text
- Use bullet points for lists, not walls of text

You have context: the user runs Jenkins and/or GitHub Actions pipelines and uses
this dashboard to monitor failures and generate new pipeline configs."""


def handle_chat(
    message: str,
    history: list[dict] | None = None,
) -> Generator[str, None, None]:
    """
    Takes a user message + optional conversation history, calls the LLM,
    yields the full response as a single chunk.

    history: list of {"role": "user"|"assistant", "content": str}
    """
    if not message or not message.strip():
        yield "Please enter a message."
        return

    try:
        provider = get_provider("generation")

        # Build full prompt including recent history (last 8 turns to stay within token budget)
        if history:
            turns = "\n".join(
                f"{'User' if h['role'] == 'user' else 'Assistant'}: {h['content']}"
                for h in history[-8:]
            )
            full_prompt = f"{turns}\nUser: {message.strip()}\nAssistant:"
        else:
            full_prompt = message.strip()

        response = provider.complete(full_prompt, system=_SYSTEM_PROMPT)
        yield response

    except Exception as e:
        logger.error("Chat handler error: %s", e)
        err = str(e)
        hint = ""
        if "unavailable" in err.lower() or "cannot reach" in err.lower() or "connect" in err.lower():
            hint = "\n\nTip: Make sure Ollama is running (`ollama serve`) or set ANTHROPIC_API_KEY in .env."
        yield f"Error: {err}{hint}"
