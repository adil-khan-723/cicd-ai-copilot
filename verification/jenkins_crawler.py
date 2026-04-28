"""
Jenkins Tool Verification Crawler (Increment 12)

Parses a Jenkinsfile for tool references, then cross-checks against:
  - Jenkins Global Tool Configuration (via /api/json)
  - Installed plugins (via /pluginManager/api/json)
  - Configured credentials (via /credentials/store/system/domain/_/api/json)

Returns a VerificationReport with matched, mismatched, missing plugins,
and missing credentials. Tool name comparison uses exact match first,
then Levenshtein fuzzy match (threshold 0.85).
"""
import re
import logging
import httpx
from Levenshtein import ratio as levenshtein_ratio

from verification.models import VerificationReport, ToolMismatch, ToolInstallIssue, ToolUsagePatternIssue

logger = logging.getLogger(__name__)

# Matches: tools { maven 'Maven3'; jdk 'JDK11' }
_TOOLS_BLOCK = re.compile(r"tools\s*\{([^}]+)\}", re.DOTALL)
_TOOL_ENTRY = re.compile(r"(\w+)\s+['\"]([^'\"]+)['\"]")

# Matches: withMaven(maven: 'Maven3') or tool(name: 'Maven3', type: 'maven')
_WITH_MAVEN_RE = re.compile(r"withMaven\s*\([^)]*maven\s*:\s*['\"]([^'\"]+)['\"]")
_TOOL_STEP_RE  = re.compile(r"tool\s*(?:name\s*:\s*)?['\"]([^'\"]+)['\"](?:[^)]*type\s*:\s*['\"](\w+)['\"])?")


# Matches: credentials('CRED_ID') or credentialsId: 'CRED_ID'
_CRED_PATTERNS = [
    re.compile(r"credentials\s*\(\s*['\"]([^'\"]+)['\"]\s*\)"),
    re.compile(r"credentialsId\s*:\s*['\"]([^'\"]+)['\"]"),
    re.compile(r"withCredentials\s*\(\s*\[.*?id\s*:\s*['\"]([^'\"]+)['\"]", re.DOTALL),
]

_FUZZY_THRESHOLD = 0.85


def verify_jenkins_tools(
    jenkinsfile_content: str,
    jenkins_url: str,
    auth: tuple[str, str] | None = None,
    timeout: float = 10.0,
) -> VerificationReport:
    """
    Parse Jenkinsfile content and verify tools/credentials against a live Jenkins instance.

    Args:
        jenkinsfile_content: Raw Jenkinsfile text
        jenkins_url: Jenkins base URL (e.g. "http://jenkins:8080")
        auth: Optional (username, api_token) tuple
        timeout: HTTP timeout in seconds

    Returns:
        VerificationReport
    """
    report = VerificationReport(platform="jenkins")

    referenced_tools = _parse_tools_block(jenkinsfile_content)
    referenced_creds = _parse_credentials(jenkinsfile_content)

    if not referenced_tools and not referenced_creds:
        logger.debug("No tools or credentials found in Jenkinsfile")
        return report

    try:
        with httpx.Client(auth=auth, timeout=timeout) as client:
            configured_tools = _fetch_configured_tools(client, jenkins_url)
            tool_install_details = _fetch_tool_install_details(client, jenkins_url)
            installed_plugins = _fetch_installed_plugins(client, jenkins_url)
            configured_creds = _fetch_credentials(client, jenkins_url)
    except httpx.ConnectError:
        report.errors.append(f"Cannot reach Jenkins at {jenkins_url}")
        return report
    except httpx.HTTPStatusError as e:
        report.errors.append(f"Jenkins API error: {e.response.status_code}")
        return report

    # Verify tools — name match + install health
    for tool_type, tool_name in referenced_tools:
        _check_tool(tool_type, tool_name, configured_tools, report)
        _check_tool_install(tool_type, tool_name, configured_tools, tool_install_details, report)

    # Verify credentials
    for cred_id in referenced_creds:
        if cred_id not in configured_creds:
            report.missing_credentials.append(cred_id)

    # Check required plugins based on tool types used
    required_plugins = _infer_required_plugins(referenced_tools)
    for plugin_id in required_plugins:
        if plugin_id not in installed_plugins:
            report.missing_plugins.append(plugin_id)

    # Detect tool-declared-but-binary-used-directly pattern
    _check_tool_usage_patterns(jenkinsfile_content, referenced_tools, report)

    return report


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def _parse_tools_block(content: str) -> list[tuple[str, str]]:
    """
    Extract (tool_type, tool_name) pairs from all tool references in Jenkinsfile:
      - tools { maven 'Maven3' }          declarative tools block
      - withMaven(maven: 'Maven3')         pipeline-maven plugin step
      - tool name: 'Maven3', type: 'maven' scripted tool() step
    """
    tools: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()

    def _add(tool_type: str, tool_name: str) -> None:
        pair = (tool_type.lower(), tool_name)
        if pair not in seen:
            seen.add(pair)
            tools.append((tool_type.lower(), tool_name))

    # 1. Declarative tools {} block
    match = _TOOLS_BLOCK.search(content)
    if match:
        for entry in _TOOL_ENTRY.finditer(match.group(1)):
            _add(entry.group(1).strip(), entry.group(2).strip())

    # 2. withMaven(maven: 'Maven3') — pipeline-maven plugin
    for m in _WITH_MAVEN_RE.finditer(content):
        _add("maven", m.group(1))

    # 3. tool(name: 'Maven3', type: 'maven') or tool 'Maven3' (defaults to maven)
    for m in _TOOL_STEP_RE.finditer(content):
        tool_name = m.group(1)
        tool_type = m.group(2) if m.group(2) else "maven"
        _add(tool_type, tool_name)

    return tools


