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
