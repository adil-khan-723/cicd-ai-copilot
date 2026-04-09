"""
GitHub Actions workflow generator (Increment 24).

NL description → workflow YAML via LLM + base template.
Validates output with PyYAML — retries once with correction prompt if invalid.
"""
import logging
import re
import yaml

from providers import get_provider
from copilot.template_selector import select_github_template

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are an expert GitHub Actions workflow engineer.
Your task: generate a complete, production-ready GitHub Actions workflow YAML file.

Rules:
- Output ONLY the YAML content — no markdown fences, no explanation, no prose.
- Start with: name: <workflow name>
- Use the provided base template as your starting point — customize it for the request.
- Pin actions to major version tags (e.g. actions/checkout@v4), not @main or @latest.
- Use ${{ secrets.SECRET_NAME }} for all sensitive values.
- The output must be valid YAML that GitHub Actions would accept.
"""


def generate_workflow(nl_request: str) -> tuple[str, str]:
    """
    Generate a GitHub Actions workflow from a natural language description.

    Args:
        nl_request: Plain English description of what the workflow should do.

    Returns:
        (template_name, generated_workflow_yaml_content)
    """
    template_name, template_content = select_github_template(nl_request)
    logger.info("Selected template: %s for request: %.80s", template_name, nl_request)

    provider = get_provider("generation")

    user_prompt = (
        f"Base template ({template_name}):\n"
        f"```yaml\n{template_content}\n```\n\n"
        f"Request: {nl_request}\n\n"
        f"Generate a complete GitHub Actions workflow YAML for this request. Output only the YAML."
    )

    raw = provider.complete(user_prompt, system=_SYSTEM_PROMPT)
    workflow_yaml = _extract_yaml(raw)

    # Validate with PyYAML — retry once if invalid
    if not _is_valid_yaml(workflow_yaml):
        logger.warning("Generated workflow failed YAML validation — retrying with correction prompt")
        correction_prompt = (
            f"The following GitHub Actions workflow has YAML errors:\n```yaml\n{workflow_yaml}\n```\n\n"
            f"Fix all YAML syntax errors. Output only the corrected YAML."
        )
        raw = provider.complete(correction_prompt, system=_SYSTEM_PROMPT)
        workflow_yaml = _extract_yaml(raw)

    return template_name, workflow_yaml


def _extract_yaml(raw: str) -> str:
    """Strip markdown fences if the LLM wrapped the output."""
    match = re.search(r"```(?:yaml|yml)?\s*\n?(name:.*?)\n?```", raw, re.DOTALL)
    if match:
        return match.group(1).strip()
    stripped = raw.strip()
    if stripped.startswith("name:") or stripped.startswith("on:"):
        return stripped
    # Best-effort: find first key that looks like a workflow root
    match = re.search(r"((?:name:|on:|jobs:).*)", raw, re.DOTALL)
    if match:
        return match.group(1).strip()
    return stripped


def _is_valid_yaml(content: str) -> bool:
    """Validate that the content parses as YAML and has required workflow keys."""
    try:
        data = yaml.safe_load(content)
    except yaml.YAMLError:
        return False
    if not isinstance(data, dict):
        return False
    # PyYAML parses the YAML key `on` as Python True (boolean YAML value)
    has_trigger = "on" in data or True in data
    return has_trigger and "jobs" in data
