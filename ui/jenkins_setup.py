"""
Auto-configure Jenkins for notification webhook delivery.

Why this exists: cloud Jenkins installs (init.groovy.d-style) skip the
"recommended" plugin set, leaving the Notification Plugin without its hard
runtime dep on `hudson.tasks.test.AbstractTestResultAction` (provided by
the junit plugin). Plugin then NoClassDefFoundError's silently inside
getTestResults() — webhook never fires.

This module:
  1. Ensures `notification` + `junit` plugins are installed
  2. Patches every existing job's config.xml to add a notification endpoint
     pointing at OUR webhook URL with event=all and branch=.* (the legacy
     plugin requires both fields populated to actually fire)
  3. Returns a report so the UI can surface what was changed and whether
     a Jenkins restart is needed (plugin install requires it).

Idempotent: re-running detects existing notification endpoint and skips.
"""
from __future__ import annotations
import logging
import re
import xml.etree.ElementTree as ET
from typing import Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

REQUIRED_PLUGINS = ("notification", "junit")
NOTIFICATION_PROPERTY_TAG = "com.tikal.hudson.plugins.notification.HudsonNotificationProperty"


@dataclass
class JenkinsSetupReport:
    plugins_installed: list[str] = field(default_factory=list)
    plugins_already_present: list[str] = field(default_factory=list)
    jobs_configured: list[str] = field(default_factory=list)
    jobs_already_configured: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    restart_required: bool = False  # True when we just installed plugins

    @property
    def ok(self) -> bool:
        return not self.errors


def configure_jenkins_for_webhooks(
    jenkins_url: str,
    user: str,
    token: str,
    webhook_url: str,
) -> JenkinsSetupReport:
    """
    Install required plugins + configure all existing jobs to POST to webhook_url.

    Args:
        webhook_url: e.g. http://1.2.3.4:8000/webhook/jenkins-notification
                     (the public URL Jenkins should call back to)
    """
    import requests
    report = JenkinsSetupReport()

    base = jenkins_url.rstrip("/")
    auth = (user, token)

    try:
        crumb = _get_crumb(base, auth)
    except Exception as e:
        report.errors.append(f"Could not obtain CSRF crumb from Jenkins: {e}")
        return report

    headers = {crumb["field"]: crumb["value"]} if crumb else {}
    cookies = crumb.get("cookies", {}) if crumb else {}

    # ── 1. Plugins ─────────────────────────────────────────────────────────
    try:
        installed = _list_installed_plugins(base, auth)
    except Exception as e:
        report.errors.append(f"Could not list plugins: {e}")
        return report

    for shortName in REQUIRED_PLUGINS:
        if shortName in installed:
            report.plugins_already_present.append(shortName)
            continue
        try:
            _install_plugin(base, auth, headers, cookies, shortName)
            report.plugins_installed.append(shortName)
            report.restart_required = True
        except Exception as e:
            report.errors.append(f"Could not install plugin '{shortName}': {e}")

    # If we just installed plugins, the rest of this can't take effect
    # until restart — caller decides whether to restart now.
    # We still patch job configs so post-restart they're ready.

    # ── 2. Configure jobs ──────────────────────────────────────────────────
    try:
        jobs = _list_jobs(base, auth)
    except Exception as e:
        report.errors.append(f"Could not list jobs: {e}")
        return report

    for job_name in jobs:
        try:
            patched = _patch_job_for_notification(
                base, auth, headers, cookies, job_name, webhook_url,
            )
            if patched:
                report.jobs_configured.append(job_name)
            else:
                report.jobs_already_configured.append(job_name)
        except Exception as e:
            report.errors.append(f"Could not configure job '{job_name}': {e}")

    logger.info(
        "Jenkins setup complete: plugins_installed=%s jobs_configured=%s errors=%d restart_required=%s",
        report.plugins_installed, report.jobs_configured, len(report.errors), report.restart_required,
    )
    return report


def _get_crumb(base: str, auth: tuple) -> Optional[dict]:
    """Return {field, value, cookies} or None if Jenkins has no CSRF protection."""
    import requests
    sess = requests.Session()
    r = sess.get(f"{base}/crumbIssuer/api/json", auth=auth, timeout=8)
    if r.status_code == 404:
        return None  # CSRF disabled
    r.raise_for_status()
    j = r.json()
    return {
        "field": j["crumbRequestField"],
        "value": j["crumb"],
        "cookies": dict(sess.cookies),
    }


def _list_installed_plugins(base: str, auth: tuple) -> set[str]:
    import requests
    r = requests.get(
        f"{base}/pluginManager/api/json",
        auth=auth,
        params={"depth": "1", "tree": "plugins[shortName,active]"},
        timeout=10,
    )
    r.raise_for_status()
    return {p["shortName"] for p in r.json().get("plugins", []) if p.get("active")}


