"""Tests for LLM Analyzer — response parser and cache (Increment 15)."""
import time
import pytest
from unittest.mock import patch, MagicMock

from analyzer.response_parser import parse_analysis_response
from analyzer import cache as analysis_cache
from analyzer.llm_client import analyze


class TestResponseParser:
    def test_parses_valid_json(self):
        raw = '{"root_cause": "Missing dep", "fix_suggestion": "Pin version", "confidence": 0.9, "fix_type": "clear_cache"}'
        result = parse_analysis_response(raw)
        assert result["root_cause"] == "Missing dep"
        assert result["confidence"] == 0.9
        assert result["fix_type"] == "clear_cache"

    def test_extracts_json_from_markdown_fence(self):
        raw = '```json\n{"root_cause": "Timeout", "fix_suggestion": "Retry", "confidence": 0.8, "fix_type": "retry"}\n```'
        result = parse_analysis_response(raw)
        assert result["fix_type"] == "retry"

    def test_extracts_bare_json_with_surrounding_text(self):
        raw = 'Here is my analysis: {"root_cause": "X", "fix_suggestion": "Y", "confidence": 0.75, "fix_type": "retry"} hope this helps'
        result = parse_analysis_response(raw)
        assert result["root_cause"] == "X"

    def test_invalid_json_returns_fallback(self):
        result = parse_analysis_response("this is not json at all")
        assert result["fix_type"] == "diagnostic_only"
        assert result["confidence"] == 0.0

    def test_empty_string_returns_fallback(self):
        result = parse_analysis_response("")
        assert result["fix_type"] == "diagnostic_only"

    def test_low_confidence_forces_diagnostic_only(self):
        raw = '{"root_cause": "X", "fix_suggestion": "Y", "confidence": 0.4, "fix_type": "retry"}'
        result = parse_analysis_response(raw)
        assert result["fix_type"] == "diagnostic_only"
        assert result["confidence"] == 0.4

    def test_confidence_at_boundary(self):
        # Exactly 0.6 should NOT be forced to diagnostic_only
        raw = '{"root_cause": "X", "fix_suggestion": "Y", "confidence": 0.6, "fix_type": "retry"}'
        result = parse_analysis_response(raw)
        assert result["fix_type"] == "retry"

    def test_unknown_fix_type_defaults(self):
        raw = '{"root_cause": "X", "fix_suggestion": "Y", "confidence": 0.85, "fix_type": "magic_fix"}'
        result = parse_analysis_response(raw)
        assert result["fix_type"] == "diagnostic_only"

    def test_confidence_clamped_to_range(self):
        raw = '{"root_cause": "X", "fix_suggestion": "Y", "confidence": 1.5, "fix_type": "retry"}'
        result = parse_analysis_response(raw)
        assert result["confidence"] == 1.0


class TestCache:
    def setup_method(self):
        analysis_cache.clear()

    def test_miss_returns_none(self):
        assert analysis_cache.get("context that was never set") is None

    def test_set_and_get(self):
        result = {"root_cause": "X", "fix_type": "retry", "confidence": 0.9, "fix_suggestion": "Y"}
        analysis_cache.set("my context", result)
        assert analysis_cache.get("my context") == result

    def test_different_contexts_different_keys(self):
        analysis_cache.set("ctx1", {"root_cause": "A"})
        analysis_cache.set("ctx2", {"root_cause": "B"})
        assert analysis_cache.get("ctx1")["root_cause"] == "A"
        assert analysis_cache.get("ctx2")["root_cause"] == "B"

    def test_expired_entry_returns_none(self):
        import analyzer.cache as mod
        result = {"root_cause": "X"}
        analysis_cache.set("ctx", result)
        # Manually expire the entry — _mem is now {profile_id: {key: entry}}
        key = analysis_cache.cache_key("ctx")
        pid = analysis_cache._profile_id()
        mod._mem[pid][key]["expires_at"] = time.time() - 1
        assert analysis_cache.get("ctx") is None

    def test_clear_empties_cache(self):
        analysis_cache.set("ctx", {"root_cause": "X"})
        analysis_cache.clear()
        assert analysis_cache.get("ctx") is None


class TestCacheRedisBackend:
    """Cache falls back to in-memory when Redis is unavailable."""

    def setup_method(self):
        analysis_cache.clear()

    def test_falls_back_to_memory_when_redis_unavailable(self):
        with patch("analyzer.cache._redis_client", None):
            analysis_cache.set("ctx", {"root_cause": "X"})
            result = analysis_cache.get("ctx")
        assert result is not None
        assert result["root_cause"] == "X"

    def test_uses_redis_when_available(self):
        mock_redis = MagicMock()
        mock_redis.get.return_value = None
        mock_redis.setex.return_value = True

        with patch("analyzer.cache._redis_client", mock_redis):
            analysis_cache.set("ctx", {"root_cause": "Y"})

        mock_redis.setex.assert_called_once()

    def test_redis_read_falls_back_to_memory_on_error(self):
        mock_redis = MagicMock()
        mock_redis.get.side_effect = Exception("Redis connection lost")

        with patch("analyzer.cache._redis_client", mock_redis):
            # pre-seed memory cache directly — _mem is {profile_id: {key: entry}}
            import time, hashlib
            key = hashlib.md5(b"ctx").hexdigest()
            pid = analysis_cache._profile_id()
            if pid not in analysis_cache._mem:
                analysis_cache._mem[pid] = {}
            analysis_cache._mem[pid][key] = {"result": {"root_cause": "Z"}, "expires_at": time.time() + 3600}
            result = analysis_cache.get("ctx")

        assert result["root_cause"] == "Z"


