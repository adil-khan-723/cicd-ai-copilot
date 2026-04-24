"""
Context Builder

Merges pipeline metadata + verification report + failing stage snippet
+ cleaned log into a single LLM-ready payload, staying within a 1000-token budget.

Budget allocation (approximate):
  - System prompt:          ~100 tokens  (static, not included here)
  - Pipeline metadata:       ~50 tokens
  - Verification findings:  ~150 tokens
  - Failing stage snippet:  ~150 tokens  (trimmed if needed; omitted when unavailable)
  - Cleaned log:            ~550 tokens  (trimmed if needed)
  Total:                   ~1000 tokens
"""
import re
import tiktoken

from parser.models import FailureContext
from verification.models import VerificationReport

# Budget constants (in tokens)
TOTAL_BUDGET = 1000
METADATA_BUDGET = 50
VERIFICATION_BUDGET = 150
STAGE_BUDGET = 150
LOG_BUDGET = TOTAL_BUDGET - METADATA_BUDGET - VERIFICATION_BUDGET - STAGE_BUDGET  # 650

_enc = tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    return len(_enc.encode(text))


def build_context(
    log: str,
    report: VerificationReport | None,
    context: FailureContext,
    jenkinsfile: str = "",
) -> str:
    """
    Build the LLM user prompt from cleaned log + verification report + metadata
    + optional failing stage Jenkinsfile snippet.

    The stage snippet gives the LLM ground truth about what the Jenkinsfile
    actually says, so it can spot typos, wrong step names, and misconfigurations
    directly rather than guessing from log output alone.

    Returns a single string to be sent as the user message to the LLM.
    """
    metadata_block = _build_metadata(context)
    verification_block = _build_verification(report)
    stage_block = _build_stage_snippet(jenkinsfile, context.failed_stage)
    log_block = _build_log(log, metadata_block, verification_block, stage_block)

    parts = [metadata_block]
    if verification_block:
        parts.append(verification_block)
    if stage_block:
        parts.append(stage_block)
    parts.append(log_block)

    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Block builders
# ---------------------------------------------------------------------------

def _build_metadata(context: FailureContext) -> str:
    lines = [
        "## Pipeline Failure Context",
        f"Platform: {context.platform}",
        f"Job: {context.job_name}",
        f"Build: #{context.build_number}",
        f"Failed stage: {context.failed_stage}",
    ]
    if context.branch:
        lines.append(f"Branch: {context.branch}")
    if context.repo:
        lines.append(f"Repo: {context.repo}")
    return "\n".join(lines)


def _build_verification(report: VerificationReport | None) -> str:
    if report is None or not report.has_issues:
        return ""

    lines = ["## Verification Findings"]
    for line in report.summary_lines():
        lines.append(f"- {line}")

    text = "\n".join(lines)

    if count_tokens(text) > VERIFICATION_BUDGET:
        text = _trim_to_tokens(text, VERIFICATION_BUDGET)

    return text


def _build_stage_snippet(jenkinsfile: str, failed_stage: str) -> str:
    """
    Extract the Groovy block for the failing stage from the Jenkinsfile.

    Tries to match:  stage('<failed_stage>') { ... }
    Falls back to a case-insensitive search if exact match fails.
    Returns empty string when Jenkinsfile is absent or stage not found.
    """
    if not jenkinsfile or not failed_stage:
        return ""

    snippet = _extract_stage_block(jenkinsfile, failed_stage)
    if not snippet:
        return ""

    header = f"## Failing Stage Source ({failed_stage})"
    text = f"{header}\n```groovy\n{snippet}\n```"

    if count_tokens(text) > STAGE_BUDGET:
        text = _trim_to_tokens(text, STAGE_BUDGET)

    return text


def _build_log(
    log: str,
    metadata_block: str,
    verification_block: str,
    stage_block: str,
) -> str:
    used = count_tokens(metadata_block)
    if verification_block:
        used += count_tokens(verification_block)
    if stage_block:
        used += count_tokens(stage_block)
    used += 15  # separators + header

    remaining = TOTAL_BUDGET - used
    available = min(remaining, LOG_BUDGET)

    header = "## Failed Stage Log"
    header_tokens = count_tokens(header + "\n")
    log_tokens_available = available - header_tokens

    trimmed_log = _trim_to_tokens(log, log_tokens_available)
    return f"{header}\n{trimmed_log}"


# ---------------------------------------------------------------------------
# Stage extraction
# ---------------------------------------------------------------------------

def _extract_stage_block(jenkinsfile: str, stage_name: str) -> str:
    """
    Extract the full `stage('name') { ... }` block using brace counting.
    Returns the outer stage(...) { ... } text, or empty string if not found.
    """
    # Build pattern that matches the opening of the target stage
    escaped = re.escape(stage_name)
    open_re = re.compile(
        rf"""stage\s*\(\s*(?:'|"){escaped}(?:'|")\s*\)\s*\{{""",
        re.IGNORECASE,
    )

    m = open_re.search(jenkinsfile)
    if not m:
        return ""

    # Walk forward counting braces to find the matching closing brace
    start = m.start()
    pos = m.end()
    depth = 1

    while pos < len(jenkinsfile) and depth > 0:
        ch = jenkinsfile[pos]
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
        pos += 1

    return jenkinsfile[start:pos].strip()


# ---------------------------------------------------------------------------
# Shared utilities
# ---------------------------------------------------------------------------

def _trim_to_tokens(text: str, max_tokens: int) -> str:
    """Trim text to fit within max_tokens. Appends '[...truncated]' if trimmed."""
    if count_tokens(text) <= max_tokens:
        return text

    tokens = _enc.encode(text)
    truncated_tokens = tokens[:max_tokens - 5]
    truncated = _enc.decode(truncated_tokens)
    return truncated + "\n[...truncated]"
