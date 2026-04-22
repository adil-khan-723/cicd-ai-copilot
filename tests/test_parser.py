from parser.log_extractor import extract_failed_logs
from parser.models import FailureContext


def test_extract_jenkins_stage_block_correct_pattern():
    """Extractor must use [Pipeline] { (Name) format, not [Pipeline] stage (Name)."""
    log = """[Pipeline] Start of Pipeline
[Pipeline] { (Checkout)
+ git clone https://github.com/foo/bar
[Pipeline] }
[Pipeline] { (Build)
+ mvn package
[Pipeline] }
[Pipeline] { (Test)
ERROR: Tests failed with exit code 1
[Pipeline] }
[Pipeline] End of Pipeline"""

    ctx = FailureContext(
        job_name="test-job",
        build_number=1,
        failed_stage="Test",
        platform="jenkins",
        raw_log=log,
    )
    result = extract_failed_logs(ctx)
    assert "Tests failed" in result
    assert "git clone" not in result
    assert "mvn package" not in result


def test_extract_jenkins_stage_no_duplicate_closing_brace():
    """Closing [Pipeline] } must not appear twice in extracted block."""
    log = "[Pipeline] { (Test)\nERROR: fail\n[Pipeline] }"
    ctx = FailureContext(job_name="j", build_number=1, failed_stage="Test",
                        platform="jenkins", raw_log=log)
    result = extract_failed_logs(ctx)
    assert result.count("[Pipeline] }") == 0  # closing brace is a boundary, not content


def test_extract_jenkins_stage_nested_same_name_no_reset():
    """Nested stage with same name as target must not reset the captured block."""
    log = (
        "[Pipeline] { (Build)\n"
        "+ mvn compile\n"
        "[Pipeline] { (Test)\n"         # outer target stage starts
        "Running outer test setup\n"
        "[Pipeline] { (Test)\n"         # inner stage same name — must NOT reset
        "ERROR: inner test failed\n"
        "[Pipeline] }\n"                # inner close
        "outer teardown\n"
        "[Pipeline] }\n"                # outer close
        "[Pipeline] { (Deploy)\n"
        "[Pipeline] }\n"
    )
    ctx = FailureContext(job_name="j", build_number=1, failed_stage="Test",
                        platform="jenkins", raw_log=log)
    result = extract_failed_logs(ctx)
    assert "outer test setup" in result
    assert "inner test failed" in result
    assert "outer teardown" in result
    assert "mvn compile" not in result  # Build stage excluded
    assert "Deploy" not in result


def test_extract_jenkins_stage_not_found_returns_tail():
    """When stage not found, return tail of full log."""
    log = "[Pipeline] { (Build)\n+ mvn package\n[Pipeline] }"
    ctx = FailureContext(job_name="j", build_number=1, failed_stage="NonExistent",
                        platform="jenkins", raw_log=log)
    result = extract_failed_logs(ctx)
    assert "mvn package" in result  # full tail returned
