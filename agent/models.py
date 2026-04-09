from dataclasses import dataclass


@dataclass
class FixResult:
    success: bool
    fix_type: str
    detail: str = ""