def _install_plugin(base: str, auth: tuple, headers: dict, cookies: dict, shortName: str) -> None:
    """Install via Jenkins script console (avoids restart-required for Update Center XML route)."""
    import requests
    script = (
        f'def uc = jenkins.model.Jenkins.instance.updateCenter; '
        f'uc.updateAllSites(); '
        f'def plugin = uc.getPlugin("{shortName}"); '
        f'if (!plugin) throw new Exception("Plugin {shortName} not found in update center"); '
        f'plugin.deploy(true).get(); '
        f'println("installed: {shortName}")'
    )
    r = requests.post(
        f"{base}/scriptText",
        auth=auth,
        headers=headers,
        cookies=cookies,
        data={"script": script},
        timeout=120,  # plugin downloads can take time
    )
    r.raise_for_status()
    body = r.text.strip()
    if "installed:" not in body:
        raise RuntimeError(f"Install script returned: {body[:300]}")


def _list_jobs(base: str, auth: tuple) -> list[str]:
    import requests
    r = requests.get(
        f"{base}/api/json",
        auth=auth,
        params={"tree": "jobs[name]"},
        timeout=10,
    )
    r.raise_for_status()
    return [j["name"] for j in r.json().get("jobs", []) if j.get("name")]


def _patch_job_for_notification(
    base: str,
    auth: tuple,
    headers: dict,
    cookies: dict,
    job_name: str,
    webhook_url: str,
) -> bool:
    """
    Add a notification endpoint to the job's config.xml.
    Returns True if patched, False if already present.
    Idempotent: detects existing endpoint with same URL.
    """
    import requests
    # GET current config
    r = requests.get(f"{base}/job/{job_name}/config.xml", auth=auth, timeout=10)
    r.raise_for_status()
    config_xml = r.text

    # Already configured? Check for our exact webhook URL
    if webhook_url in config_xml and NOTIFICATION_PROPERTY_TAG in config_xml:
        return False

    new_xml = _inject_notification_property(config_xml, webhook_url)
    if new_xml == config_xml:
        # No change made (couldn't find <properties/> to patch into)
        raise RuntimeError("Could not locate <properties> in job config.xml")

    push_headers = dict(headers)
    push_headers["Content-Type"] = "application/xml"
    r2 = requests.post(
        f"{base}/job/{job_name}/config.xml",
        auth=auth,
        headers=push_headers,
        cookies=cookies,
        data=new_xml.encode("utf-8"),
        timeout=15,
    )
    r2.raise_for_status()
    return True


def _inject_notification_property(config_xml: str, webhook_url: str) -> str:
    """
    Add HudsonNotificationProperty into <properties>. Handles both empty
    <properties/> and existing <properties>...</properties> blocks.
    Removes any pre-existing notification property first to avoid duplicates.
    """
    # Strip any existing notification property block (idempotent re-runs)
    config_xml = re.sub(
        rf"<{re.escape(NOTIFICATION_PROPERTY_TAG)}.*?</{re.escape(NOTIFICATION_PROPERTY_TAG)}>",
        "",
        config_xml,
        flags=re.DOTALL,
    )

    notification_block = (
        f'    <{NOTIFICATION_PROPERTY_TAG} plugin="notification">\n'
        f'      <endpoints>\n'
        f'        <com.tikal.hudson.plugins.notification.Endpoint>\n'
        f'          <protocol>HTTP</protocol>\n'
        f'          <format>JSON</format>\n'
        f'          <url>{webhook_url}</url>\n'
        f'          <urlInfo>\n'
        f'            <urlOrId>{webhook_url}</urlOrId>\n'
        f'            <urlType>PUBLIC</urlType>\n'
        f'          </urlInfo>\n'
        f'          <event>all</event>\n'
        f'          <timeout>30000</timeout>\n'
        f'          <loglines>0</loglines>\n'
        f'          <retries>0</retries>\n'
        f'          <branch>.*</branch>\n'
        f'        </com.tikal.hudson.plugins.notification.Endpoint>\n'
        f'      </endpoints>\n'
        f'    </{NOTIFICATION_PROPERTY_TAG}>\n'
    )

    # Case 1: <properties/> self-closing — replace with open/close + content
    if "<properties/>" in config_xml:
        return config_xml.replace(
            "<properties/>",
            f"<properties>\n{notification_block}  </properties>",
            1,
        )

    # Case 2: <properties>...</properties> — inject before </properties>
    if "<properties>" in config_xml and "</properties>" in config_xml:
        return config_xml.replace(
            "</properties>",
            f"{notification_block}  </properties>",
            1,
        )

    return config_xml  # unchanged — caller raises
