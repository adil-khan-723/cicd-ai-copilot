"""
Extract credential ID references from a Declarative Jenkinsfile.

Handles:
  - credentialsId: 'ID'           (withCredentials, environment block, etc.)
  - credentials('ID')             (environment block shorthand)
  - sshagent(credentials: ['ID']) (SSH Agent plugin)

Skips dynamic references like `credentialsId: env.MY_VAR`.
"""
import re

# credentialsId: 'ID' or credentialsId: "ID"
_CRED_ID_RE = re.compile(r"credentialsId\s*:\s*['\"]([^'\"]+)['\"]")

# credentials('ID') or credentials("ID") — environment block shorthand
_CRED_SHORTHAND_RE = re.compile(r"\bcredentials\s*\(\s*['\"]([^'\"]+)['\"]\s*\)")

# sshagent(credentials: ['ID', ...]) — SSH Agent plugin
_SSHAGENT_RE = re.compile(r"sshagent\s*\(\s*credentials\s*:\s*\[([^\]]+)\]")
_QUOTED_RE = re.compile(r"['\"]([^'\"]+)['\"]")


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

    for block in _SSHAGENT_RE.findall(jenkinsfile):
        for m in _QUOTED_RE.findall(block):
            _add(m)

    return result
