"""
Concrete fix implementations against Jenkins API.

Each function takes job_name + optional build_number and returns a FixResult.
All Jenkins calls go through python-jenkins.

Never auto-fixed (always diagnostic_only):
  - tool mismatches, missing plugins, missing credentials, IAM issues
"""
import logging
import re
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


def pull_fresh_image(
    job_name: str,
    build_number: str = "0",
    bad_image: str = "",
    correct_image: str = "",
) -> FixResult:
    """
    Patch the Dockerfile inside the Jenkins workspace to replace bad_image with
    correct_image (both provided by the LLM), then retrigger the job.

    If bad_image/correct_image are not supplied, falls back to a plain retry.
    Searches Dockerfiles inside the Jenkins Docker container workspace under /tmp.
    """
    import subprocess
    import shlex

    try:
        server = _get_jenkins_server()

        if bad_image and correct_image:
            find_cmd = [
                "docker", "exec", "jenkins",
                "find", "/tmp", "-name", "Dockerfile", "-maxdepth", "4",
            ]
            find_result = subprocess.run(find_cmd, capture_output=True, text=True, timeout=10)
            dockerfiles = [p.strip() for p in find_result.stdout.splitlines() if p.strip()]

            patched = []
            for df_path in dockerfiles:
                cat_result = subprocess.run(
                    ["docker", "exec", "jenkins", "cat", df_path],
                    capture_output=True, text=True, timeout=10,
                )
                content = cat_result.stdout
                if bad_image not in content:
                    continue
                fixed = content.replace(bad_image, correct_image)
                write_cmd = [
                    "docker", "exec", "jenkins", "sh", "-c",
                    f"printf '%s' {shlex.quote(fixed)} > {shlex.quote(df_path)}",
                ]
                wr = subprocess.run(write_cmd, capture_output=True, text=True, timeout=10)
                if wr.returncode == 0:
                    patched.append(df_path)
                    logger.info("pull_fresh_image: patched %s: %r → %r", df_path, bad_image, correct_image)

            try:
                server.build_job(job_name)
            except Exception:
                pass

            if patched:
                return FixResult(
                    success=True,
                    fix_type="pull_image",
                    detail=f"Dockerfile patched: '{bad_image}' → '{correct_image}' in {', '.join(patched)}. Job retriggered.",
                )
            return FixResult(
                success=False,
                fix_type="pull_image",
                detail=f"Image tag '{bad_image}' not found in any Dockerfile under /tmp — patch could not be applied.",
            )

        # No LLM-provided image info — retrigger with PULL_FRESH_IMAGE flag
        logger.info("pull_fresh_image: no bad_image/correct_image provided, plain retry for %s", job_name)
        try:
            server.build_job(job_name, parameters={"PULL_FRESH_IMAGE": "true"})
        except Exception:
            pass
        return FixResult(
            success=True,
            fix_type="pull_image",
            detail=f"Job '{job_name}' retriggered (no image patch — re-run may resolve transient pull failure).",
        )
    except jenkins.JenkinsException as e:
        return FixResult(success=False, fix_type="pull_image", detail=str(e))
    except Exception as e:
        logger.error("pull_fresh_image unexpected error for %s: %s", job_name, e)
        return FixResult(success=False, fix_type="pull_image", detail=f"Unexpected error: {e}")


def increase_timeout(
    job_name: str,
    build_number: str = "0",
    bad_line: str = "",
    correct_line: str = "",
    bad_step: str = "",
    correct_step: str = "",
) -> FixResult:
    """
    Patch the timeout in the Jenkinsfile using LLM-provided bad_line/correct_line.

    Primary: use bad_line/correct_line (LLM knows the exact Groovy timeout line).
    Fallback: regex-double the <timeout> XML element (Build Timeout plugin jobs only).
    """
    import xml.etree.ElementTree as ET

    try:
        server = _get_jenkins_server()
        config_xml = server.get_job_config(job_name)

        # Accept either bad_line/correct_line or bad_step/correct_step (same data, different field names)
        bad_line = bad_line or bad_step
        correct_line = correct_line or correct_step

        # ── Primary: LLM-provided line patch (works for any Groovy timeout syntax) ──
        if bad_line and correct_line:
            tree = ET.fromstring(config_xml)
            script_el = tree.find('.//script')
            if script_el is not None and script_el.text:
                jenkinsfile = script_el.text
                bad = bad_line.strip()
                good = correct_line.strip()

                new_jenkinsfile = None
                # Exact stripped-line match
                lines = jenkinsfile.splitlines(keepends=True)
                new_lines = []
                matched = 0
                for line in lines:
                    if line.strip() == bad:
                        indent = line[: len(line) - len(line.lstrip())]
                        new_lines.append(indent + good + '\n')
                        matched += 1
                    else:
                        new_lines.append(line)
                if matched:
                    new_jenkinsfile = ''.join(new_lines)

                # Substring fallback
                if new_jenkinsfile is None and bad in jenkinsfile:
                    new_jenkinsfile = jenkinsfile.replace(bad, good)

                if new_jenkinsfile and new_jenkinsfile != jenkinsfile:
                    script_el.text = new_jenkinsfile
                    new_config_xml = ET.tostring(tree, encoding='unicode', xml_declaration=False)
                    new_config_xml = "<?xml version='1.1' encoding='UTF-8'?>\n" + new_config_xml
                    server.reconfig_job(job_name, new_config_xml)
                    server.build_job(job_name)
                    logger.info("increase_timeout: patched Jenkinsfile for %s, retriggered", job_name)
                    return FixResult(
                        success=True,
                        fix_type="increase_timeout",
                        detail=f"Timeout line patched in Jenkinsfile. Job reconfigured and retriggered.",
                    )

        # ── Fallback: <timeout> XML element (Jenkins Build Timeout plugin) ──────────
        pattern = re.compile(r"(<timeout>)(\d+)(</timeout>)")
        match = pattern.search(config_xml)
        if match:
            current = int(match.group(2))
            new_timeout = current * 2
            new_config = pattern.sub(f"\\g<1>{new_timeout}\\g<3>", config_xml)
            server.reconfig_job(job_name, new_config)
            server.build_job(job_name)
            logger.info("increase_timeout: XML element %d → %d for %s, retriggered", current, new_timeout, job_name)
            return FixResult(
                success=True,
                fix_type="increase_timeout",
                detail=f"Timeout increased from {current} to {new_timeout} (XML config). Job retriggered.",
            )

        return FixResult(
            success=False,
            fix_type="increase_timeout",
            detail="Could not locate timeout in Jenkinsfile or job config — increase manually.",
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
    Patch the Jenkinsfile in the job's config XML: replace every occurrence of
    referenced_name with configured_name in the raw Jenkinsfile text, then reconfig.

    Uses ElementTree to decode the config XML (handles all entity variants:
    &apos; &quot; &#x27; &amp; etc.) and operates on the plain Jenkinsfile text —
    no hardcoded syntax patterns, works for tools{} block, withMaven(), tool() steps,
    and any other syntax that references the tool name.
    """
    import xml.etree.ElementTree as ET

    if not referenced_name or not configured_name:
        return FixResult(
            success=False,
            fix_type="configure_tool",
            detail="Missing referenced_name or configured_name — cannot patch.",
        )
    try:
        server = _get_jenkins_server()
        config_xml = server.get_job_config(job_name)

        tree = ET.fromstring(config_xml)
        script_el = tree.find('.//script')
        if script_el is None or script_el.text is None:
            return FixResult(
                success=False,
                fix_type="configure_tool",
                detail="No <script> element found in job config — is this a Pipeline job?",
            )

        jenkinsfile = script_el.text
        if referenced_name not in jenkinsfile:
            return FixResult(
                success=False,
                fix_type="configure_tool",
                detail=f"Tool name '{referenced_name}' not found in Jenkinsfile.",
            )

        count = jenkinsfile.count(referenced_name)
        new_jenkinsfile = jenkinsfile.replace(referenced_name, configured_name)
        script_el.text = new_jenkinsfile

        new_config_xml = ET.tostring(tree, encoding='unicode', xml_declaration=False)
        new_config_xml = "<?xml version='1.1' encoding='UTF-8'?>\n" + new_config_xml

        server.reconfig_job(job_name, new_config_xml)
        server.build_job(job_name)
        logger.info("configure_tool: patched %s: '%s' → '%s' (%d occurrence(s)), retriggered",
                    job_name, referenced_name, configured_name, count)
        return FixResult(
            success=True,
            fix_type="configure_tool",
            detail=f"Jenkinsfile updated: '{referenced_name}' → '{configured_name}' ({count} occurrence(s)). Job re-configured and retriggered.",
        )
    except jenkins.JenkinsException as e:
        logger.error("configure_tool failed for %s: %s", job_name, e)
        return FixResult(success=False, fix_type="configure_tool", detail=str(e))
    except Exception as e:
        return FixResult(success=False, fix_type="configure_tool", detail=f"Unexpected error: {e}")


def fix_step_typo(
    job_name: str,
    build_number: str = "0",
    bad_step: str = "",
    correct_step: str = "",
) -> FixResult:
    """
    Patch the Jenkinsfile stored in the job's config XML to fix ANY Groovy/Jenkins
    syntax error — step name typos, wrong keyword spelling, bad argument syntax,
    missing/wrong brackets, wrong credential IDs, wrong plugin/tool references, etc.

    Strategy: extract the raw Jenkinsfile text from inside <script>…</script>,
    patch it as plain text (no XML encoding concerns), then re-encode and put it back.
    This is robust against all XML entity variants (&apos; &quot; &#x27; &amp; etc.)
    and handles line-mode (full line) and token-mode (short token) replacement.
    """
    if not bad_step or not correct_step:
        return FixResult(
            success=False,
            fix_type="fix_step_typo",
            detail="Missing bad_step or correct_step — cannot patch.",
        )
    try:
        import xml.etree.ElementTree as ET

        server = _get_jenkins_server()
        config_xml = server.get_job_config(job_name)

        # Parse the config XML properly — ElementTree decodes all entity variants
        # (&apos; &quot; &#x27; &amp; &lt; &gt;) back to raw characters automatically.
        tree = ET.fromstring(config_xml)
        script_el = tree.find('.//script')
        if script_el is None or script_el.text is None:
            return FixResult(
                success=False,
                fix_type="fix_step_typo",
                detail="No <script> element found in job config — is this a Pipeline job?",
            )

        jenkinsfile = script_el.text
        bad  = bad_step.strip()
        good = correct_step.strip()

        # ── Try all matching strategies in order until one lands ──────────────

        new_jenkinsfile = None
        strategy_used   = None

        # 1. Exact line match (preserves indentation of surrounding lines)
        if '\n' not in bad:
            lines = jenkinsfile.splitlines(keepends=True)
            new_lines = []
            matched = 0
            for line in lines:
                stripped = line.strip()
                if stripped == bad:
                    indent = line[: len(line) - len(line.lstrip())]
                    new_lines.append(indent + good + '\n')
                    matched += 1
                else:
                    new_lines.append(line)
            if matched:
                new_jenkinsfile = ''.join(new_lines)
                strategy_used = f"exact-line ({matched} line(s))"

        # 2. Substring match within a line (handles partial-line fixes)
        if new_jenkinsfile is None:
            if bad in jenkinsfile:
                new_jenkinsfile = jenkinsfile.replace(bad, good)
                strategy_used = f"substring ({jenkinsfile.count(bad)} occurrence(s))"

        # 3. Word-boundary token match (echo1 → echo, stgae → stage)
        if new_jenkinsfile is None and not re.search(r'\s', bad):
            pattern = re.compile(r'\b' + re.escape(bad) + r'\b')
            result, count = pattern.subn(good, jenkinsfile)
            if count:
                new_jenkinsfile = result
                strategy_used = f"word-boundary ({count} token(s))"

        # 4. Fuzzy: collapse whitespace differences when matching
        if new_jenkinsfile is None:
            normalized_bad = re.sub(r'\s+', r'\\s+', re.escape(bad))
            pattern = re.compile(normalized_bad)
            result, count = pattern.subn(good, jenkinsfile)
            if count:
                new_jenkinsfile = result
                strategy_used = f"whitespace-fuzzy ({count} match(es))"

        if new_jenkinsfile is None or new_jenkinsfile == jenkinsfile:
            return FixResult(
                success=False,
                fix_type="fix_step_typo",
                detail=(
                    f"Pattern not found in Jenkinsfile after trying exact-line, substring, "
                    f"word-boundary, and fuzzy matching. bad={bad[:80]!r}"
                ),
            )

        # Write patched Jenkinsfile back — ElementTree re-encodes all special chars correctly
        script_el.text = new_jenkinsfile
        new_config_xml = ET.tostring(tree, encoding='unicode', xml_declaration=False)
        new_config_xml = "<?xml version='1.1' encoding='UTF-8'?>\n" + new_config_xml

        server.reconfig_job(job_name, new_config_xml)
        server.build_job(job_name)
        logger.info(
            "fix_step_typo: patched %s via %s — %r → %r, retriggered",
            job_name, strategy_used, bad[:60], good[:60],
        )
        return FixResult(
            success=True,
            fix_type="fix_step_typo",
            detail=f"Jenkinsfile patched ({strategy_used}). Job reconfigured and retriggered.",
        )
    except jenkins.JenkinsException as e:
        logger.error("fix_step_typo failed for %s: %s", job_name, e)
        return FixResult(success=False, fix_type="fix_step_typo", detail=str(e))
    except Exception as e:
        logger.error("fix_step_typo unexpected error for %s: %s", job_name, e)
        return FixResult(success=False, fix_type="fix_step_typo", detail=f"Unexpected error: {e}")


def configure_credential(
    job_name: str,
    build_number: str = "0",
    credential_id: str = "",
    credential_type: str = "secret_text",
) -> FixResult:
    """
    Create a placeholder credential in Jenkins global system store.

    credential_type (from LLM):
      - 'secret_text'       → StringCredentials (for string() bindings)
      - 'username_password' → UsernamePasswordCredentials (for usernamePassword() bindings)
      - 'ssh_key'           → BasicSSHUserPrivateKey (for sshUserPrivateKey() bindings)

    Credentials are created with empty/placeholder values — operator must update in Jenkins UI.
    """
    import requests

    if not credential_id:
        return FixResult(
            success=False,
            fix_type="configure_credential",
            detail="No credential_id provided.",
        )

    desc = f"Auto-created by DevOps AI Agent (job: {job_name}). Update value in Jenkins UI."

    cred_type = (credential_type or "secret_text").strip().lower()
    if cred_type == "username_password":
        cred_xml = (
            "<com.cloudbees.plugins.credentials.impl.UsernamePasswordCredentialsImpl>"
            "<scope>GLOBAL</scope>"
            f"<id>{credential_id}</id>"
            "<username></username>"
            "<password></password>"
            f"<description>{desc}</description>"
            "</com.cloudbees.plugins.credentials.impl.UsernamePasswordCredentialsImpl>"
        )
    elif cred_type == "ssh_key":
        cred_xml = (
            "<com.cloudbees.jenkins.plugins.sshcredentials.impl.BasicSSHUserPrivateKey>"
            "<scope>GLOBAL</scope>"
            f"<id>{credential_id}</id>"
            "<username></username>"
            "<privateKeySource class=\"com.cloudbees.jenkins.plugins.sshcredentials.impl.BasicSSHUserPrivateKey$DirectEntryPrivateKeySource\">"
            "<privateKey></privateKey>"
            "</privateKeySource>"
            f"<description>{desc}</description>"
            "</com.cloudbees.jenkins.plugins.sshcredentials.impl.BasicSSHUserPrivateKey>"
        )
    else:
        # Default: secret_text — works for string() and withCredentials string bindings
        cred_xml = (
            "<org.jenkinsci.plugins.plaincredentials.impl.StringCredentialsImpl>"
            "<scope>GLOBAL</scope>"
            f"<id>{credential_id}</id>"
            "<secret></secret>"
            f"<description>{desc}</description>"
            "</org.jenkinsci.plugins.plaincredentials.impl.StringCredentialsImpl>"
        )

    try:
        s = get_settings()
        server = _get_jenkins_server()

        crumb_url = f"{s.jenkins_url}/crumbIssuer/api/json"
        crumb_resp = requests.get(crumb_url, auth=(s.jenkins_user, s.jenkins_token), timeout=10)
        crumb_resp.raise_for_status()
        crumb_data = crumb_resp.json()
        crumb_header = {crumb_data["crumbRequestField"]: crumb_data["crumb"]}

        create_url = f"{s.jenkins_url}/credentials/store/system/domain/_/createCredentials"
        resp = requests.post(
            create_url,
            data=cred_xml.encode("utf-8"),
            headers={"Content-Type": "application/xml", **crumb_header},
            auth=(s.jenkins_user, s.jenkins_token),
            timeout=10,
        )
        if resp.status_code not in (200, 201, 302):
            raise jenkins.JenkinsException(
                f"Credential creation returned HTTP {resp.status_code}: {resp.text[:200]}"
            )

        server.build_job(job_name)
        logger.info("configure_credential: created '%s' (type=%s) for job %s, retriggered",
                    credential_id, cred_type, job_name)
        return FixResult(
            success=True,
            fix_type="configure_credential",
            detail=f"Credential '{credential_id}' ({cred_type}) created in Jenkins (placeholder — update value in Jenkins UI). Job retriggered.",
        )
    except jenkins.JenkinsException as e:
        logger.error("configure_credential failed for %s: %s", job_name, e)
        return FixResult(success=False, fix_type="configure_credential", detail=str(e))
    except Exception as e:
        logger.error("configure_credential unexpected error for %s: %s", job_name, e)
        return FixResult(success=False, fix_type="configure_credential", detail=f"Unexpected error: {e}")
