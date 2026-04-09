"""
Repo committer (Increment 27).

Commits a generated pipeline file to a GitHub repository via PyGithub.
Creates or updates the file at the appropriate path.
"""
import logging
from datetime import datetime, timezone

from github import Github, GithubException
from config import get_settings

logger = logging.getLogger(__name__)

_JENKINS_PATH = "Jenkinsfile"
_GITHUB_ACTIONS_DIR = ".github/workflows"


def commit_pipeline_file(
    repo: str,
    platform: str,
    content: str,
    description: str,
    branch: str = "main",
) -> tuple[str, str]:
    """
    Create or update a pipeline file in the GitHub repo.

    Args:
        repo: 'owner/repo' string
        platform: 'jenkins' or 'github'
        content: File content to commit
        description: Original NL request (used in commit message)
        branch: Target branch (default: main)

    Returns:
        (file_path, commit_url) tuple

    Raises:
        RuntimeError on GitHub API failure
    """
    settings = get_settings()
    token = settings.github_token
    if not token:
        raise RuntimeError("GITHUB_TOKEN not configured — cannot commit file.")

    gh = Github(token)

    try:
        github_repo = gh.get_repo(repo)
    except GithubException as e:
        raise RuntimeError(f"Cannot access repo '{repo}': {e.data.get('message', str(e))}")

    file_path = _determine_file_path(platform, description)
    commit_message = (
        f"feat: add generated {platform} pipeline [bot]\n\n"
        f"Request: {description}\n"
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"
    )

    try:
        # Check if file already exists
        try:
            existing = github_repo.get_contents(file_path, ref=branch)
            result = github_repo.update_file(
                path=file_path,
                message=commit_message,
                content=content,
                sha=existing.sha,
                branch=branch,
            )
            action = "updated"
        except GithubException as e:
            if e.status == 404:
                result = github_repo.create_file(
                    path=file_path,
                    message=commit_message,
                    content=content,
                    branch=branch,
                )
                action = "created"
            else:
                raise

        commit_url = result["commit"].html_url
        logger.info("%s file %s in %s: %s", action.capitalize(), file_path, repo, commit_url)
        return file_path, commit_url

    except GithubException as e:
        msg = e.data.get("message", str(e)) if hasattr(e, "data") else str(e)
        raise RuntimeError(f"GitHub API error: {msg}")


def commit_file(
    repo: str,
    path: str,
    content: str,
    message: str,
    branch: str = "main",
) -> str:
    """
    Low-level helper: commit any file to the repo at a specific path.
    Returns the commit URL.
    """
    settings = get_settings()
    gh = Github(settings.github_token)

    try:
        github_repo = gh.get_repo(repo)
        try:
            existing = github_repo.get_contents(path, ref=branch)
            result = github_repo.update_file(path, message, content, existing.sha, branch=branch)
        except GithubException as e:
            if e.status == 404:
                result = github_repo.create_file(path, message, content, branch=branch)
            else:
                raise
        return result["commit"].html_url
    except GithubException as e:
        msg = e.data.get("message", str(e)) if hasattr(e, "data") else str(e)
        raise RuntimeError(f"GitHub commit failed: {msg}")


def _determine_file_path(platform: str, description: str) -> str:
    """Choose the file path based on platform and request description."""
    if platform == "jenkins":
        return _JENKINS_PATH

    # GitHub Actions: generate a workflow filename from the description
    slug = _slugify(description)
    return f"{_GITHUB_ACTIONS_DIR}/{slug}.yml"


def _slugify(text: str) -> str:
    """Convert description to a safe filename slug."""
    import re
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower().strip())
    slug = slug.strip("-")
    return slug[:50] or "pipeline"
