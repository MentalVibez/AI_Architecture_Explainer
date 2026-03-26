"""
app/services/scorecard.py
---------------------
Scorecard Engine: Produces the production-readiness score from findings + scan metadata.

Design rules:
  1. Every deduction is traceable to a specific CodeFinding
  2. Overall score is weighted by scan confidence — partial scans get honest scores
  3. No finding = no deduction. No invented penalties.
  4. Scores are per-dimension (security, performance, etc.) + overall composite
  5. The confidence interval is surfaced to the user — never hidden
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from app.schemas.intelligence import (
    CodeFinding,
    FileIntelligence,
    RepoIntelligence,
    ScanMetadata,
)


# ---------------------------------------------------------------------------
# Scoring dimensions
# ---------------------------------------------------------------------------

DIMENSIONS = [
    "security",
    "performance",
    "reliability",
    "maintainability",
    "test_coverage",
    "documentation",
]

# Base score for each dimension (before deductions)
BASE_SCORE = 100

# Dimension weights for composite score
DIMENSION_WEIGHTS: Dict[str, float] = {
    "security": 0.30,
    "performance": 0.15,
    "reliability": 0.20,
    "maintainability": 0.15,
    "test_coverage": 0.12,
    "documentation": 0.08,
}

# Minimum score per dimension (floor — prevents negative composite)
DIMENSION_FLOOR = 0


# ---------------------------------------------------------------------------
# Test coverage scorer (deterministic from file scan)
# ---------------------------------------------------------------------------

def score_test_coverage(files: List[FileIntelligence]) -> tuple[int, str]:
    """Returns (score, explanation)"""
    total = [f for f in files if f.language in ("python", "typescript", "javascript") and f.role != "config"]
    tests = [f for f in files if f.is_test]

    if not total:
        return (50, "No source files detected — score is neutral")

    test_ratio = len(tests) / len(total)

    if test_ratio >= 0.4:
        return (95, f"Strong test presence: {len(tests)} test files for {len(total)} source files")
    elif test_ratio >= 0.25:
        return (80, f"Moderate test coverage: {len(tests)} test files for {len(total)} source files")
    elif test_ratio >= 0.1:
        return (60, f"Limited test coverage: {len(tests)} test files for {len(total)} source files")
    elif test_ratio > 0:
        return (40, f"Minimal testing: only {len(tests)} test files for {len(total)} source files")
    else:
        return (10, "No test files detected")


# ---------------------------------------------------------------------------
# Documentation scorer (deterministic from file scan)
# ---------------------------------------------------------------------------

def score_documentation(files: List[FileIntelligence]) -> tuple[int, str]:
    source_files = [f for f in files if f.role not in ("test", "config", "migration", "infra", "unknown")]
    if not source_files:
        return (50, "No source files to evaluate")

    with_docs = [f for f in source_files if f.has_docstrings]
    readme_present = any(
        f.path.lower() in ("readme.md", "readme.rst", "readme.txt")
        for f in files
    )

    doc_ratio = len(with_docs) / len(source_files)
    score = int(doc_ratio * 80) + (20 if readme_present else 0)
    score = min(100, score)

    explanation = (
        f"{len(with_docs)}/{len(source_files)} source files have docstrings. "
        f"README: {'present' if readme_present else 'missing'}."
    )
    return (score, explanation)


# ---------------------------------------------------------------------------
# Scorecard builder
# ---------------------------------------------------------------------------

@dataclass
class DimensionScore:
    dimension: str
    raw_score: int              # Before confidence adjustment
    adjusted_score: int         # After confidence adjustment
    base: int = BASE_SCORE
    deductions: List[str] = field(default_factory=list)   # Human-readable evidence
    finding_ids: List[str] = field(default_factory=list)  # Traceable to findings
    explanation: str = ""

    @property
    def label(self) -> str:
        if self.adjusted_score >= 90:
            return "Excellent"
        elif self.adjusted_score >= 75:
            return "Good"
        elif self.adjusted_score >= 60:
            return "Moderate"
        elif self.adjusted_score >= 40:
            return "Poor"
        else:
            return "Critical"


@dataclass
class ProductionScore:
    dimension_scores: Dict[str, DimensionScore]
    composite_score: int
    composite_label: str
    confidence: float           # 0-1: how complete the scan was
    confidence_explanation: str
    total_findings: int
    findings_by_severity: Dict[str, int]
    before_optimization: Optional["ProductionScore"] = None  # Set when comparing


def build_scorecard(
    findings: List[CodeFinding],
    files: List[FileIntelligence],
    scan_metadata: ScanMetadata,
) -> ProductionScore:
    """
    Builds the full scorecard from findings + file scan data.
    All deductions are traceable. Confidence is calculated honestly.
    """

    # --- 1. Group findings by dimension ---
    dimension_findings: Dict[str, List[CodeFinding]] = {d: [] for d in DIMENSIONS}
    for f in findings:
        if not f.is_suppressed:
            cat = f.category
            if cat in dimension_findings:
                dimension_findings[cat].append(f)
            # Map some categories to scorecard dimensions
            elif cat in ("error_handling",):
                dimension_findings["reliability"].append(f)
            elif cat in ("type_safety",):
                dimension_findings["maintainability"].append(f)

    # --- 2. Score each dimension ---
    dimension_scores: Dict[str, DimensionScore] = {}

    for dim in DIMENSIONS:
        if dim == "test_coverage":
            score, explanation = score_test_coverage(files)
            dimension_scores[dim] = DimensionScore(
                dimension=dim,
                raw_score=score,
                adjusted_score=score,
                explanation=explanation,
            )
            continue

        if dim == "documentation":
            score, explanation = score_documentation(files)
            dimension_scores[dim] = DimensionScore(
                dimension=dim,
                raw_score=score,
                adjusted_score=score,
                explanation=explanation,
            )
            continue

        dim_findings = dimension_findings.get(dim, [])
        raw_score = BASE_SCORE
        deductions = []
        finding_ids = []

        for f in dim_findings:
            deduction = f.score_impact  # Always <= 0
            raw_score += deduction  # subtract
            deductions.append(
                f"[-{abs(deduction)}] {f.severity.upper()}: {f.title} ({f.file_path}:{f.line_start})"
            )
            finding_ids.append(f.id)

        raw_score = max(DIMENSION_FLOOR, raw_score)

        finding_count = len(dim_findings)
        if finding_count == 0:
            explanation = f"No {dim} issues detected."
        elif finding_count == 1:
            explanation = f"1 {dim} issue found."
        else:
            explanation = f"{finding_count} {dim} issues found."

        dimension_scores[dim] = DimensionScore(
            dimension=dim,
            raw_score=raw_score,
            adjusted_score=raw_score,  # adjusted below
            deductions=deductions,
            finding_ids=finding_ids,
            explanation=explanation,
        )

    # --- 3. Compute scan confidence ---
    confidence = _compute_confidence(scan_metadata, files)
    confidence_explanation = _explain_confidence(confidence, scan_metadata)

    # --- 4. Apply confidence adjustment to scores ---
    # Low confidence = wider uncertainty band → pull scores toward neutral (50)
    # Full confidence (1.0) = scores are exact
    # Low confidence (0.3) = scores blend toward 50
    NEUTRAL = 50
    for dim_score in dimension_scores.values():
        if confidence < 1.0:
            blended = int(
                (dim_score.raw_score * confidence) + (NEUTRAL * (1 - confidence))
            )
            dim_score.adjusted_score = max(DIMENSION_FLOOR, blended)
        else:
            dim_score.adjusted_score = dim_score.raw_score

    # --- 5. Compute weighted composite ---
    composite = sum(
        dimension_scores[dim].adjusted_score * DIMENSION_WEIGHTS[dim]
        for dim in DIMENSIONS
    )
    composite_score = int(round(composite))

    composite_label = _score_label(composite_score)

    # --- 6. Severity summary ---
    severity_counts: Dict[str, int] = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for f in findings:
        if not f.is_suppressed:
            severity_counts[f.severity] = severity_counts.get(f.severity, 0) + 1

    return ProductionScore(
        dimension_scores=dimension_scores,
        composite_score=composite_score,
        composite_label=composite_label,
        confidence=round(confidence, 3),
        confidence_explanation=confidence_explanation,
        total_findings=sum(1 for f in findings if not f.is_suppressed),
        findings_by_severity=severity_counts,
    )


def _compute_confidence(
    scan_metadata: ScanMetadata,
    files: List[FileIntelligence],
) -> float:
    """
    Honest confidence calculation with two separated concerns:

    1. scan_coverage  — what fraction of the repo was attempted
    2. parse_quality  — how well we actually parsed what we fetched

    The original code used `parse_success_rate` (fetch success) for both.
    This version derives true parse quality from the per-file confidence
    scores stored in FileIntelligence — a file that fetched fine but parsed
    with errors will have confidence < 1.0, and that shows here.

    Confidence ceiling is 0.97 — a score of 1.0 would imply certainty,
    which is never warranted from static analysis alone.
    """
    if scan_metadata.total_files == 0:
        return 0.0

    # Coverage: what fraction of total repo files were scanned
    scan_coverage = min(
        scan_metadata.files_scanned / scan_metadata.total_files,
        1.0,
    )

    # Parse quality: average FileIntelligence.confidence across scanned files
    # This is accurate because confidence=0.0 for fetch failures, <1.0 for
    # partial parses, and 1.0 for fully parsed files.
    scanned_files = [f for f in files if not f.parse_errors or f.confidence > 0.0]
    if scanned_files:
        parse_quality = sum(f.confidence for f in scanned_files) / len(scanned_files)
    else:
        parse_quality = 0.0

    # Structural completeness bonuses — small but meaningful
    has_tests = any(f.is_test for f in files)
    has_entrypoints = any(f.is_entrypoint for f in files)
    has_config = any(f.role == "config" for f in files)

    completeness_bonus = (
        (0.04 if has_tests else 0.0)
        + (0.04 if has_entrypoints else 0.0)
        + (0.02 if has_config else 0.0)
    )

    confidence = (
        (scan_coverage * 0.45)
        + (parse_quality * 0.40)
        + completeness_bonus
    )

    # Cap at 0.97 — static analysis is never certain
    return min(0.97, round(confidence, 3))


def _explain_confidence(confidence: float, meta: ScanMetadata) -> str:
    parts = [
        f"Scanned {meta.files_scanned}/{meta.total_files} files "
        f"({meta.files_scanned} fetched, {meta.files_failed} failed)."
    ]

    if meta.files_skipped > 0:
        parts.append(f"{meta.files_skipped} files skipped (binary/vendor/generated).")

    if meta.files_failed > 0:
        parts.append(f"{meta.files_failed} files failed to fetch or parse.")

    if confidence >= 0.85:
        parts.append("Score confidence is HIGH — results are reliable.")
    elif confidence >= 0.65:
        parts.append("Score confidence is MODERATE — some files may have been missed.")
    else:
        parts.append(
            "Score confidence is LOW — significant portions of the repo were not scanned. "
            "Treat scores as directional, not definitive."
        )

    return " ".join(parts)


def _score_label(score: int) -> str:
    if score >= 90:
        return "Production Ready"
    elif score >= 75:
        return "Near Production Ready"
    elif score >= 60:
        return "Needs Attention"
    elif score >= 40:
        return "Significant Issues"
    else:
        return "Not Production Ready"


# ---------------------------------------------------------------------------
# Before/After comparison
# ---------------------------------------------------------------------------

def compare_scores(
    before: ProductionScore,
    after: ProductionScore,
) -> Dict:
    """
    Produces a structured diff between pre- and post-optimization scores.
    Used by the Report layer to explain what changed and why.
    """
    delta = after.composite_score - before.composite_score
    dimension_deltas = {}

    for dim in DIMENSIONS:
        before_dim = before.dimension_scores.get(dim)
        after_dim = after.dimension_scores.get(dim)
        if before_dim and after_dim:
            d = after_dim.adjusted_score - before_dim.adjusted_score
            if d != 0:
                dimension_deltas[dim] = {
                    "before": before_dim.adjusted_score,
                    "after": after_dim.adjusted_score,
                    "delta": d,
                    "label_before": before_dim.label,
                    "label_after": after_dim.label,
                }

    findings_resolved = before.total_findings - after.total_findings
    severity_resolved = {
        sev: before.findings_by_severity.get(sev, 0) - after.findings_by_severity.get(sev, 0)
        for sev in ("critical", "high", "medium", "low")
    }

    return {
        "composite_before": before.composite_score,
        "composite_after": after.composite_score,
        "composite_delta": delta,
        "label_before": before.composite_label,
        "label_after": after.composite_label,
        "dimension_deltas": dimension_deltas,
        "findings_resolved": max(0, findings_resolved),
        "severity_resolved": {k: max(0, v) for k, v in severity_resolved.items()},
        "summary": _comparison_summary(delta, dimension_deltas, findings_resolved),
    }


def _comparison_summary(
    composite_delta: int,
    dimension_deltas: Dict,
    findings_resolved: int,
) -> str:
    if composite_delta <= 0:
        return "No improvement detected. Optimizations may have been minimal or offset by other issues."

    improved_dims = [
        f"{dim} (+{data['delta']})"
        for dim, data in dimension_deltas.items()
        if data["delta"] > 0
    ]

    parts = [f"Score improved by {composite_delta} points."]
    if improved_dims:
        parts.append(f"Improvements in: {', '.join(improved_dims)}.")
    if findings_resolved > 0:
        parts.append(f"{findings_resolved} issues resolved.")

    return " ".join(parts)
