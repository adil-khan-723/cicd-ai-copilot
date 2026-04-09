"""
Jenkins Configurator (Increment 28).

Creates or updates a Jenkins job with a generated Declarative Jenkinsfile
using the python-jenkins library and Jenkins Pipeline Job XML config.
"""
import logging
import jenkins
from config import get_settings

logger = logging.getLogger(__name__)

_PIPELINE_JOB_XML = """\
<?xml version='1.1' encoding='UTF-8'?>
<flow-definition plugin="workflow-job">
  <description>{description}</description>
  <keepDependencies>false</keepDependencies>
  <properties/>
  <definition class="org.jenkinsci.plugins.workflow.cps.CpsFlowDefinition" plugin="workflow-cps">
    <script>{jenkinsfile_content}</script>
    <sandbox>true</sandbox>
  </definition>
  <triggers/>
  <disabled>false</disabled>
</flow-definition>
"""


def create_job(name: str, jenkinsfile_content: str, description: str = "") -> str:
    """
    Create or update a Jenkins Pipeline job with the given Jenkinsfile content.

    Args:
        name: Jenkins job name (will be created if it doesn't exist)
        jenkinsfile_content: Full Declarative Jenkinsfile as a string
        description: Optional job description

    Returns:
        Jenkins job URL

    Raises:
        RuntimeError on Jenkins API failure
    """
    settings = get_settings()

    if not settings.jenkins_url or settings.jenkins_url == "http://localhost:8080":
        if not settings.jenkins_token:
            raise RuntimeError("Jenkins not configured — set JENKINS_URL and JENKINS_TOKEN in .env")

    try:
        server = jenkins.Jenkins(
            settings.jenkins_url,
            username=settings.jenkins_user,
            password=settings.jenkins_token,
        )
    except Exception as e:
        raise RuntimeError(f"Cannot connect to Jenkins at {settings.jenkins_url}: {e}")

    config_xml = _PIPELINE_JOB_XML.format(
        description=_xml_escape(description or f"Generated pipeline: {name}"),
        jenkinsfile_content=_xml_escape(jenkinsfile_content),
    )

    try:
        if server.job_exists(name):
            server.reconfig_job(name, config_xml)
            action = "updated"
            logger.info("Updated Jenkins job: %s", name)
        else:
            server.create_job(name, config_xml)
            action = "created"
            logger.info("Created Jenkins job: %s", name)

        job_url = f"{settings.jenkins_url.rstrip('/')}/job/{name}/"
        return job_url

    except jenkins.JenkinsException as e:
        raise RuntimeError(f"Jenkins API error: {e}")


def _xml_escape(text: str) -> str:
    """Escape special XML characters."""
    return (
        text
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )
