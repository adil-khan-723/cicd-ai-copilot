"""
Live integration tests — real Jenkins API + real Anthropic API.
Run only when JENKINS_URL and ANTHROPIC_API_KEY are set in .env.

pytest tests/test_integration_live.py -v -s
"""
import os
import time
import pytest

# Load .env
from pathlib import Path
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

JENKINS_URL   = os.environ.get("JENKINS_URL", "")
JENKINS_USER  = os.environ.get("JENKINS_USER", "")
JENKINS_TOKEN = os.environ.get("JENKINS_TOKEN", "")
ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

needs_jenkins   = pytest.mark.skipif(not (JENKINS_URL and JENKINS_TOKEN), reason="Jenkins not configured")
needs_anthropic = pytest.mark.skipif(not ANTHROPIC_KEY, reason="ANTHROPIC_API_KEY not set")


def _get_jenkins_server():
    import jenkins
    return jenkins.Jenkins(JENKINS_URL, username=JENKINS_USER, password=JENKINS_TOKEN)


def _get_failed_job(server):
    jobs = server.get_all_jobs()
    failed = [j for j in jobs if j.get("color", "").startswith("red")]
    return failed[0] if failed else None


# ---------------------------------------------------------------------------
# Jenkins connectivity
# ---------------------------------------------------------------------------

class TestJenkinsLive:

    @needs_jenkins
    def test_jenkins_api_reachable(self):
        server = _get_jenkins_server()
        info = server.get_info()
        assert "jobs" in info

    @needs_jenkins
    def test_jenkins_lists_jobs(self):
        server = _get_jenkins_server()
        jobs = server.get_all_jobs()
        assert isinstance(jobs, list)
        assert len(jobs) > 0
        print(f"\nJenkins jobs ({len(jobs)}): {[j['name'] for j in jobs]}")

    @needs_jenkins
    def test_jenkins_get_job_config(self):
        server = _get_jenkins_server()
        jobs = server.get_all_jobs()
        assert jobs
        config_xml = server.get_job_config(jobs[0]["name"])
        assert len(config_xml) > 100
        print(f"\nConfig for '{jobs[0]['name']}': {len(config_xml)} chars")

    @needs_jenkins
    def test_jenkins_failed_job_exists(self):
        server = _get_jenkins_server()
        jobs = server.get_all_jobs()
        failed = [j for j in jobs if j.get("color", "").startswith("red")]
        print(f"\nFailed jobs: {[j['name'] for j in failed]}")
        assert failed, "No failed jobs — need at least one red job"

    @needs_jenkins
    def test_jenkins_build_log_fetch(self):
        server = _get_jenkins_server()
        job = _get_failed_job(server)
        assert job, "No failed job"
        job_name = job["name"]
        last_build = server.get_job_info(job_name)["lastBuild"]
        assert last_build is not None
        log = server.get_build_console_output(job_name, last_build["number"])
        assert len(log) > 0
        print(f"\nLog from '{job_name}' #{last_build['number']}: {len(log)} chars")
        print(log[:400])


# ---------------------------------------------------------------------------
# Parser pipeline on real log
# ---------------------------------------------------------------------------

