"""
Extract credential ID references from a Declarative Jenkinsfile.

Handles:
  - credentialsId: 'ID'                    (withCredentials, environment block, etc.)
  - credentials('ID')                      (environment block shorthand)
  - sshagent(credentials: ['ID'])          (SSH Agent plugin, string literal)
  - docker.withRegistry('url', 'ID')       (Docker Registry plugin, string literal)
  - CRED_VAR = 'id' in environment block   (variable assigned then used in credential context)

Skips dynamic references like `credentialsId: env.MY_VAR`.
"""
import re

# credentialsId: 'ID' or credentialsId: "ID"
_CRED_ID_RE = re.compile(r"credentialsId\s*:\s*['\"]([^'\"]+)['\"]")

# credentials('ID') or credentials("ID") — environment block shorthand
_CRED_SHORTHAND_RE = re.compile(r"\bcredentials\s*\(\s*['\"]([^'\"]+)['\"]\s*\)")

# sshagent(credentials: ['ID', ...]) — string literals only
_SSHAGENT_LITERAL_RE = re.compile(r"sshagent\s*\(\s*credentials\s*:\s*\[([^\]]+)\]")
_QUOTED_RE = re.compile(r"['\"]([^'\"]+)['\"]")

# docker.withRegistry('url', 'ID') or docker.withRegistry("url", "ID")
_DOCKER_REGISTRY_RE = re.compile(
    r"docker\.withRegistry\s*\(\s*['\"][^'\"]*['\"]\s*,\s*['\"]([^'\"]+)['\"]"
)

# Environment block: VAR_NAME = 'value' where VAR_NAME suggests a credential
# Matches: DOCKERHUB_CREDS = 'my-cred-id', SSH_KEY = 'ssh-key-id', etc.
_CRED_VAR_NAMES = re.compile(
    r"(CRED|SECRET|KEY|TOKEN|PASS|SSH|CERT|AUTH)",
    re.IGNORECASE,
)
_ENV_ASSIGNMENT_RE = re.compile(r"^\s*\w+\s*=\s*['\"]([^'\"]+)['\"]", re.MULTILINE)
_ENV_VAR_RE = re.compile(r"^\s*(\w+)\s*=\s*['\"]([^'\"]+)['\"]", re.MULTILINE)


def extract_credential_ids(jenkinsfile: str) -> list[str]:
    """Return unique credential IDs referenced in the Jenkinsfile, in order of appearance."""
    seen: set[str] = set()
    result: list[str] = []

    def _add(cid: str) -> None:
        if cid not in seen:
            seen.add(cid)
            result.append(cid)

    for m in _CRED_ID_RE.findall(jenkinsfile):
        _add(m)

    for m in _CRED_SHORTHAND_RE.findall(jenkinsfile):
        _add(m)

    for block in _SSHAGENT_LITERAL_RE.findall(jenkinsfile):
        for m in _QUOTED_RE.findall(block):
            _add(m)

    for m in _DOCKER_REGISTRY_RE.findall(jenkinsfile):
        _add(m)

    # Environment block variables whose names suggest credentials
    for var_name, value in _ENV_VAR_RE.findall(jenkinsfile):
        if _CRED_VAR_NAMES.search(var_name):
            _add(value)

    return result
