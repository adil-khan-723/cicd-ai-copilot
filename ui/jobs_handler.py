"""
Fetches Jenkins jobs list via python-jenkins.
Returns a list of dicts safe to serialize as JSON.
"""
import logging
import jenkins
from config import get_settings

logger = logging.getLogger(__name__)


def get_jenkins_jobs() -> list[dict]:
    """
    Returns all Jenkins jobs with name, url, and status.
    Returns empty list if Jenkins is unreachable.

    Each dict has:
      name: str
      url: str
      status: "success" | "failure" | "running" | "unknown"
      last_build_number: int | None
      last_build_result: str | None
    """
    settings = get_settings()
    if not settings.jenkins_url or not settings.jenkins_token:
        return []

    try:
        server = jenkins.Jenkins(
            settings.jenkins_url,
            username=settings.jenkins_user,
            password=settings.jenkins_token,
        )
        raw_jobs = server.get_jobs()
    except Exception as e:
        logger.warning("Failed to fetch Jenkins jobs: %s", e)
        return []

    jobs = []
    for job in raw_jobs:
        color = job.get("color", "")
        entry = {
            "name": job.get("name", ""),
            "url": job.get("url", ""),
            "status": _color_to_status(color),
            "last_build_number": None,
            "last_build_result": None,
        }
        jobs.append(entry)

    return jobs


def trigger_job(job_name: str) -> dict:
    """
    Trigger a Jenkins job. Returns {"ok": True} or {"ok": False, "error": "..."}.
    """
    settings = get_settings()
    try:
        server = jenkins.Jenkins(
            settings.jenkins_url,
            username=settings.jenkins_user,
            password=settings.jenkins_token,
        )
        server.build_job(job_name)
        logger.info("Triggered job: %s", job_name)
        return {"ok": True}
    except jenkins.JenkinsException as e:
        return {"ok": False, "error": str(e)}
    except Exception as e:
        return {"ok": False, "error": f"Unexpected error: {e}"}


def _color_to_status(color: str) -> str:
    if "blue" in color:
        return "success"
    if "red" in color:
        return "failure"
    if "anime" in color:
        return "running"
    return "unknown"