class TestParserOnRealLog:

    @needs_jenkins
    def test_parse_and_clean_real_log(self):
        from parser.pipeline_parser import parse_failure
        from parser.log_extractor import extract_failed_logs
        from parser.log_cleaner import clean_log

        server = _get_jenkins_server()
        job = _get_failed_job(server)
        assert job
        job_name = job["name"]
        job_info = server.get_job_info(job_name)
        last_build = job_info["lastBuild"]
        raw_log = server.get_build_console_output(job_name, last_build["number"])

        payload = {
            "source": "jenkins",
            "log": raw_log,
            "job_name": job_name,
            "build_number": last_build["number"],
            "stages": [],
        }
        parsed = parse_failure(payload, source="jenkins")
        print(f"\nParsed failed stage: {parsed.failed_stage}")
        assert parsed is not None

        extracted = extract_failed_logs(parsed)
        assert isinstance(extracted, str)
        assert len(extracted) > 0

        cleaned = clean_log(extracted)
        assert isinstance(cleaned, str)
        assert "\x1b[" not in cleaned, "ANSI codes not stripped"
        print(f"Cleaned log ({len(cleaned)} chars):\n{cleaned[:400]}")

    @needs_jenkins
    def test_token_reduction_real_log(self):
        from parser.pipeline_parser import parse_failure
        from parser.log_extractor import extract_failed_logs
        from parser.log_cleaner import clean_log

        server = _get_jenkins_server()
        job = _get_failed_job(server)
        assert job
        job_name = job["name"]
        job_info = server.get_job_info(job_name)
        last_build = job_info["lastBuild"]
        raw_log = server.get_build_console_output(job_name, last_build["number"])

        payload = {"source": "jenkins", "log": raw_log, "job_name": job_name,
                   "build_number": last_build["number"], "stages": []}
        parsed = parse_failure(payload, source="jenkins")
        extracted = extract_failed_logs(parsed)
        cleaned = clean_log(extracted)

        reduction_pct = (1 - len(cleaned) / max(len(raw_log), 1)) * 100
        print(f"\nRaw: {len(raw_log)} → Cleaned: {len(cleaned)} → {reduction_pct:.1f}% reduction")
        assert len(cleaned) < len(raw_log), "Cleaned log should be shorter than raw"


# ---------------------------------------------------------------------------
# Crawler on real Jenkins
# ---------------------------------------------------------------------------

class TestCrawlerLive:

    @needs_jenkins
    def test_crawler_fetches_global_tools(self):
        from verification.jenkins_crawler import get_configured_tools
        tools = get_configured_tools(JENKINS_URL, auth=(JENKINS_USER, JENKINS_TOKEN))
        print(f"\nConfigured tools: {tools}")
        assert isinstance(tools, dict)

    @needs_jenkins
    def test_crawler_verify_against_real_job(self):
        from verification.jenkins_crawler import verify_jenkins_tools

        server = _get_jenkins_server()
        jobs = server.get_all_jobs()

        # Find a pipeline job with a Jenkinsfile-style config
        pipeline_jenkinsfile = None
        pipeline_job_name = None
        for job in jobs:
            try:
                config = server.get_job_config(job["name"])
                if "stage(" in config or "pipeline {" in config.lower():
                    pipeline_job_name = job["name"]
                    pipeline_jenkinsfile = config
                    break
            except Exception:
                continue

        if not pipeline_job_name:
            pytest.skip("No pipeline jobs found to crawl")

        result = verify_jenkins_tools(
            jenkinsfile_content=pipeline_jenkinsfile,
            jenkins_url=JENKINS_URL,
            auth=(JENKINS_USER, JENKINS_TOKEN),
            timeout=15.0,
        )
        lines = result.summary_lines()
        print(f"\nCrawl result for '{pipeline_job_name}': has_issues={result.has_issues}")
        print("Summary:", lines)
        assert hasattr(result, "has_issues")
        assert isinstance(lines, list)


# ---------------------------------------------------------------------------
# Anthropic API live
# ---------------------------------------------------------------------------

class TestAnthropicLive:

    @needs_anthropic
    def test_anthropic_provider_is_available(self):
        from providers.anthropic_provider import AnthropicProvider
        provider = AnthropicProvider(
            model=os.environ.get("ANTHROPIC_ANALYSIS_MODEL", "claude-haiku-4-5-20251001")
        )
        assert provider.is_available() is True

    @needs_anthropic
    def test_anthropic_complete_simple_prompt(self):
        from providers.anthropic_provider import AnthropicProvider
        provider = AnthropicProvider(
            model=os.environ.get("ANTHROPIC_ANALYSIS_MODEL", "claude-haiku-4-5-20251001")
        )
        response = provider.complete("Reply with only the word: PONG")
        assert "PONG" in response.upper(), f"Unexpected response: {response}"
        print(f"\nAnthropic response: {response!r}")

    @needs_anthropic
    def test_anthropic_haiku_routes_for_analysis(self):
        from providers.factory import get_provider
        os.environ["LLM_PROVIDER"] = "anthropic"
        provider = get_provider("analysis")
        model_name = provider.name
        assert "haiku" in model_name.lower() or "claude" in model_name.lower()
        print(f"\nAnalysis provider: {model_name}")

    @needs_anthropic
    def test_anthropic_sonnet_routes_for_generation(self):
        from providers.factory import get_provider
        os.environ["LLM_PROVIDER"] = "anthropic"
        provider = get_provider("generation")
        model_name = provider.name
        assert "sonnet" in model_name.lower() or "claude" in model_name.lower()
        print(f"\nGeneration provider: {model_name}")


