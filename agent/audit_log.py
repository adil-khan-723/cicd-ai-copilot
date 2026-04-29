"""
Audit log (Increment 19).

Append-only JSONL file recording every fix execution attempt.
Never logs secret values, credentials, or tokens.

Fields logged per entry:
  timestamp, fix_type, job_name, build_number,
  triggered_by (user ID), result, confidence_at_trigger
"""
import json
import logging
from datetime import datetime, timezone

from config import get_settings

logger = logging.getLogger(__name__)


def log_fix(
    fix_type: str,
    triggered_by: str,
    job_name: str,
    build_number: str | int,
    result: str,
    confidence_at_trigger: float = 0.0,
) -> None:
    """
    Append one fix execution record to the audit log.

    Args:
        fix_type: The fix that was executed (or 'dismissed' / 'manual_review')
        triggered_by: User ID of the person who triggered the fix
        job_name: Jenkins/GitHub Actions job name
        build_number: Build number (string or int)
        result: 'success' | 'failed' | 'dismissed' | 'acknowledged'
        confidence_at_trigger: LLM confidence score at the time of approval
    """
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "fix_type": fix_type,
        "job_name": job_name,
        "build_number": str(build_number),
        "triggered_by": triggered_by,
        "result": result,
        "confidence_at_trigger": round(confidence_at_trigger, 4),
    }

    path = _audit_path()
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
        logger.debug("Audit log entry written: %s", entry)
    except OSError as e:
        logger.error("Failed to write audit log entry: %s", e)


def _audit_path() -> str:
    configured = get_settings().audit_log_path
    if configured:
        return configured
    from ui.profiles_store import get_active_profile_dir
    return str(get_active_profile_dir() / "audit.log")


def read_recent(n: int = 50) -> list[dict]:
    """
    Return the last n entries from the audit log (most recent last).
    Returns empty list if the log doesn't exist yet.
    """
    path = _audit_path()
    try:
        with open(path, encoding="utf-8") as f:
            lines = f.readlines()
        entries = []
        for line in lines:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    logger.warning("Skipping malformed audit log line: %.80s", line)
        return entries[-n:]
    except FileNotFoundError:
        return []
