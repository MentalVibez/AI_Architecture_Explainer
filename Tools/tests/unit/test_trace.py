"""
Tests for sentence-level traceability and challenge_claim().
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../.."))

from atlas_reviewer.llm.contract import build_llm_input
from atlas_reviewer.llm.summaries import _deterministic_fallback
from atlas_reviewer.llm.trace import TraceSource, SummaryTrace, SentenceTrace
from atlas_reviewer.models.report import (
    ReviewReport, RepoMeta, Scorecard, ReviewCoverage, ScoreInterpretation
)
from atlas_reviewer.models.finding import Finding
from atlas_reviewer.models.evidence import EvidenceItem


def make_report(security=58, testing=24, production_suitable=False):
    return ReviewReport(
        schema_version="1.0", ruleset_version="2026.03",
        repo=RepoMeta(url="https://github.com/test/repo", commit="abc123",
                      primary_languages=["Python"]),
        coverage=ReviewCoverage(limits=["Runtime execution not performed"]),
        scorecard=Scorecard(security=security, testing=testing,
                            maintainability=72, reliability=66,
                            operational_readiness=61, developer_experience=79),
        interpretation=ScoreInterpretation(
            overall_label="Mixed", production_suitable=production_suitable),
    )


def make_finding(rule_id="TEST-001", severity="high", category="testing"):
    return Finding(
        id=f"f-{rule_id}", rule_id=rule_id, title=f"Issue {rule_id}",
        category=category, severity=severity, confidence="high", layer="rule",
        summary="", why_it_matters="matters", suggested_fix="fix it",
        evidence=[EvidenceItem(kind="metric", value="evidence")],
    )


# ── Sentence-level traces ─────────────────────────────────────────────────────

def test_trace_is_sentence_level_not_paragraph():
    report = make_report(testing=20)
    findings = [make_finding("TEST-001", "high", "testing")]
    llm_input = build_llm_input(report, 55, findings)
    summary, trace = _deterministic_fallback(llm_input, findings)
    # Each trace entry should be a complete sentence, not a fragment
    for t in trace.all_traces():
        assert len(t.sentence) > 10, "Trace entry should be a full sentence"
        assert t.sentence.strip()[-1] in ".!?", f"Should end with punctuation: '{t.sentence}'"


def test_each_trace_has_single_source_type():
    report = make_report(testing=24)
    findings = [make_finding("SEC-001", "critical", "security")]
    llm_input = build_llm_input(report, 50, findings)
    summary, trace = _deterministic_fallback(llm_input, findings)
    for t in trace.all_traces():
        assert isinstance(t.source_type, TraceSource)


def test_developer_traces_minimum_count():
    report = make_report(testing=20, security=55)
    findings = [make_finding("TEST-001", "critical")]
    llm_input = build_llm_input(report, 55, findings)
    summary, trace = _deterministic_fallback(llm_input, findings)
    assert len(trace.developer_traces) >= 1


def test_manager_traces_always_include_verdict():
    report = make_report()
    findings = []
    llm_input = build_llm_input(report, 80, findings)
    summary, trace = _deterministic_fallback(llm_input, findings)
    verdict_traces = [t for t in trace.manager_traces if t.source_type == TraceSource.VERDICT]
    assert len(verdict_traces) >= 1


# ── challenge_claim() ─────────────────────────────────────────────────────────

def test_challenge_claim_finds_trace_for_testing_sentence():
    report = make_report(testing=24)
    findings = [make_finding()]
    llm_input = build_llm_input(report, 60, findings)
    summary, trace = _deterministic_fallback(llm_input, findings)
    results = trace.challenge_claim("Testing coverage is critically insufficient")
    assert len(results) >= 1
    assert results[0].score_field == "testing"


def test_challenge_claim_finds_trace_for_critical_sentence():
    report = make_report()
    findings = [make_finding("SEC-001", "critical", "security")]
    llm_input = build_llm_input(report, 50, findings)
    summary, trace = _deterministic_fallback(llm_input, findings)
    results = trace.challenge_claim("critical finding")
    assert len(results) >= 1
    assert "SEC-001" in results[0].finding_ids


def test_challenge_claim_returns_empty_for_invented_claim():
    report = make_report()
    findings = []
    llm_input = build_llm_input(report, 90, findings)
    summary, trace = _deterministic_fallback(llm_input, findings)
    # This sentence does not exist in any trace
    results = trace.challenge_claim("SQL injection vulnerability detected in payment module")
    assert results == [], "Invented claim should return empty trace"


def test_challenge_claim_case_insensitive():
    report = make_report(testing=20)
    findings = [make_finding()]
    llm_input = build_llm_input(report, 55, findings)
    summary, trace = _deterministic_fallback(llm_input, findings)
    results_lower = trace.challenge_claim("testing coverage")
    results_upper = trace.challenge_claim("TESTING COVERAGE")
    assert len(results_lower) == len(results_upper)


# ── untraced_check() ──────────────────────────────────────────────────────────

def test_untraced_check_returns_empty_for_clean_summary():
    report = make_report(testing=20)
    findings = [make_finding("TEST-001", "critical", "testing")]
    llm_input = build_llm_input(report, 55, findings)
    summary, trace = _deterministic_fallback(llm_input, findings)
    all_text = f"{summary.developer} {summary.manager} {summary.hiring}"
    untraced = trace.untraced_check(all_text)
    # Deterministic fallback should have zero untraced sentences
    assert len(untraced) == 0, f"Unexpected untraced: {untraced}"


def test_untraced_check_flags_invented_sentence():
    trace = SummaryTrace()
    trace.developer_traces = [SentenceTrace(
        sentence="This repo has critical issues.",
        source_type=TraceSource.FINDING,
        finding_ids=["SEC-001"],
    )]
    # Inject a sentence that has no trace
    invented = "The authentication module has a race condition vulnerability."
    real = "This repo has critical issues."
    untraced = trace.untraced_check(f"{real} {invented}")
    assert any("race condition" in s for s in untraced)


# ── audit_report() ───────────────────────────────────────────────────────────

def test_audit_report_structure():
    report = make_report(testing=20)
    findings = [make_finding()]
    llm_input = build_llm_input(report, 55, findings)
    summary, trace = _deterministic_fallback(llm_input, findings)
    audit = trace.audit_report()
    assert "generation_method" in audit
    assert "total_traced_sentences" in audit
    assert audit["total_traced_sentences"] == len(trace.all_traces())
    assert isinstance(audit["developer"], list)
    assert isinstance(audit["manager"], list)


def test_fragment_property_truncates_long_sentences():
    t = SentenceTrace(
        sentence="This is a very long sentence that exceeds sixty characters by quite a lot.",
        source_type=TraceSource.DETERMINISTIC,
    )
    assert t.fragment.endswith("…")
    assert len(t.fragment) <= 63  # 60 + ellipsis
