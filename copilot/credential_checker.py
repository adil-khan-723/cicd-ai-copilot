"""
Cross-check extracted credential IDs against what exists in Jenkins.

Returns only the IDs that are missing — no false positives.
If the Jenkins API is unavailable, returns an empty list (fail-open:
better to not block the commit than to falsely report everything missing).
"""
import logging
import requests
from config import get_settings

logger = logging.getLogger(__name__)


def get_missing_credentials(credential_ids: list[str]) -> list[str]:
    """
    Given a list of credential IDs, return those that don't exist in Jenkins.

    Uses the Jenkins Credentials REST API. Fails open (returns []) if Jenkins
    is unreachable or the API returns unexpected data.
    """
    if not credential_ids:
        return []

    s = get_settings()
    if not s.jenkins_url or not s.jenkins_token:
        logger.warning("credential_checker: Jenkins not configured, skipping check")
        return []

    try:
        url = (
            f"{s.jenkins_url.rstrip('/')}/credentials/store/system/domain/_/"
            "api/json?tree=credentials[id]"
        )
        resp = requests.get(url, auth=(s.jenkins_user, s.jenkins_token), timeout=8)
        resp.raise_for_status()
        data = resp.json()
        existing = {c["id"] for c in data.get("credentials", []) if c.get("id")}
        return [cid for cid in credential_ids if cid not in existing]
    except Exception as e:
        logger.warning("credential_checker: failed to fetch Jenkins credentials: %s", e)
        return []