def _parse_credentials(content: str) -> list[str]:
    """Extract all credential IDs referenced in the Jenkinsfile."""
    creds: list[str] = []
    for pattern in _CRED_PATTERNS:
        creds.extend(pattern.findall(content))
    return list(dict.fromkeys(creds))  # deduplicate, preserve order


# ---------------------------------------------------------------------------
# Jenkins API fetchers
# ---------------------------------------------------------------------------

def _fetch_configured_tools(client: httpx.Client, jenkins_url: str) -> dict[str, list[str]]:
    """
    Returns {tool_type: [configured_name, ...]} from Jenkins global tool config.
    Uses the script console (POST /scriptText) which reliably returns all tool installations.
    Falls back to empty dict on any error.
    """
    # Enumerate every registered ToolDescriptor dynamically — no hardcoded type list,
    # picks up any installed tool plugin automatically.
    # Uses displayName as the type key (e.g. "Maven", "JDK", "Git") — clean and stable.
    script = (
        "import jenkins.model.Jenkins\n"
        "Jenkins.instance.getExtensionList(hudson.tools.ToolDescriptor.class).each { desc ->\n"
        "  try {\n"
        "    def typeName = desc.displayName?.toLowerCase()?.replaceAll('[^a-z0-9]', '') ?: 'tool'\n"
        "    desc.installations.each { inst ->\n"
        "      if (inst.name) println typeName + ':' + inst.name\n"
        "    }\n"
        "  } catch (e) {}\n"
        "}\n"
        "null\n"
    )
    url = f"{jenkins_url.rstrip('/')}/scriptText"
    try:
        resp = client.post(url, data={"script": script})
        resp.raise_for_status()
    except (httpx.HTTPStatusError, httpx.ConnectError):
        return {}

    tools: dict[str, list[str]] = {}
    for line in resp.text.splitlines():
        line = line.strip()
        if ":" not in line:
            continue
        tool_type, _, tool_name = line.partition(":")
        tool_type = tool_type.strip().lower()
        tool_name = tool_name.strip()
        if tool_type and tool_name:
            tools.setdefault(tool_type, []).append(tool_name)

    return tools


def _fetch_installed_plugins(client: httpx.Client, jenkins_url: str) -> set[str]:
    """Returns set of installed plugin short names."""
    url = f"{jenkins_url.rstrip('/')}/pluginManager/api/json?depth=1"
    try:
        resp = client.get(url)
        resp.raise_for_status()
        data = resp.json()
        return {p["shortName"] for p in data.get("plugins", [])}
    except (httpx.HTTPStatusError, KeyError):
        return set()


def _fetch_credentials(client: httpx.Client, jenkins_url: str) -> set[str]:
    """Returns set of configured credential IDs in the global domain."""
    url = f"{jenkins_url.rstrip('/')}/credentials/store/system/domain/_/api/json?depth=1"
    try:
        resp = client.get(url)
        resp.raise_for_status()
        data = resp.json()
        return {c.get("id", "") for c in data.get("credentials", [])}
    except (httpx.HTTPStatusError, KeyError):
        return set()


# ---------------------------------------------------------------------------
# New API fetcher: per-tool installation details
# ---------------------------------------------------------------------------

