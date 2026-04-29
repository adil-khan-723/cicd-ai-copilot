"""
Template selector — picks the closest base template from the templates/ directory
based on keywords in the natural language request.
"""
from pathlib import Path

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"

# keyword sets → template file (relative to TEMPLATES_DIR)
_JENKINS_RULES: list[tuple[set[str], str]] = [
    ({"python", "ecr", "aws"},          "jenkins/python-docker-ecr.groovy"),
    ({"python", "docker", "ecr"},       "jenkins/python-docker-ecr.groovy"),
    ({"java", "maven", "ecr"},          "jenkins/java-maven.groovy"),
    ({"java", "maven", "docker"},       "jenkins/java-maven.groovy"),
    ({"node", "docker"},                "jenkins/node-docker.groovy"),
    ({"nodejs", "docker"},              "jenkins/node-docker.groovy"),
    ({"javascript", "docker"},          "jenkins/node-docker.groovy"),
    ({"java", "maven"},                 "jenkins/java-maven.groovy"),
    ({"java", "gradle"},                "jenkins/java-maven.groovy"),
    ({"java", "spring"},                "jenkins/java-maven.groovy"),
    ({"java"},                          "jenkins/java-maven.groovy"),
    ({"maven"},                         "jenkins/java-maven.groovy"),
    ({"python"},                        "jenkins/python-docker-ecr.groovy"),
    ({"docker"},                        "jenkins/node-docker.groovy"),
]

_GITHUB_RULES: list[tuple[set[str], str]] = [
    ({"python", "ecr"},                 "github/docker-ecr.yml"),
    ({"docker", "ecr"},                 "github/docker-ecr.yml"),
    ({"python", "ci"},                  "github/python-ci.yml"),
    ({"python", "test"},                "github/python-ci.yml"),
    ({"python"},                        "github/python-ci.yml"),
    ({"docker"},                        "github/docker-ecr.yml"),
]


def select_jenkins_template(nl_request: str) -> tuple[str, str]:
    """
    Return (template_name, template_content) for the best-matching Jenkins template.
    Falls back to generic.groovy if nothing matches.
    """
    return _select("jenkins", nl_request, _JENKINS_RULES, "jenkins/generic.groovy")


def select_github_template(nl_request: str) -> tuple[str, str]:
    """
    Return (template_name, template_content) for the best-matching GitHub Actions template.
    Falls back to generic.yml if nothing matches.
    """
    return _select("github", nl_request, _GITHUB_RULES, "github/generic.yml")


def _select(
    platform: str,
    nl_request: str,
    rules: list[tuple[set[str], str]],
    fallback: str,
) -> tuple[str, str]:
    words = _tokenize(nl_request)
    best_path = fallback
    best_score = 0
    best_kw_size = 0

    for keywords, template_path in rules:
        score = len(keywords & words)
        # Higher match count wins; tie → larger keyword set wins (more specific rule)
        if score > best_score or (score == best_score and score > 0 and len(keywords) > best_kw_size):
            best_score = score
            best_kw_size = len(keywords)
            best_path = template_path

    full_path = TEMPLATES_DIR / best_path
    content = full_path.read_text(encoding="utf-8")
    return best_path, content


def _tokenize(text: str) -> set[str]:
    """Split request into normalized word tokens, handling 'node.js' → {'node', 'js'}."""
    import re
    words = re.split(r"[\s.,;!?/\-]+", text.lower())
    return {w for w in words if w}


def list_templates(platform: str) -> list[str]:
    """Return list of available template names for the given platform."""
    dir_path = TEMPLATES_DIR / platform
    if not dir_path.exists():
        return []
    return [f.name for f in sorted(dir_path.iterdir()) if f.is_file()]
