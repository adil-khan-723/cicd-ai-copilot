"""
Concrete fix implementations against Jenkins API.

Each function takes job_name + optional build_number and returns a FixResult.
All Jenkins calls go through python-jenkins.

Never auto-fixed (always diagnostic_only):
  - tool mismatches, missing plugins, missing credentials, IAM issues
"""
import logging
import jenkins
from config import get_settings
from agent.models import FixResult

logger = logging.getLogger(__name__)


def _get_jenkins_server() -> jenkins.Jenkins:
    s = get_settings()
    return jenkins.Jenkins(s.jenkins_url, username=s.jenkins_user, password=s.jenkins_token)


def retry_pipeline(job_name: str, build_number: str = "0") -> FixResult:
    """Re-queue the pipeline job."""
    try:
        server = _get_jenkins_server()
        server.build_job(job_name)
        logger.info("Triggered retry for job: %s", job_name)
        return FixResult(success=True, fix_type="retry", detail=f"Job '{job_name}' re-queued.")
    except jenkins.JenkinsException as e:
        logger.error("Failed to retry job %s: %s", job_name, e)
        return FixResult(success=False, fix_type="retry", detail=str(e))
    except Exception as e:
        logger.error("Unexpected error retrying %s: %s", job_name, e)
        return FixResult(success=False, fix_type="retry", detail=f"Unexpected error: {e}")


def clear_docker_cache(job_name: str, build_number: str = "0") -> FixResult:
    """Trigger build with DOCKER_NO_CACHE=true parameter, falling back to plain retry."""
    try:
        server = _get_jenkins_server()
        try:
            server.build_job(job_name, parameters={"DOCKER_NO_CACHE": "true"})
            logger.info("Triggered Docker cache-bust build for: %s", job_name)
            return FixResult(success=True, fix_type="clear_cache", detail=f"Job '{job_name}' triggered with DOCKER_NO_CACHE=true.")
        except Exception as param_err:
            # Job has no parameters — fall back to plain retry
            if "400" in str(param_err) or "Bad Request" in str(param_err):
                logger.warning("Job '%s' has no parameters, falling back to plain retry", job_name)
                server.build_job(job_name)
                return FixResult(success=True, fix_type="clear_cache", detail=f"Job '{job_name}' re-triggered (no parameters defined — plain retry).")
            raise
    except jenkins.JenkinsException as e:
        logger.error("Failed to clear Docker cache for %s: %s", job_name, e)
        return FixResult(success=False, fix_type="clear_cache", detail=str(e))
    except Exception as e:
        return FixResult(success=False, fix_type="clear_cache", detail=f"Unexpected error: {e}")


def clear_npm_cache(job_name: str, build_number: str = "0") -> FixResult:
    """Trigger build with CLEAR_NPM_CACHE=true parameter, falling back to plain retry."""
    try:
        server = _get_jenkins_server()
        try:
            server.build_job(job_name, parameters={"CLEAR_NPM_CACHE": "true"})
            logger.info("Triggered npm cache-bust build for: %s", job_name)
            return FixResult(success=True, fix_type="clear_cache", detail=f"Job '{job_name}' triggered with CLEAR_NPM_CACHE=true.")
        except Exception as param_err:
            if "400" in str(param_err) or "Bad Request" in str(param_err):
                server.build_job(job_name)
                return FixResult(success=True, fix_type="clear_cache", detail=f"Job '{job_name}' re-triggered (no parameters defined — plain retry).")
            raise
    except jenkins.JenkinsException as e:
        return FixResult(success=False, fix_type="clear_cache", detail=str(e))
    except Exception as e:
        return FixResult(success=False, fix_type="clear_cache", detail=f"Unexpected error: {e}")


def pull_fresh_image(job_name: str, build_number: str = "0") -> FixResult:
    """Trigger build with PULL_FRESH_IMAGE=true parameter, falling back to plain retry."""
    try:
        server = _get_jenkins_server()
        try:
            server.build_job(job_name, parameters={"PULL_FRESH_IMAGE": "true"})
            logger.info("Triggered fresh image pull build for: %s", job_name)
            return FixResult(success=True, fix_type="pull_image", detail=f"Job '{job_name}' triggered with PULL_FRESH_IMAGE=true.")
        except Exception as param_err:
            if "400" in str(param_err) or "Bad Request" in str(param_err):
                server.build_job(job_name)
                return FixResult(success=True, fix_type="pull_image", detail=f"Job '{job_name}' re-triggered (no parameters defined — plain retry).")
            raise
    except jenkins.JenkinsException as e:
        return FixResult(success=False, fix_type="pull_image", detail=str(e))
    except Exception as e:
        return FixResult(success=False, fix_type="pull_image", detail=f"Unexpected error: {e}")


