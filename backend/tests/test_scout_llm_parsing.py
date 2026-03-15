"""
test_scout_llm_parsing.py
─────────────────────────────────────────────────────────────────────────────
Tests for the LLM output parsing layer.

These tests verify that safe_parse_llm_output() handles every realistic
failure mode without crashing — which is the whole point of FIX [4].
─────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations
import json
import pytest

from app.llm.scout_prompts import safe_parse_llm_output, LLMScoutOutput


# ── helpers ───────────────────────────────────────────────────────────────────

def _valid_payload(overrides: dict | None = None) -> str:
    base = {
        "scores": {
            "gh_123": {
                "relevance_score": 82,
                "verdict": "HIGHLY_RECOMMENDED",
                "insight": "This repo is the canonical implementation of the pattern you are looking for. It is actively maintained and widely adopted.",
                "risks": ["requires Python 3.11+"],
            }
        },
        "tldr": "The top result is a strong match for your query. It has broad community support and recent maintenance activity.",
    }
    if overrides:
        base.update(overrides)
    return json.dumps(base)


# ═════════════════════════════════════════════════════════════════════════════
# Happy path
# ═════════════════════════════════════════════════════════════════════════════

class TestValidOutput:
    def test_clean_json_parses(self):
        result = safe_parse_llm_output(_valid_payload())
        assert result is not None
        assert isinstance(result, LLMScoutOutput)

    def test_scores_accessible(self):
        result = safe_parse_llm_output(_valid_payload())
        assert "gh_123" in result.scores
        score = result.scores["gh_123"]
        assert score.relevance_score == 82
        assert score.verdict == "HIGHLY_RECOMMENDED"

    def test_tldr_accessible(self):
        result = safe_parse_llm_output(_valid_payload())
        assert len(result.tldr) > 20

    def test_empty_risks_list_valid(self):
        payload = _valid_payload()
        data = json.loads(payload)
        data["scores"]["gh_123"]["risks"] = []
        result = safe_parse_llm_output(json.dumps(data))
        assert result is not None
        assert result.scores["gh_123"].risks == []

    def test_multiple_repos_in_scores(self):
        data = json.loads(_valid_payload())
        data["scores"]["gl_456"] = {
            "relevance_score": 60,
            "verdict": "RECOMMENDED",
            "insight": "A decent alternative with fewer features but easier setup and good documentation.",
            "risks": [],
        }
        result = safe_parse_llm_output(json.dumps(data))
        assert result is not None
        assert len(result.scores) == 2


# ═════════════════════════════════════════════════════════════════════════════
# Markdown fence stripping
# ═════════════════════════════════════════════════════════════════════════════

class TestMarkdownFenceStripping:
    def test_json_fence_stripped(self):
        raw = f"```json\n{_valid_payload()}\n```"
        result = safe_parse_llm_output(raw)
        assert result is not None

    def test_plain_fence_stripped(self):
        raw = f"```\n{_valid_payload()}\n```"
        result = safe_parse_llm_output(raw)
        assert result is not None

    def test_leading_whitespace_handled(self):
        raw = f"   \n{_valid_payload()}"
        result = safe_parse_llm_output(raw)
        assert result is not None

    def test_trailing_text_after_json(self):
        """LLM sometimes appends explanation after the JSON block."""
        raw = f"```json\n{_valid_payload()}\n```\n\nHope this helps!"
        result = safe_parse_llm_output(raw)
        assert result is not None


# ═════════════════════════════════════════════════════════════════════════════
# Malformed output — all should return None without raising
# ═════════════════════════════════════════════════════════════════════════════

class TestMalformedOutput:
    def test_empty_string_returns_none(self):
        assert safe_parse_llm_output("") is None

    def test_plain_text_returns_none(self):
        assert safe_parse_llm_output("Sorry, I cannot help with that.") is None

    def test_truncated_json_returns_none(self):
        truncated = _valid_payload()[:50]
        assert safe_parse_llm_output(truncated) is None

    def test_missing_scores_key_returns_none(self):
        data = json.loads(_valid_payload())
        del data["scores"]
        assert safe_parse_llm_output(json.dumps(data)) is None

    def test_missing_tldr_returns_none(self):
        data = json.loads(_valid_payload())
        del data["tldr"]
        assert safe_parse_llm_output(json.dumps(data)) is None

    def test_short_tldr_returns_none(self):
        """tldr must be at least 20 chars per schema."""
        data = json.loads(_valid_payload())
        data["tldr"] = "ok"
        assert safe_parse_llm_output(json.dumps(data)) is None

    def test_invalid_verdict_returns_none(self):
        data = json.loads(_valid_payload())
        data["scores"]["gh_123"]["verdict"] = "MAGIC"
        assert safe_parse_llm_output(json.dumps(data)) is None

    def test_relevance_out_of_range_returns_none(self):
        data = json.loads(_valid_payload())
        data["scores"]["gh_123"]["relevance_score"] = 150
        assert safe_parse_llm_output(json.dumps(data)) is None

    def test_relevance_negative_returns_none(self):
        data = json.loads(_valid_payload())
        data["scores"]["gh_123"]["relevance_score"] = -5
        assert safe_parse_llm_output(json.dumps(data)) is None

    def test_short_insight_returns_none(self):
        """insight must be at least 20 chars per schema."""
        data = json.loads(_valid_payload())
        data["scores"]["gh_123"]["insight"] = "ok"
        assert safe_parse_llm_output(json.dumps(data)) is None

    def test_null_scores_returns_none(self):
        data = json.loads(_valid_payload())
        data["scores"] = None
        assert safe_parse_llm_output(json.dumps(data)) is None

    def test_wrong_type_for_scores_returns_none(self):
        data = json.loads(_valid_payload())
        data["scores"] = "should be a dict"
        assert safe_parse_llm_output(json.dumps(data)) is None

    def test_html_response_returns_none(self):
        assert safe_parse_llm_output("<html><body>Error 500</body></html>") is None

    def test_none_input_returns_none(self):
        # Guard against callers passing None
        assert safe_parse_llm_output(None) is None   # type: ignore[arg-type]


# ═════════════════════════════════════════════════════════════════════════════
# Score blend
# ═════════════════════════════════════════════════════════════════════════════

class TestScoreBlend:
    """Tests for ScoreBreakdown.blend() — the weighted composition."""

    def test_blend_default_weights(self):
        from app.schemas.scout import ScoreBreakdown
        b = ScoreBreakdown.blend(quality=60, relevance=80)
        # 0.4 * 60 + 0.6 * 80 = 24 + 48 = 72
        assert b.overall_score == 72
        assert b.quality_score == 60
        assert b.relevance_score == 80

    def test_blend_clamps_to_100(self):
        from app.schemas.scout import ScoreBreakdown
        b = ScoreBreakdown.blend(quality=100, relevance=100)
        assert b.overall_score == 100

    def test_blend_zero_values(self):
        from app.schemas.scout import ScoreBreakdown
        b = ScoreBreakdown.blend(quality=0, relevance=0)
        assert b.overall_score == 0

    def test_high_relevance_dominates(self):
        """relevance_weight=0.6 means relevance should drive overall more than quality."""
        from app.schemas.scout import ScoreBreakdown
        high_q_low_r = ScoreBreakdown.blend(quality=90, relevance=10)
        low_q_high_r = ScoreBreakdown.blend(quality=10, relevance=90)
        # 0.4*90 + 0.6*10 = 42    vs    0.4*10 + 0.6*90 = 58
        assert low_q_high_r.overall_score > high_q_low_r.overall_score
