import re
from parser.models import FailureContext


def parse_failure(payload: dict, source: str = "unknown") -> FailureContext:
    """
    Parse a webhook payload into a FailureContext.
    Supports Jenkins and GitHub Actions payload shapes.
    """
    if source == "github":
        return _parse_github(payload)
    if source == "jenkins":
        return _parse_jenkins(payload)
    # Best-effort for unknown sources — try both shapes
    if "workflow_run" in payload:
        return _parse_github(payload)
    return _parse_jenkins(payload)


def _parse_jenkins(payload: dict) -> FailureContext:
    job_name = payload.get("job_name") or payload.get("name", "unknown-job")
    build_number = payload.get("build_number") or payload.get("number", 0)
    raw_log = payload.get("log", "") or payload.get("build_log", "")

    # Extract failed stage from log header or dedicated field
    failed_stage = (
        payload.get("failed_stage")
        or payload.get("failedStage")
        or _extract_jenkins_stage(raw_log)
    )

    # Parse ordered stage list from payload if provided
    # Expected format: [{"name": "Test", "status": "failed"}, ...]
    # or a simple list of strings (all treated as the pipeline definition)
    pipeline_stages = _parse_stage_list(payload.get("stages", []), failed_stage)

    return FailureContext(
        job_name=job_name,
        build_number=build_number,
        failed_stage=failed_stage,
        platform="jenkins",
        raw_log=raw_log,
        branch=payload.get("branch", ""),
        pipeline_stages=pipeline_stages,
    )


def _parse_stage_list(stages_payload, failed_stage: str) -> list[tuple[str, str]]:
    """
    Normalise stages payload into list of (name, status) tuples.
    Accepts:
      - list of {"name": str, "status": str}
      - list of strings (stage names only — status inferred from failed_stage)
    """
    if not stages_payload:
        return []
    result = []
    seen_failed = False
    for s in stages_payload:
        if isinstance(s, dict):
            name = s.get("name", "")
            status = s.get("status", "passed").lower()
        elif isinstance(s, str):
            name = s
            # Everything before failed_stage passed, failed_stage failed, rest skipped
            if name == failed_stage:
                status = "failed"
                seen_failed = True
            elif seen_failed:
                status = "skipped"
            else:
                status = "passed"
        else:
            continue
        if name:
            result.append((name, status))
    return result


def _parse_github(payload: dict) -> FailureContext:
    wr = payload.get("workflow_run", {})
    repo = wr.get("repository", {}).get("full_name", "") or payload.get("repository", {}).get("full_name", "")
    job_name = wr.get("name") or payload.get("workflow", "unknown-workflow")
    build_number = wr.get("run_number") or payload.get("run_number", 0)
    raw_log = payload.get("log", "")

    # GitHub sends the failed job name in pull_requests or jobs field
    failed_stage = (
        payload.get("failed_job")
        or payload.get("failed_step")
        or _extract_github_failed_job(payload)
    )

    return FailureContext(
        job_name=job_name,
        build_number=build_number,
        failed_stage=failed_stage,
        platform="github",
        raw_log=raw_log,
        repo=repo,
        branch=wr.get("head_branch", ""),
    )


_ERROR_PATTERN = re.compile(r"\b(ERROR|FAILED|Exception|Error:|fatal|FAILURE)\b", re.IGNORECASE)
_STAGE_PATTERN = re.compile(r"\[Pipeline\]\s+stage\s*\(([^)]+)\)")


def _extract_jenkins_stage(log: str) -> str:
    """
    Scan Jenkins log for the stage that contains the error/failure.
    Splits log into stage blocks and returns the first block containing an error keyword.
    Falls back to the second-to-last stage if no error keyword found.
    """
    if not log:
        return "unknown-stage"

    # Split log into (stage_name, block_text) pairs
    lines = log.splitlines()
    stages: list[tuple[str, list[str]]] = []
    current_stage: str | None = None
    current_block: list[str] = []

    for line in lines:
        match = _STAGE_PATTERN.search(line)
        if match:
            if current_stage is not None:
                stages.append((current_stage, current_block))
            current_stage = match.group(1).strip()
            current_block = [line]
        else:
            if current_stage is not None:
                current_block.append(line)

    if current_stage is not None:
        stages.append((current_stage, current_block))

    if not stages:
        return "unknown-stage"

    # Return the first stage whose block contains an error keyword
    for name, block in stages:
        if _ERROR_PATTERN.search("\n".join(block)):
            return name

    # No error keyword found — return second-to-last stage (last is often cleanup)
    return stages[-2][0] if len(stages) >= 2 else stages[-1][0]


def _extract_github_failed_job(payload: dict) -> str:
    """Extract failed job/step name from GitHub Actions payload."""
    # Check jobs list if present (from expanded payloads)
    for job in payload.get("jobs", []):
        if job.get("conclusion") == "failure":
            # Find the failed step within the job
            for step in job.get("steps", []):
                if step.get("conclusion") == "failure":
                    return f"{job.get('name', 'unknown')} / {step.get('name', 'unknown')}"
            return job.get("name", "unknown-job")
    return "unknown-stage"
