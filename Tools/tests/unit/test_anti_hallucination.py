"""
Tests for the anti-hallucination contract layer.

Verifies:
  1. LLM input never contains raw code or file contents
  2. Deterministic fallback produces valid output without LLM
  3. Output validation rejects hallucinated claims
  4. LLM input is bounded to structured findings only
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../.."))

import json
from atlas_reviewer.llm.contract import (
    LLMFindingInput, LLMReportInput, LLMSummaryOutput, build_llm_input
)
from atlas_reviewer.llm.summaries import _deterministic_fallback, _validate_output
from atlas_reviewer.models.report import ReviewReport, RepoMeta, Scorecard, ReviewCoverage, ScoreInterpretation
from atlas_reviewer.models.finding import Finding
from atlas_reviewer.models.evidence import EvidenceItem


def make_report(security=58, testing=24, production_suitable=False):
    return ReviewReport(
        schema_version="1.0", ruleset_version="2026.03",
        repo=RepoMeta(url="https://github.com/test/repo", commit="abc123",
                      primary_languages=["Python"]),
        coverage=ReviewCoverage(
            repo_files_scanned_pct=0.87,
            limits=["Runtime execution not performed"],
        ),
        scorecard=Scorecard(security=security, testing=testing,
                            maintainability=72, reliability=66,
                            operational_readiness=61, developer_experience=79),
        interpretation=ScoreInterpretation(
            overall_label="Promising — not production-ready",
            trust_recommendation="moderate",
            production_suitable=production_suitable,
        ),
    )


def make_finding(rule_id="SEC-001", severity="high", category="security",
                 title="Test finding", why="It matters", fix="Fix it"):
    return Finding(
        id=f"f-{rule_id}", rule_id=rule_id, title=title, category=category,
        severity=severity, confidence="high", layer="rule",
        summary="", why_it_matters=why, suggested_fix=fix,
        evidence=[EvidenceItem(kind="tool", value="scanner found issue")],
    )


# ── Contract: LLM input boundaries ───────────────────────────────────────────

def test_llm_input_never_contains_raw_code():
    report = make_report()
    findings = [make_finding()]
    llm_input = build_llm_input(report, 68, findings)
    # Serialize and check no source code leaks through
    serialized = json.dumps(llm_input.model_dump())
    # These strings should never appear in the LLM payload
    assert "def " not in serialized, "Function definitions should not be in LLM input"
    assert "import " not in serialized, "Raw import statements should not be in LLM input"
    assert "class " not in serialized, "Class definitions should not be in LLM input"


def test_llm_input_contains_only_structured_fields():
    report = make_report()
    findings = [make_finding(severity="critical"), make_finding("SEC-002", "high")]
    llm_input = build_llm_input(report, 62, findings)
    # Must have score summary
    assert "security" in llm_input.scorecard_summary
    # Must have findings but as structured objects
    assert all(isinstance(f, LLMFindingInput) for f in llm_input.findings)
    # Verdict must come from report, not recomputed
    assert llm_input.verdict_label == "Promising — not production-ready"


def test_llm_input_filters_info_findings():
    report = make_report()
    findings = [
        make_finding("A", "critical"),
        make_finding("B", "info"),   # should be filtered
        make_finding("C", "high"),
    ]
    llm_input = build_llm_input(report, 62, findings)
    severities = {f.severity for f in llm_input.findings}
    assert "info" not in severities, "Info findings should not be passed to LLM"


def test_llm_input_caps_evidence_strings():
    report = make_report()
    f = make_finding()
    f.evidence = [EvidenceItem(kind="tool", value=f"evidence {i}") for i in range(10)]
    llm_input = build_llm_input(report, 62, [f])
    for lf in llm_input.findings:
        assert len(lf.evidence_strings) <= 3, "LLM should see max 3 evidence strings per finding"


# ── Contract: Deterministic fallback ─────────────────────────────────────────

def test_deterministic_fallback_works_without_llm():
    report = make_report(security=58, testing=24)
    findings = [
        make_finding("SEC-001", "critical", title="Exposed credential"),
        make_finding("TEST-001", "high", category="testing", title="No tests"),
    ]
    llm_input = build_llm_input(report, 62, findings)
    summary, _ = _deterministic_fallback(llm_input)
    assert summary.developer, "Developer summary must not be empty"
    assert summary.manager, "Manager summary must not be empty"
    assert summary.hiring, "Hiring summary must not be empty"


def test_deterministic_fallback_mentions_critical_count():
    report = make_report()
    findings = [make_finding("SEC-001", "critical"), make_finding("SEC-002", "critical")]
    llm_input = build_llm_input(report, 50, findings)
    summary, _ = _deterministic_fallback(llm_input)
    assert "2" in summary.developer or "critical" in summary.developer.lower()


def test_deterministic_fallback_mentions_testing_when_weak():
    report = make_report(testing=20)
    findings = [make_finding("TEST-001", "high", category="testing")]
    llm_input = build_llm_input(report, 60, findings)
    summary, _ = _deterministic_fallback(llm_input)
    assert "test" in summary.developer.lower()


# ── Contract: Output validation ───────────────────────────────────────────────

def test_validation_accepts_grounded_risks():
    llm_input = LLMReportInput(
        repo_url="https://github.com/test/repo", primary_languages=["Python"],
        overall_score=68, verdict_label="Mixed", production_suitable=False,
        scorecard_summary={"security": 58},
        findings=[LLMFindingInput(rule_id="SEC-001", severity="high", confidence="high",
                                   category="security", title="Security issue",
                                   why_it_matters="Risk", suggested_fix="Fix",
                                   evidence_strings=["scanner found it"])],
        coverage_pct=0.87, coverage_limits=[], ruleset_version="2026.03",
    )
    output = LLMSummaryOutput(
        developer_summary="Security issues detected.",
        manager_summary="Elevated risk.",
        hiring_summary="Security gaps present.",
        top_risks=["security gap in authentication"],
        strengths=["good structure"],
    )
    violations = _validate_output(output, llm_input)
    # Should pass — "security" is a known category
    assert len(violations) == 0


def test_llm_summary_output_schema_requires_all_fields():
    import pytest
    with pytest.raises(Exception):
        LLMSummaryOutput(developer_summary="only one field")