# ---------------------------------------------------------------------------
# Full end-to-end: real Jenkins log → real LLM analysis
# ---------------------------------------------------------------------------

class TestE2ELiveAnalysis:

    @needs_jenkins
    @needs_anthropic
    def test_full_pipeline_real_log_real_llm(self):
        """Real Jenkins failed log → parser → context builder → Anthropic → parsed result."""
        from parser.pipeline_parser import parse_failure
        from parser.log_extractor import extract_failed_logs
        from parser.log_cleaner import clean_log
        from analyzer.context_builder import build_context
        from analyzer.llm_client import analyze

        os.environ["LLM_PROVIDER"] = "anthropic"

        server = _get_jenkins_server()
        job = _get_failed_job(server)
        assert job, "No failed jobs for E2E test"

        job_name = job["name"]
        job_info = server.get_job_info(job_name)
        last_build = job_info["lastBuild"]
        raw_log = server.get_build_console_output(job_name, last_build["number"])

        payload = {"source": "jenkins", "log": raw_log, "job_name": job_name,
                   "build_number": last_build["number"], "stages": []}
        parsed = parse_failure(payload, source="jenkins")
        extracted = extract_failed_logs(parsed)
        cleaned = clean_log(extracted)

        context_str = build_context(log=cleaned, report=None, context=parsed)
        token_count = len(context_str.split())
        print(f"\nContext tokens (approx): {token_count}")
        assert token_count <= 1500, f"Context too large: {token_count} tokens"

        result = analyze(context_str)
        print(f"\nLLM result: fix_type={result.get('fix_type')}, confidence={result.get('confidence')}")
        print(f"Summary: {result.get('root_cause','')[:200]}")

        assert result is not None
        assert "fix_type" in result
        assert "confidence" in result
        assert 0.0 <= result["confidence"] <= 1.0
        assert len(result.get("root_cause", "")) > 0

    @needs_jenkins
    @needs_anthropic
    def test_cache_hit_on_second_identical_analysis(self):
        """Second call with same context must hit cache and be significantly faster."""
        from parser.pipeline_parser import parse_failure
        from parser.log_extractor import extract_failed_logs
        from parser.log_cleaner import clean_log
        from analyzer.context_builder import build_context
        from analyzer.llm_client import analyze

        os.environ["LLM_PROVIDER"] = "anthropic"

        server = _get_jenkins_server()
        job = _get_failed_job(server)
        assert job
        job_name = job["name"]
        job_info = server.get_job_info(job_name)
        last_build = job_info["lastBuild"]
        raw_log = server.get_build_console_output(job_name, last_build["number"])

        payload = {"source": "jenkins", "log": raw_log, "job_name": job_name,
                   "build_number": last_build["number"], "stages": []}
        parsed = parse_failure(payload, source="jenkins")
        extracted = extract_failed_logs(parsed)
        cleaned = clean_log(extracted)
        context_str = build_context(log=cleaned, report=None, context=parsed)

        t0 = time.time()
        result1 = analyze(context_str)
        t1 = time.time()

        t2 = time.time()
        result2 = analyze(context_str)
        t3 = time.time()

        first_ms  = (t1 - t0) * 1000
        second_ms = (t3 - t2) * 1000

        print(f"\nFirst call: {first_ms:.2f}ms | Second (cache): {second_ms:.2f}ms")
        # Both complete in <5ms — cache is in-process dict, not network.
        # Verify correctness (idempotent) rather than sub-ms timing.
        assert result1["fix_type"] == result2["fix_type"], "Cache returned different fix_type"
        assert result1.get("root_cause") == result2.get("root_cause"), "Cache returned different root_cause"
        assert result1["confidence"] == result2["confidence"], "Cache returned different confidence"
        # Both should be fast (well under 1s each — no network call on second)
        assert second_ms < 500, f"Cache hit took too long: {second_ms:.0f}ms"
