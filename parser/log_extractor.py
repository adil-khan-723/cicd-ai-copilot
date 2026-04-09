import re
from parser.models import FailureContext

MAX_CHARS = 2000


def extract_failed_logs(context: FailureContext) -> str:
    """
    Extract only the failed stage log block from the raw log.
    Discards all passing stage output — only the failure goes to the LLM.
    """
    if not context.raw_log:
        return ""

    if context.platform == "jenkins":
        return _extract_jenkins_stage_block(context.raw_log, context.failed_stage)
    if context.platform == "github":
        return _extract_github_step_block(context.raw_log, context.failed_stage)

    # Unknown platform — return tail of log (most errors are at the end)
    return _tail(context.raw_log, MAX_CHARS)


def _extract_jenkins_stage_block(log: str, failed_stage: str) -> str:
    """
    Extract the log block for the failed Jenkins stage.
    Stages are delimited by: [Pipeline] stage (StageName) ... [Pipeline] stage
    """
    lines = log.splitlines()
    in_stage = False
    block: list[str] = []

    stage_pattern = re.compile(r"\[Pipeline\]\s+stage\s*\(([^)]+)\)")

    for line in lines:
        match = stage_pattern.search(line)
        if match:
            stage_name = match.group(1).strip()
            if stage_name.lower() == failed_stage.lower():
                in_stage = True
                block = [line]
                continue
            elif in_stage:
                # Entered the next stage — stop collecting
                break

        if in_stage:
            block.append(line)

    if not block:
        # Stage boundary not found — fall back to tail
        return _tail(log, MAX_CHARS)

    return _tail("\n".join(block), MAX_CHARS)


def _extract_github_step_block(log: str, failed_step: str) -> str:
    """
    Extract the log block for the failed GitHub Actions step.
    GitHub logs steps as: ##[group]Run <step-name> ... ##[endgroup]
    """
    lines = log.splitlines()
    in_step = False
    block: list[str] = []

    step_name = failed_step.split(" / ")[-1].lower()  # strip job prefix if present

    for line in lines:
        if "##[group]" in line and step_name in line.lower():
            in_step = True
            block = [line]
            continue
        if in_step and "##[endgroup]" in line:
            block.append(line)
            break
        if in_step:
            block.append(line)

    if not block:
        return _tail(log, MAX_CHARS)

    return _tail("\n".join(block), MAX_CHARS)


def _tail(text: str, max_chars: int) -> str:
    """Return the last max_chars characters of text (errors appear at the end)."""
    if len(text) <= max_chars:
        return text
    return "...[truncated]\n" + text[-max_chars:]
