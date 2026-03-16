"""
Sentence-level summary traceability.

Design law: every sentence that appears in a summary must be traceable
to a specific source — not a paragraph, not a summary field, but a sentence.

challenge_claim(sentence_fragment) → list[SentenceTrace]
  Given any fragment from a generated summary, returns the exact
  source entries that support it. Empty = untraceable = audit flag.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum


class TraceSource(str, Enum):
    FINDING          = "finding"
    SCORE_THRESHOLD  = "score_threshold"
    VERDICT          = "verdict"
    COVERAGE         = "coverage"
    DETERMINISTIC    = "deterministic"


@dataclass
class SentenceTrace:
    """One claim → one source. The minimum auditable unit."""
    sentence: str                # The full sentence this trace supports
    source_type: TraceSource
    finding_ids: list[str]       = field(default_factory=list)
    score_field: str | None      = None
    score_value: int | None      = None
    score_threshold: int | None  = None
    verdict_field: str | None    = None

    @property
    def fragment(self) -> str:
        """First 60 chars — for display in audit output."""
        return self.sentence[:60] + ("…" if len(self.sentence) > 60 else "")

    def to_dict(self) -> dict:
        return {
            "sentence": self.sentence,
            "fragment": self.fragment,
            "source": self.source_type.value,
            "finding_ids": self.finding_ids,
            "score": f"{self.score_field}={self.score_value}" if self.score_field else None,
            "threshold": self.score_threshold,
            "verdict_field": self.verdict_field,
        }


@dataclass
class SummaryTrace:
    """Complete sentence-level trace for all three summary voices."""
    developer_traces: list[SentenceTrace] = field(default_factory=list)
    manager_traces:   list[SentenceTrace] = field(default_factory=list)
    hiring_traces:    list[SentenceTrace] = field(default_factory=list)
    generation_method: str = "deterministic"   # "deterministic" | "llm_validated"
    validated: bool = True

    def all_traces(self) -> list[SentenceTrace]:
        return self.developer_traces + self.manager_traces + self.hiring_traces

    def challenge_claim(self, fragment: str) -> list[SentenceTrace]:
        """
        Given any substring from a generated summary, return every
        SentenceTrace that supports it. Empty list = untraceable claim.

        Usage:
            trace.challenge_claim("testing coverage is critically")
            # → [SentenceTrace(score_field="testing", score_value=24, ...)]
        """
        needle = fragment.lower().strip()
        matches = []
        for t in self.all_traces():
            if needle in t.sentence.lower():
                matches.append(t)
        return matches

    def audit_report(self) -> dict:
        """Full audit output. Every trace in every voice."""
        return {
            "generation_method": self.generation_method,
            "validated": self.validated,
            "total_traced_sentences": len(self.all_traces()),
            "developer": [t.to_dict() for t in self.developer_traces],
            "manager":   [t.to_dict() for t in self.manager_traces],
            "hiring":    [t.to_dict() for t in self.hiring_traces],
        }

    def to_dict(self) -> dict:
        """Compact form for storage in ReviewSummary.trace."""
        return {
            "generation_method": self.generation_method,
            "validated": self.validated,
            "developer": [t.to_dict() for t in self.developer_traces],
            "manager":   [t.to_dict() for t in self.manager_traces],
            "hiring":    [t.to_dict() for t in self.hiring_traces],
        }

    def untraced_check(self, summary_text: str) -> list[str]:
        """
        Split summary_text into sentences and check each against traces.
        Returns sentences that have NO trace entry — potential hallucination surface.
        """
        import re
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", summary_text) if s.strip()]
        untraced = []
        for sentence in sentences:
            if not self.challenge_claim(sentence[:40]):
                untraced.append(sentence)
        return untraced


def _score_trace(sentence: str, field: str, value: int, threshold: int) -> SentenceTrace:
    return SentenceTrace(
        sentence=sentence, source_type=TraceSource.SCORE_THRESHOLD,
        score_field=field, score_value=value, score_threshold=threshold,
    )


def _finding_trace(sentence: str, finding_ids: list[str]) -> SentenceTrace:
    return SentenceTrace(
        sentence=sentence, source_type=TraceSource.FINDING,
        finding_ids=finding_ids,
    )


def _verdict_trace(sentence: str, verdict_field: str) -> SentenceTrace:
    return SentenceTrace(
        sentence=sentence, source_type=TraceSource.VERDICT,
        verdict_field=verdict_field,
    )


def build_deterministic_trace(
    llm_input,
    findings: list,
    scorecard_dict: dict,
) -> SummaryTrace:
    """
    Build sentence-level traces for deterministic fallback output.
    Each call to this function mirrors the sentence logic in _deterministic_fallback.
    They must stay in sync.
    """
    trace = SummaryTrace(generation_method="deterministic", validated=True)
    sc = scorecard_dict
    critical = [f for f in findings if f.severity == "critical"]
    high     = [f for f in findings if f.severity == "high"]
    testing  = sc.get("testing", 100)
    security = sc.get("security", 100)
    verdict  = llm_input.verdict_label

    # ── Developer traces ──────────────────────────────────────────────────
    if critical:
        sentence = f"This repository has {len(critical)} critical finding(s) requiring immediate attention before deployment."
        trace.developer_traces.append(_finding_trace(sentence, [f.rule_id for f in critical]))
    elif high:
        cats = list({f.category for f in high})[:2]
        sentence = f"This repository has {len(high)} high-severity finding(s) in {', '.join(cats)}."
        trace.developer_traces.append(_finding_trace(sentence, [f.rule_id for f in high[:4]]))
    else:
        sentence = f"This repository is {verdict.lower()} with no critical issues detected."
        trace.developer_traces.append(_verdict_trace(sentence, "verdict_label"))

    if testing < 50:
        sentence = "Testing coverage is critically insufficient."
        trace.developer_traces.append(_score_trace(sentence, "testing", testing, 50))
    elif security < 65:
        sentence = "Security posture requires attention before production use."
        trace.developer_traces.append(_score_trace(sentence, "security", security, 65))

    # ── Manager traces ────────────────────────────────────────────────────
    verdict_sentence = f"This repository is {verdict.lower()}."
    trace.manager_traces.append(_verdict_trace(verdict_sentence, "verdict_label"))

    # Build the combined gap sentence the same way _build_sentences does
    gap_areas = [fname for fname, threshold in [("testing",50),("security",65),("reliability",65)]
                 if sc.get(fname, 100) < threshold]
    if gap_areas:
        combined_sentence = f"Elevated delivery risk in {', '.join(gap_areas)}."
        # Primary trace: first gap field. Combined because that's what the output produces.
        primary_field = gap_areas[0]
        trace.manager_traces.append(_score_trace(
            combined_sentence, primary_field, sc.get(primary_field, 100),
            {"testing":50,"security":65,"reliability":65}[primary_field],
        ))

    if not llm_input.production_suitable:
        sentence = "A hardening sprint is recommended before further onboarding."
        trace.manager_traces.append(SentenceTrace(
            sentence=sentence, source_type=TraceSource.VERDICT,
            verdict_field="production_suitable",
        ))
    else:
        # Two sentences produced when production_suitable: "...manageable technical debt." + "No blockers..."
        sentence1 = f"This repository is {verdict.lower()} with manageable technical debt."
        trace.manager_traces.append(SentenceTrace(
            sentence=sentence1, source_type=TraceSource.VERDICT,
            verdict_field="production_suitable",
        ))
        sentence2 = "No blockers for planned delivery."
        trace.manager_traces.append(_verdict_trace(sentence2, "production_suitable"))

    # ── Hiring traces ─────────────────────────────────────────────────────
    # Qualifier depends on confidence_label — must match _build_sentences() logic
    confidence_label = getattr(llm_input, "confidence_label", "Low")
    adapters_ran = getattr(llm_input, "adapters_ran", False)
    if confidence_label == "High":
        qualifier = "demonstrates"
    elif confidence_label == "Medium":
        qualifier = "shows signals of"
    else:
        qualifier = "shows structural signals of"

    weak   = [k for k, v in sc.items() if v < 55]
    strong = [k for k, v in sc.items() if v >= 75]

    if weak:
        sentence = f"This repository {qualifier} implementation capability but lacks discipline in {', '.join(weak[:2]).replace('_', ' ')}."
        trace.hiring_traces.append(SentenceTrace(
            sentence=sentence, source_type=TraceSource.SCORE_THRESHOLD,
            score_field=weak[0], score_value=sc[weak[0]], score_threshold=55,
        ))
    else:
        if confidence_label == "Low":
            sentence = "Structural signals suggest this repository has basic engineering hygiene in place."
            trace.hiring_traces.append(SentenceTrace(
                sentence=sentence, source_type=TraceSource.SCORE_THRESHOLD,
                score_field="developer_experience", score_value=sc.get("developer_experience", 80), score_threshold=75,
            ))
            if not adapters_ran:
                sentence2 = "Static analysis was not available — deeper quality assessment requires tool output."
                trace.hiring_traces.append(SentenceTrace(
                    sentence=sentence2, source_type=TraceSource.COVERAGE,
                ))
        else:
            sentence = f"This repository {qualifier} solid engineering discipline across {', '.join(strong[:3]).replace('_', ' ')}."
            trace.hiring_traces.append(SentenceTrace(
                sentence=sentence, source_type=TraceSource.SCORE_THRESHOLD,
                score_field=strong[0] if strong else "developer_experience",
                score_value=sc.get(strong[0] if strong else "developer_experience", 100),
                score_threshold=75,
            ))

    if testing < 40:
        sentence = "Absence of testing is a significant signal for a hiring evaluation."
        trace.hiring_traces.append(_score_trace(sentence, "testing", testing, 40))

    return trace
