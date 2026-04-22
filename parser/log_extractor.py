import re
from parser.models import FailureContext

MAX_CHARS = 2000

# Matches: [Pipeline] { (StageName)
_STAGE_OPEN_RE = re.compile(r'^\[Pipeline\] \{ \((.+?)\)\s*$')
_STAGE_CLOSE_RE = re.compile(r'^\[Pipeline\] \}')


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

    return _tail(context.raw_log, MAX_CHARS)


def _extract_jenkins_stage_block(log: str, failed_stage: str) -> str:
    """
    Extract the log block for the failed Jenkins stage.
    Uses [Pipeline] { (Name) ... [Pipeline] } block boundaries.
    """
    lines = log.splitlines()
    depth = 0
    in_stage = False
    block: list[str] = []

    for line in lines:
        stripped = line.rstrip()
        open_match = _STAGE_OPEN_RE.match(stripped)

        if open_match and not in_stage:
            # Only check for target stage when not already inside one
            stage_name = open_match.group(1).strip()
            if stage_name.lower() == failed_stage.lower():
                in_stage = True
                depth = 1
                block = [line]
            continue  # stage-open lines are boundaries, never content

        if not in_stage:
            continue

        if open_match:
            # Nested stage open inside target stage
            depth += 1
            block.append(line)
        elif _STAGE_CLOSE_RE.match(stripped):
            depth -= 1
            if depth <= 0:
                # Closing brace of the target stage — stop (don't include it)
                break
            block.append(line)
        else:
            block.append(line)

    if not block:
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

    step_name = failed_step.split(" / ")[-1].lower()

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
    """Return the last max_chars characters of text."""
    if len(text) <= max_chars:
        return text
    return "...[truncated]\n" + text[-max_chars:]