def increase_timeout(job_name: str, build_number: str = "0") -> FixResult:
    """
    Double the timeout in the job's config XML.
    Reads current config, patches the <timeout> value, updates the job.
    Falls back to diagnostic_only if config can't be parsed.
    """
    try:
        server = _get_jenkins_server()
        config_xml = server.get_job_config(job_name)

        import re
        # Match <timeout>NNN</timeout> (Jenkins Build Timeout plugin)
        pattern = re.compile(r"(<timeout>)(\d+)(</timeout>)")
        match = pattern.search(config_xml)

        if not match:
            return FixResult(
                success=False,
                fix_type="increase_timeout",
                detail="No <timeout> element found in job config — increase manually.",
            )

        current = int(match.group(2))
        new_timeout = current * 2
        new_config = pattern.sub(f"\\g<1>{new_timeout}\\g<3>", config_xml)
        server.reconfig_job(job_name, new_config)

        logger.info("Increased timeout for %s: %d → %d", job_name, current, new_timeout)
        return FixResult(
            success=True,
            fix_type="increase_timeout",
            detail=f"Timeout increased from {current} to {new_timeout} minutes.",
        )
    except jenkins.JenkinsException as e:
        return FixResult(success=False, fix_type="increase_timeout", detail=str(e))
    except Exception as e:
        return FixResult(success=False, fix_type="increase_timeout", detail=f"Unexpected error: {e}")


def configure_tool(
    job_name: str,
    build_number: str = "0",
    referenced_name: str = "",
    configured_name: str = "",
) -> FixResult:
    """
    Patch the Jenkinsfile in the job's config XML to replace referenced_name
    with configured_name in the tools {} block, then reconfig the job.
    """
    if not referenced_name or not configured_name:
        return FixResult(
            success=False,
            fix_type="configure_tool",
            detail="Missing referenced_name or configured_name — cannot patch.",
        )
    try:
        server = _get_jenkins_server()
        config_xml = server.get_job_config(job_name)

        import re
        pattern = re.compile(
            r"((?:maven|jdk|gradle|nodejs|docker|git|ant)\s+['\"])" + re.escape(referenced_name) + r"(['\"])",
            re.IGNORECASE,
        )
        new_xml, count = pattern.subn(r"\g<1>" + configured_name + r"\g<2>", config_xml)

        if count == 0:
            return FixResult(
                success=False,
                fix_type="configure_tool",
                detail=f"Tool name '{referenced_name}' not found in job config XML.",
            )

        server.reconfig_job(job_name, new_xml)
        logger.info("configure_tool: patched %s: '%s' → '%s'", job_name, referenced_name, configured_name)
        return FixResult(
            success=True,
            fix_type="configure_tool",
            detail=f"Jenkinsfile updated: '{referenced_name}' → '{configured_name}'. Job re-configured.",
        )
    except jenkins.JenkinsException as e:
        logger.error("configure_tool failed for %s: %s", job_name, e)
        return FixResult(success=False, fix_type="configure_tool", detail=str(e))
    except Exception as e:
        return FixResult(success=False, fix_type="configure_tool", detail=f"Unexpected error: {e}")


def configure_credential(
    job_name: str,
    build_number: str = "0",
    credential_id: str = "",
) -> FixResult:
    """
    Create a placeholder username/password credential in Jenkins global store
    with the given credential_id so the Jenkinsfile reference resolves.
    Credentials are created empty — operator must update values in Jenkins UI.
    """
    if not credential_id:
        return FixResult(
            success=False,
            fix_type="configure_credential",
            detail="No credential_id provided.",
        )
    try:
        server = _get_jenkins_server()
        server.create_credential(
            "system::system::jenkins",
            {
                "": "0",
                "credentials": {
                    "scope": "GLOBAL",
                    "id": credential_id,
                    "username": "",
                    "password": "",
                    "description": f"Auto-created by DevOps AI Agent (job: {job_name}). Update credentials in Jenkins UI.",
                    "$class": "com.cloudbees.plugins.credentials.impl.UsernamePasswordCredentialsImpl",
                },
            },
        )
        logger.info("configure_credential: created '%s' for job %s", credential_id, job_name)
        return FixResult(
            success=True,
            fix_type="configure_credential",
            detail=f"Credential '{credential_id}' created in Jenkins (empty — update values in Jenkins UI).",
        )
    except jenkins.JenkinsException as e:
        logger.error("configure_credential failed for %s: %s", job_name, e)
        return FixResult(success=False, fix_type="configure_credential", detail=str(e))
    except Exception as e:
        return FixResult(success=False, fix_type="configure_credential", detail=f"Unexpected error: {e}")
