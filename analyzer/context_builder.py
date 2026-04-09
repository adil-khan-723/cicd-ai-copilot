"""
Context Builder (Increment 14)

Merges pipeline metadata + verification report + cleaned log into a single
LLM-ready payload, staying within an 850-token budget.

Budget allocation (approximate):
  - System prompt:          ~100 tokens  (static, not included here)
  - Pipeline metadata:       ~50 tokens
  - Verification findings:  ~150 tokens
  - Cleaned log:            ~550 tokens  (trimmed if needed)
  Total:                    ~850 tokens
"""
import tiktoken

from parser.models import FailureContext
from verification.models import VerificationReport

# Budget constants (in tokens)
TOTAL_BUDGET = 850
METADATA_BUDGET = 50
VERIFICATION_BUDGET = 150
LOG_BUDGET = TOTAL_BUDGET - METADATA_BUDGET - VERIFICATION_BUDGET  # 550

_enc = tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    return len(_enc.encode(text))


def build_context(
    log: str,
    report: VerificationReport | None,
    context: FailureContext,
) -> str:
    """
    Build the LLM user prompt from cleaned log + verification report + metadata.
    Trims the log section to stay within budget.

    Returns a single string to be sent as the user message to the LLM.
    """
    metadata_block = _build_metadata(context)
    verification_block = _build_verification(report)
    log_block = _build_log(log, metadata_block, verification_block)

    parts = [metadata_block]
    if verification_block:
        parts.append(verification_block)
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

    # Hard cap at VERIFICATION_BUDGET tokens
    if count_tokens(text) > VERIFICATION_BUDGET:
        text = _trim_to_tokens(text, VERIFICATION_BUDGET)

    return text


def _build_log(log: str, metadata_block: str, verification_block: str) -> str:
    # Calculate remaining token budget for the log
    used = count_tokens(metadata_block)
    if verification_block:
        used += count_tokens(verification_block)
    # Add ~10 tokens for separators/headers
    used += 10

    remaining = TOTAL_BUDGET - used
    available = min(remaining, LOG_BUDGET)

    header = "## Failed Stage Log"
    header_tokens = count_tokens(header + "\n")
    log_tokens_available = available - header_tokens

    trimmed_log = _trim_to_tokens(log, log_tokens_available)
    return f"{header}\n{trimmed_log}"


def _trim_to_tokens(text: str, max_tokens: int) -> str:
    """Trim text to fit within max_tokens. Appends '[...truncated]' if trimmed."""
    if count_tokens(text) <= max_tokens:
        return text

    # Binary-search for the cutoff character index
    tokens = _enc.encode(text)
    truncated_tokens = tokens[:max_tokens - 5]  # reserve 5 tokens for suffix
    truncated = _enc.decode(truncated_tokens)
    return truncated + "\n[...truncated]"
