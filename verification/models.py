from dataclasses import dataclass, field


@dataclass
class ToolMismatch:
    referenced: str   # name used in Jenkinsfile / workflow YAML
    configured: str   # closest name found in Jenkins/GitHub config
    match_score: float  # Levenshtein ratio (1.0 = exact)


@dataclass
class VerificationReport:
    platform: str  # "jenkins" or "github"
    matched_tools: list[str] = field(default_factory=list)
    mismatched_tools: list[ToolMismatch] = field(default_factory=list)
    missing_plugins: list[str] = field(default_factory=list)
    missing_credentials: list[str] = field(default_factory=list)
    missing_secrets: list[str] = field(default_factory=list)
    missing_runners: list[str] = field(default_factory=list)
    unpinned_actions: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def has_issues(self) -> bool:
        return bool(
            self.mismatched_tools
            or self.missing_plugins
            or self.missing_credentials
            or self.missing_secrets
            or self.missing_runners
        )

    def summary_lines(self) -> list[str]:
        lines = []
        for m in self.mismatched_tools:
            lines.append(f"Tool mismatch: '{m.referenced}' → closest match '{m.configured}' ({m.match_score:.0%})")
        for p in self.missing_plugins:
            lines.append(f"Missing plugin: {p}")
        for c in self.missing_credentials:
            lines.append(f"Missing credential: {c}")
        for s in self.missing_secrets:
            lines.append(f"Missing secret: {s}")
        for r in self.missing_runners:
            lines.append(f"Missing/unknown runner: {r}")
        for a in self.unpinned_actions:
            lines.append(f"Unpinned action: {a}")
        return lines
