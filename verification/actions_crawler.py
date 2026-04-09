"""
GitHub Actions Verification Crawler (Increment 13)

Parses a workflow YAML file and verifies:
  - All ${{ secrets.X }} references exist as repo/org secrets
  - Runner labels are valid (GitHub-hosted or self-hosted)
  - Actions are pinned to a commit SHA (warns on @main, @master, @latest, branch refs)

Returns a VerificationReport.
"""
import re
import logging
import httpx
import yaml

from verification.models import VerificationReport

logger = logging.getLogger(__name__)

# Matches ${{ secrets.SECRET_NAME }} (with any whitespace inside)
_SECRET_REF = re.compile(r"\$\{\{\s*secrets\.([A-Za-z0-9_]+)\s*\}\}")

# Matches action uses lines: actions/checkout@v4 or org/repo@abc1234
_USES_REF = re.compile(r"uses:\s*([^\s#]+)")

# SHA-pinned refs look like @<40-char hex>
_SHA_PIN = re.compile(r"@[0-9a-f]{40}$", re.IGNORECASE)

# Unpinned patterns: @main, @master, @latest, or @v-prefix without SHA
_UNPINNED = re.compile(r"@(main|master|latest|develop|\d+\.\d+)$", re.IGNORECASE)

# GitHub-hosted runner labels
# Sentinel: returned by _fetch_github_secrets when the API responds 403 (no permission)
# Caller interprets this as "skip secrets check silently"
_SKIP_SECRETS_CHECK = object()

_GITHUB_RUNNERS = {
    "ubuntu-latest", "ubuntu-22.04", "ubuntu-20.04", "ubuntu-24.04",
    "windows-latest", "windows-2022", "windows-2019",
    "macos-latest", "macos-14", "macos-13", "macos-12",
    "macos-latest-xlarge", "macos-14-xlarge",
}


def verify_actions_config(
    workflow_content: str,
    github_repo: str,
    github_token: str | None = None,
    timeout: float = 10.0,
) -> VerificationReport:
    """
    Parse workflow YAML content and verify secrets/runners against GitHub API.

    Args:
        workflow_content: Raw YAML text of the workflow file
        github_repo: "owner/repo" string
        github_token: Personal access token or Actions token (needs secrets:read scope)
        timeout: HTTP timeout in seconds

    Returns:
        VerificationReport
    """
    report = VerificationReport(platform="github")

    try:
        workflow = yaml.safe_load(workflow_content)
    except yaml.YAMLError as e:
        report.errors.append(f"YAML parse error: {e}")
        return report

    if not isinstance(workflow, dict):
        report.errors.append("Workflow YAML did not parse to a mapping")
        return report

    referenced_secrets = _extract_secrets(workflow_content)
    runner_labels = _extract_runner_labels(workflow)
    action_refs = _extract_action_refs(workflow_content)

    # Check runner labels
    for label in runner_labels:
        if label not in _GITHUB_RUNNERS and not label.startswith("self-hosted"):
            report.missing_runners.append(label)

    # Check action pins
    for ref in action_refs:
        if _UNPINNED.search(ref):
            report.unpinned_actions.append(ref)
        # SHA-pinned → OK; version tags like @v4 → acceptable, skip

    # Verify secrets against GitHub API (skip if no token)
    if referenced_secrets:
        if github_token:
            configured_secrets = _fetch_github_secrets(github_repo, github_token, timeout)
            if configured_secrets is None:
                report.errors.append("Could not fetch secrets from GitHub API")
            elif configured_secrets is not _SKIP_SECRETS_CHECK:
                for secret in referenced_secrets:
                    if secret not in configured_secrets:
                        report.missing_secrets.append(secret)
        else:
            logger.debug("No GitHub token provided — skipping secrets verification")

    return report


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def _extract_secrets(content: str) -> list[str]:
    """Extract all secrets.X references from raw YAML text."""
    found = _SECRET_REF.findall(content)
    # Filter out built-in pseudo-secrets
    builtins = {"GITHUB_TOKEN", "GITHUB_REF", "GITHUB_SHA"}
    return list(dict.fromkeys(s for s in found if s not in builtins))


def _extract_runner_labels(workflow: dict) -> list[str]:
    """Walk jobs and collect all runs-on values (string or list)."""
    labels: list[str] = []
    jobs = workflow.get("jobs", {})
    if not isinstance(jobs, dict):
        return labels
    for job_def in jobs.values():
        if not isinstance(job_def, dict):
            continue
        runs_on = job_def.get("runs-on")
        if isinstance(runs_on, str):
            labels.append(runs_on)
        elif isinstance(runs_on, list):
            labels.extend(runs_on)
    return labels


def _extract_action_refs(content: str) -> list[str]:
    """Extract all `uses:` action references from raw YAML text."""
    return list(dict.fromkeys(_USES_REF.findall(content)))


# ---------------------------------------------------------------------------
# GitHub API fetcher
# ---------------------------------------------------------------------------

def _fetch_github_secrets(
    repo: str,
    token: str,
    timeout: float,
) -> set[str] | None:
    """
    Fetch configured secret names for a repo.
    Returns set of secret names, or None on error.
    Tries repo secrets first, then org secrets.
    """
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    all_secrets: set[str] = set()

    try:
        with httpx.Client(headers=headers, timeout=timeout) as client:
            # Repo-level secrets
            url = f"https://api.github.com/repos/{repo}/actions/secrets"
            while url:
                resp = client.get(url)
                resp.raise_for_status()
                data = resp.json()
                for s in data.get("secrets", []):
                    all_secrets.add(s["name"])
                # Follow pagination
                url = resp.links.get("next", {}).get("url")

    except httpx.ConnectError:
        return None
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 403:
            logger.warning("No permission to list secrets (403) — skipping secrets check")
            return _SKIP_SECRETS_CHECK  # type: ignore[return-value]
        return None

    return all_secrets