def _fetch_tool_install_details(client: httpx.Client, jenkins_url: str) -> dict[str, dict]:
    """
    Returns {tool_name: {"home": str, "auto_install": bool}} for every configured tool.
    Uses script console to enumerate all ToolInstallation objects dynamically — no
    hardcoded tool type list, picks up any plugin automatically.
    Falls back to empty dict on any error (non-fatal).
    """
    script = (
        "import jenkins.model.Jenkins\n"
        "import hudson.tools.ToolInstallation\n"
        "Jenkins.instance.getExtensionList(hudson.tools.ToolDescriptor.class).each { desc ->\n"
        "  try {\n"
        "    desc.installations.each { inst ->\n"
        "      def home = inst.home ?: ''\n"
        "      def autoInstall = inst.properties?.any { it instanceof hudson.tools.InstallSourceProperty } ?: false\n"
        "      println inst.name + '|' + home + '|' + autoInstall\n"
        "    }\n"
        "  } catch (e) {}\n"
        "}\n"
        "null\n"
    )
    url = f"{jenkins_url.rstrip('/')}/scriptText"
    try:
        resp = client.post(url, data={"script": script})
        resp.raise_for_status()
    except Exception:
        return {}

    details: dict[str, dict] = {}
    for line in resp.text.splitlines():
        parts = line.strip().split("|")
        if len(parts) < 3:
            continue
        name, home, auto_install_raw = parts[0], parts[1], parts[2]
        if name:
            details[name] = {
                "home": home.strip(),
                "auto_install": auto_install_raw.strip().lower() == "true",
            }
    return details


def _check_tool_install(
    tool_type: str,
    tool_name: str,
    configured_tools: dict[str, list[str]],
    install_details: dict[str, dict],
    report: VerificationReport,
) -> None:
    """
    Check whether a matched tool's installation looks healthy.
    Only runs when the tool name is already confirmed as matched (exact).
    Flags: empty home path, auto-install with no home set (relies on network download).
    """
    # Only check tools that passed the name match (in matched_tools)
    if tool_name not in report.matched_tools:
        return

    detail = install_details.get(tool_name)
    if not detail:
        # No install details available — cannot assess, skip silently
        return

    home = detail["home"]
    auto_install = detail["auto_install"]

    if not home and not auto_install:
        report.tool_install_issues.append(ToolInstallIssue(
            tool_type=tool_type,
            tool_name=tool_name,
            issue="no install home path and no auto-install configured — tool may not be available at runtime",
        ))
    elif not home and auto_install:
        report.tool_install_issues.append(ToolInstallIssue(
            tool_type=tool_type,
            tool_name=tool_name,
            issue="relies on auto-install (network download at build time) — will fail in air-gapped environments or if download URL is unreachable",
        ))


# ---------------------------------------------------------------------------
# Tool usage pattern check: declared tool but binary used directly in sh/bat
# ---------------------------------------------------------------------------

# Maps tool type → set of binary names that could appear in sh/bat steps
_TOOL_BINARIES: dict[str, set[str]] = {
    "maven":   {"mvn", "mvnw", "./mvnw"},
    "gradle":  {"gradle", "gradlew", "./gradlew"},
    "jdk":     {"java", "javac", "jar"},
    "nodejs":  {"node", "npm", "npx", "yarn", "pnpm"},
    "ant":     {"ant"},
    "docker":  {"docker", "docker-compose"},
    "git":     {"git"},
}

# Matches sh/bat/powershell step content: sh 'cmd' or sh "cmd" or sh(script: 'cmd')
_SH_STEP_RE = re.compile(
    r"""\b(?:sh|bat|powershell)\s*(?:\(\s*(?:script\s*:\s*)?)?(?:['"])(.*?)(?:['"])""",
    re.DOTALL,
)


def _check_tool_usage_patterns(
    jenkinsfile: str,
    referenced_tools: list[tuple[str, str]],
    report: VerificationReport,
) -> None:
    """
    Detect tools declared in tools{}/withMaven()/tool() but whose binary is called
    directly in sh/bat steps. This means the tool is resolved by Jenkins but its
    bin/ directory may not be on PATH in the shell environment.

    Pattern: maven declared → 'mvn ...' appears in sh step → flag it.
    Only flags tools that are in the matched or mismatched list (i.e. Jenkins knows about them).
    Does NOT flag if a withMaven() or tool() step wrapping the sh call is present
    (those properly export the PATH).
    """
    if not referenced_tools or not jenkinsfile:
        return

    known_names = {name for _, name in referenced_tools}

    # Collect all sh/bat command strings
    sh_commands = [m.group(1) for m in _SH_STEP_RE.finditer(jenkinsfile)]

    for tool_type, tool_name in referenced_tools:
        binaries = _TOOL_BINARIES.get(tool_type.lower())
        if not binaries:
            continue

        # Check whether a proper wrapper is already in place for this tool type
        has_wrapper = _has_tool_wrapper(jenkinsfile, tool_type, tool_name)
        if has_wrapper:
            continue

        for cmd in sh_commands:
            # Check if the first token of the command is a known binary for this tool type
            first_token = cmd.strip().split()[0] if cmd.strip() else ""
            # Strip leading ./ for comparison
            bare = first_token.lstrip("./")
            if bare in {b.lstrip("./") for b in binaries}:
                report.tool_usage_pattern_issues.append(ToolUsagePatternIssue(
                    tool_type=tool_type,
                    tool_name=tool_name,
                    declared_in=_declared_in(jenkinsfile, tool_type, tool_name),
                    used_as="direct_sh",
                    binary=first_token or bare,
                ))
                break  # one finding per tool is enough


