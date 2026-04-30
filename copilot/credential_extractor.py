"""
Extract credentialsId references from a Declarative Jenkinsfile.

Works for all Jenkins credential binding types (string, usernamePassword,
sshUserPrivateKey, dockerCert, file, etc.) — any binding that uses the
`credentialsId:` named argument.

Skips dynamic references like `credentialsId: env.MY_VAR` (non-string literals
can't be resolved statically and won't match the pattern).
"""
import re

_CRED_ID_RE = re.compile(r"credentialsId\s*:\s*['\"]([^'\"]+)['\"]")


def extract_credential_ids(jenkinsfile: str) -> list[str]:
    """Return unique credential IDs referenced in the Jenkinsfile, in order of appearance."""
    matches = _CRED_ID_RE.findall(jenkinsfile)
    seen: set[str] = set()
    result: list[str] = []
    for m in matches:
        if m not in seen:
            seen.add(m)
            result.append(m)
    return result
