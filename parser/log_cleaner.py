import re


# Patterns to strip from logs
_ANSI = re.compile(r"\x1b\[[0-9;]*[mGKHF]")
_TIMESTAMP_FULL = re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?")
_TIMESTAMP_SHORT = re.compile(r"\b\d{2}:\d{2}:\d{2}(?:\.\d+)?\b")
_LOG_PREFIXES = re.compile(r"^\s*\[(INFO|DEBUG|TRACE|Pipeline|Checks|Declarative)\]\s*", re.MULTILINE)
_PROGRESS_BAR = re.compile(r"[#=\-]{10,}")
_BLANK_LINES = re.compile(r"\n{3,}")


def clean_log(raw: str) -> str:
    """
    Strip noise from extracted stage logs before sending to the LLM.
    Removes: ANSI codes, timestamps, INFO/DEBUG prefixes, progress bars, excess blank lines.
    """
    text = raw

    # Strip ANSI escape sequences first
    text = _ANSI.sub("", text)

    # Strip timestamps
    text = _TIMESTAMP_FULL.sub("", text)
    text = _TIMESTAMP_SHORT.sub("", text)

    # Strip common log level / pipeline prefixes
    text = _LOG_PREFIXES.sub("", text)

    # Strip Jenkins/npm progress bars
    text = _PROGRESS_BAR.sub("", text)

    # Collapse multiple blank lines into one
    text = _BLANK_LINES.sub("\n\n", text)

    # Strip leading/trailing whitespace per line
    lines = [line.rstrip() for line in text.splitlines()]

    # Drop lines that are now empty after stripping (keep single blank lines as separators)
    cleaned: list[str] = []
    prev_blank = False
    for line in lines:
        is_blank = line.strip() == ""
        if is_blank and prev_blank:
            continue
        cleaned.append(line)
        prev_blank = is_blank

    return "\n".join(cleaned).strip()