class TestAnalyze:
    def setup_method(self):
        analysis_cache.clear()

    def test_calls_provider_and_returns_parsed_result(self):
        mock_provider = MagicMock()
        mock_provider.name = "mock"
        mock_provider.complete.return_value = (
            '{"root_cause": "pip version conflict", "fix_suggestion": "Pin fastapi", '
            '"confidence": 0.88, "fix_type": "clear_cache"}'
        )

        with patch("analyzer.llm_client.get_provider", return_value=mock_provider):
            result = analyze("some context string")

        assert result["fix_type"] == "clear_cache"
        assert result["confidence"] == 0.88
        mock_provider.complete.assert_called_once()

    def test_caches_result_on_second_call(self):
        mock_provider = MagicMock()
        mock_provider.name = "mock"
        mock_provider.complete.return_value = (
            '{"root_cause": "X", "fix_suggestion": "Y", "confidence": 0.8, "fix_type": "retry"}'
        )

        with patch("analyzer.llm_client.get_provider", return_value=mock_provider):
            result1 = analyze("same context")
            result2 = analyze("same context")

        # Provider should only be called once — second call hits cache
        assert mock_provider.complete.call_count == 1
        assert result1 == result2

    def test_provider_exception_returns_fallback(self):
        mock_provider = MagicMock()
        mock_provider.name = "mock"
        mock_provider.complete.side_effect = RuntimeError("connection refused")

        with patch("analyzer.llm_client.get_provider", return_value=mock_provider):
            result = analyze("context")

        assert result["fix_type"] == "diagnostic_only"
        assert result["confidence"] == 0.0


class TestSystemPromptPotentialIssues:
    def test_system_prompt_includes_potential_issues_schema(self):
        from analyzer.prompt_builder import build_system_prompt
        prompt = build_system_prompt()
        assert "potential_issues" in prompt
        assert "syntax" in prompt
        assert "logic" in prompt
        assert "config" in prompt

    def test_system_prompt_has_concrete_exemplar(self):
        """Prompt must show a worked example so the LLM populates potential_issues correctly."""
        from analyzer.prompt_builder import build_system_prompt
        prompt = build_system_prompt()
        # Exemplar must show a populated potential_issues array (not just empty)
        assert "EXAMPLE" in prompt
        # Exemplar shows multiple entries
        assert prompt.count('"fix_type": "configure_credential"') >= 1
        assert prompt.count('"fix_type": "fix_step_typo"') >= 1

    def test_system_prompt_forbids_merging_into_root_cause(self):
        from analyzer.prompt_builder import build_system_prompt
        prompt = build_system_prompt()
        assert "root_cause" in prompt
        # Stronger directive — explicit "do not merge"
        lower = prompt.lower()
        assert "must go in potential_issues" in lower or "must populate" in lower or "do not mention secondary issues only in prose" in lower


class TestPotentialIssuesParsing:
    def test_parse_potential_issues_valid(self):
        raw = '''{
            "root_cause": "Missing credential",
            "fix_suggestion": "Create the credential",
            "steps": ["Create aws-prod in Jenkins"],
            "confidence": 0.9,
            "fix_type": "configure_credential",
            "potential_issues": [
                {
                    "type": "config",
                    "line": "maven 'Maven-3'",
                    "issue": "Tool name mismatch",
                    "fix_type": "configure_tool"
                },
                {
                    "type": "syntax",
                    "line": "sh 'mvn clen install'",
                    "issue": "Typo in maven goal",
                    "fix_type": "fix_step_typo"
                }
            ]
        }'''
        result = parse_analysis_response(raw)
        assert "potential_issues" in result
        assert len(result["potential_issues"]) == 2
        assert result["potential_issues"][0]["type"] == "config"
        assert result["potential_issues"][1]["fix_type"] == "fix_step_typo"

    def test_parse_potential_issues_missing_key_returns_empty(self):
        raw = '{"root_cause": "Some error", "fix_suggestion": "Fix it", "steps": [], "confidence": 0.8, "fix_type": "retry"}'
        result = parse_analysis_response(raw)
        assert result["potential_issues"] == []

    def test_parse_potential_issues_malformed_entry_skipped(self):
        raw = '''{
            "root_cause": "Some error",
            "fix_suggestion": "Fix it",
            "steps": [],
            "confidence": 0.8,
            "fix_type": "retry",
            "potential_issues": [
                {"type": "config", "line": "good entry", "issue": "real issue", "fix_type": "configure_tool"},
                {"broken": true}
            ]
        }'''
        result = parse_analysis_response(raw)
        assert len(result["potential_issues"]) == 1
        assert result["potential_issues"][0]["line"] == "good entry"
