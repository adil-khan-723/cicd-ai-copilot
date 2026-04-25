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

from verification.models import VerificationReport, ToolMismatch

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
            installed_plugins = _fetch_installed_plugins(client, jenkins_url)
            configured_creds = _fetch_credentials(client, jenkins_url)
    except httpx.ConnectError:
        report.errors.append(f"Cannot reach Jenkins at {jenkins_url}")
        return report
    except httpx.HTTPStatusError as e:
        report.errors.append(f"Jenkins API error: {e.response.status_code}")
        return report

    # Verify tools
    for tool_type, tool_name in referenced_tools:
        _check_tool(tool_type, tool_name, configured_tools, report)

    # Verify credentials
    for cred_id in referenced_creds:
        if cred_id in configured_creds:
            pass  # credential exists — no need to log matched creds
        else:
            report.missing_credentials.append(cred_id)

    # Check required plugins based on tool types used
    required_plugins = _infer_required_plugins(referenced_tools)
    for plugin_id in required_plugins:
        if plugin_id not in installed_plugins:
            report.missing_plugins.append(plugin_id)

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
