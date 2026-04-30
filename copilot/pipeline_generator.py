"""
Jenkins pipeline generator (Increment 23).

NL description → Jenkinsfile via LLM + base template.
Uses the generation provider (qwen2.5-coder or claude-sonnet).
"""
import logging
import re

from providers import get_provider
from copilot.template_selector import select_jenkins_template

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are an expert Jenkins pipeline engineer.
Your task: generate a complete, production-ready Declarative Jenkinsfile.

Rules:
- Output ONLY the Jenkinsfile content — no markdown fences, no explanation, no prose.
- Start with: pipeline {
- Use the provided base template as your starting point — customize it for the request.
- Keep stage names clear and descriptive.
- Use withCredentials() for any secrets — never hardcode values.
- Add post { failure { } } blocks for important stages.
- The output must be valid Groovy that Jenkins would accept.
- For any value the user must supply (server IPs, image names, registry URLs, usernames, paths),
  use SCREAMING_SNAKE_CASE placeholders prefixed with YOUR_. Examples:
  YOUR_DOCKERHUB_USERNAME, YOUR_SERVER_IP, YOUR_APP_NAME, YOUR_ECR_REPO.
  Never use lowercase kebab placeholders like your-server-ip.
- Never use 'checkout scm' — it only works in Multibranch Pipelines. Always use:
  git(url: 'YOUR_REPO_URL', branch: 'YOUR_BRANCH', credentialsId: 'YOUR_GIT_CREDENTIALS_ID')
- Never generate YOUR_ORG_NAME, YOUR_GITHUB_ORG, or YOUR_GITHUB_USERNAME as separate placeholders.
  The full repository URL (YOUR_REPO_URL) already contains the org/username. One placeholder for the full URL.
"""


def generate_jenkinsfile(nl_request: str) -> tuple[str, str]:
    """
    Generate a Jenkinsfile from a natural language description.

    Args:
        nl_request: Plain English description of what the pipeline should do.

    Returns:
        (template_name, generated_jenkinsfile_content)
    """
    template_name, template_content = select_jenkins_template(nl_request)
    logger.info("Selected template: %s for request: %.80s", template_name, nl_request)

    provider = get_provider("generation")

    user_prompt = (
        f"Base template ({template_name}):\n"
        f"```groovy\n{template_content}\n```\n\n"
        f"Request: {nl_request}\n\n"
        f"Generate a complete Jenkinsfile for this request. Output only the Jenkinsfile."
    )

    raw = provider.complete(user_prompt, system=_SYSTEM_PROMPT)
    jenkinsfile = _extract_groovy(raw)

    # Basic syntax check — retry once with correction prompt if invalid
    if not _is_valid_groovy(jenkinsfile):
        logger.warning("Generated Jenkinsfile failed basic validation — retrying with correction prompt")
        correction_prompt = (
            f"The following Jenkinsfile has syntax issues:\n```groovy\n{jenkinsfile}\n```\n\n"
            f"Fix it so it is valid Declarative Pipeline Groovy. Output only the corrected Jenkinsfile."
        )
        raw = provider.complete(correction_prompt, system=_SYSTEM_PROMPT)
        jenkinsfile = _extract_groovy(raw)

    return template_name, jenkinsfile


def _extract_groovy(raw: str) -> str:
    """Strip markdown fences if the LLM wrapped the output."""
    # Try ```groovy ... ``` or ``` ... ```
    match = re.search(r"```(?:groovy)?\s*\n?(pipeline\s*\{.*?)\n?```", raw, re.DOTALL)
    if match:
        return match.group(1).strip()
    # If it starts with pipeline { directly, use as-is
    stripped = raw.strip()
    if stripped.startswith("pipeline"):
        return stripped
    # Best-effort: find pipeline { ... } block
    match = re.search(r"(pipeline\s*\{.*)", raw, re.DOTALL)
    if match:
        return match.group(1).strip()
    return stripped


def _is_valid_groovy(content: str) -> bool:
    """
    Basic structural validation for Declarative Pipelines.
    Checks brace balance and required keywords — not a full Groovy parser.
    """
    if not content.strip().startswith("pipeline"):
        return False
    if content.count("{") != content.count("}"):
        return False
    if "stages" not in content:
        return False
    if "stage(" not in content and "stage (" not in content:
        return False
    return True