def _has_tool_wrapper(jenkinsfile: str, tool_type: str, tool_name: str) -> bool:
    """
    Return True if the Jenkinsfile already wraps sh steps with a proper environment
    exporter for this tool: withMaven(), tool(), or environment { PATH } block.
    """
    name_escaped = re.escape(tool_name)
    if tool_type == "maven":
        # withMaven(maven: 'Maven-3') properly exports PATH
        if re.search(rf"""withMaven\s*\([^)]*maven\s*:\s*['\"]{name_escaped}['\"]""", jenkinsfile):
            return True
    # tool('ToolName') or tool(name: 'ToolName') — scripted PATH export
    if re.search(rf"""tool\s*(?:name\s*:\s*)?['\"]({name_escaped})['\"]""", jenkinsfile):
        # Only counts as a wrapper if the result is used (assigned or in PATH step)
        if re.search(r"""(?:env\.PATH|PATH\s*=|def\s+\w+\s*=\s*tool)""", jenkinsfile):
            return True
    return False


def _declared_in(jenkinsfile: str, tool_type: str, tool_name: str) -> str:
    """Return where the tool is declared: tools_block | with_maven | tool_step."""
    name_escaped = re.escape(tool_name)
    if re.search(rf"""tools\s*\{{[^}}]*{name_escaped}""", jenkinsfile, re.DOTALL):
        return "tools_block"
    if re.search(rf"""withMaven\s*\([^)]*maven\s*:\s*['\"]{name_escaped}['\"]""", jenkinsfile):
        return "with_maven"
    return "tool_step"


# ---------------------------------------------------------------------------
# Verification logic
# ---------------------------------------------------------------------------

def _check_tool(
    tool_type: str,
    tool_name: str,
    configured_tools: dict[str, list[str]],
    report: VerificationReport,
) -> None:
    """Exact match → fuzzy match → record mismatch or match."""
    all_configured: list[str] = []
    for names in configured_tools.values():
        all_configured.extend(names)

    if not all_configured:
        # Can't verify without data — skip silently
        return

    # Exact match
    if tool_name in all_configured:
        report.matched_tools.append(tool_name)
        return

    # Fuzzy match
    best_name = ""
    best_score = 0.0
    for configured_name in all_configured:
        score = levenshtein_ratio(tool_name.lower(), configured_name.lower())
        if score > best_score:
            best_score = score
            best_name = configured_name

    if best_score >= _FUZZY_THRESHOLD:
        # Close enough to flag as mismatch (not missing entirely)
        report.mismatched_tools.append(ToolMismatch(
            referenced=tool_name,
            configured=best_name,
            match_score=best_score,
        ))
    else:
        # Nothing close — treat as mismatch with low confidence
        report.mismatched_tools.append(ToolMismatch(
            referenced=tool_name,
            configured=best_name or "(none)",
            match_score=best_score,
        ))


_PLUGIN_MAP: dict[str, str] = {
    "maven": "maven-plugin",
    "jdk": "jdk-tool",
    "gradle": "gradle",
    "nodejs": "nodejs",
    "docker": "docker-plugin",
    "git": "git",
    "ant": "ant",
}


def _infer_required_plugins(tools: list[tuple[str, str]]) -> list[str]:
    """Map tool types to plugin short names."""
    plugins = []
    for tool_type, _ in tools:
        plugin = _PLUGIN_MAP.get(tool_type.lower())
        if plugin:
            plugins.append(plugin)
    return plugins


def get_configured_tools(jenkins_url: str, auth=None, timeout: float = 10.0) -> dict[str, list[str]]:
    """Public helper: return {tool_type: [name, ...]} from Jenkins global tool config."""
    try:
        with httpx.Client(auth=auth, timeout=timeout) as client:
            return _fetch_configured_tools(client, jenkins_url)
    except Exception:
        return {}
