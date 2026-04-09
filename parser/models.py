from dataclasses import dataclass
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
