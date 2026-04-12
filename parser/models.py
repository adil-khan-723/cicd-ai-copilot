from dataclasses import dataclass, field
from typing import Literal


@dataclass
class FailureContext:
    job_name: str
    build_number: int | str
    failed_stage: str
    platform: Literal["jenkins", "github", "unknown"]
    raw_log: str = ""
    repo: str = ""
    branch: str = ""
    # Ordered list of (stage_name, status) from the CI system
    # status: "passed" | "failed" | "skipped"
    pipeline_stages: list[tuple[str, str]] = field(default_factory=list)
