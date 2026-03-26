"""
app/services/report_builder.py
---------------------------
ReportBuilder: Converts RepoIntelligence into the API response payload.

This layer is responsible for:
  1. Attaching UITruthLabel to every piece of output
  2. Structuring data for frontend consumption
  3. Separating the analysis engine output from the API contract

Rules:
  - No analysis logic here — only formatting and label attachment
  - Every claim in the response has a truth label or is clearly marked as derived
  - The frontend renders what it receives — it does not decide what's confirmed
  - Score values never appear without confidence context

The response shape produced here maps directly to the existing Atlas API contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.schemas.intelligence import (
    CodeFinding,
    ConfidenceBreakdown,
    DependencyEdge,
    RepoIntelligence,
    TruthLabels,
    UITruthLabel,
)

# ---------------------------------------------------------------------------
# Response shape types
# These are the exact structures the frontend receives.
# They are separate from the internal schema types to allow the API contract
# to evolve independently.
# ---------------------------------------------------------------------------

@dataclass
class EdgeResponse:
    source_path: str
    target_path: str | None
    raw_import: str
    kind: str
    confidence: str
    unresolved_reason: str | None
    truth_label: dict  # serialized UITruthLabel


@dataclass
class FileResponse:
    path: str
    language: str
    role: str
    is_entrypoint: bool
    is_on_critical_path: bool
    loc: int
    complexity_score: float
    caller_count: int
    sensitive_operations: list[str]
    confidence: float
    was_truncated: bool
    truth_label: dict


@dataclass
class FindingResponse:
    id: str
    file_path: str
    category: str
    severity: str
    source: str
    line_start: int
    line_end: int
    evidence_snippet: str
    title: str
    explanation: str
    remediation: str | None
    score_impact: int
    confidence: float


@dataclass
class DimensionScoreResponse:
    dimension: str
    score: int
    label: str
    deductions: list[str]
    finding_count: int


@dataclass
class ScorecardResponse:
    composite_score: int
    composite_label: str
    dimensions: list[DimensionScoreResponse]
    total_findings: int
    findings_by_severity: dict[str, int]
    confidence: float
    confidence_label: str
    truth_label: dict


@dataclass
class GraphSummaryResponse:
    total_files: int
    files_scanned: int
    entrypoints: list[str]
    critical_path_files: list[str]
    critical_path_algorithm: str
    graph_semantics_version: int
    graph_confidence: float
    confirmed_edge_count: int
    unresolved_edge_count: int
    unresolved_by_reason: dict[str, int]
    languages: dict[str, int]


@dataclass
class AnalysisReportResponse:
    """
    The top-level API response for a completed analysis.
    Maps to GET /api/results/{result_id}
    """
    repo_url: str
    repo_owner: str
    repo_name: str
    schema_version: str
    graph_semantics_version: int

    # Summary section — what the frontend shows first
    graph: GraphSummaryResponse
    scorecard: ScorecardResponse | None

    # Detailed data — loaded on demand by the frontend
    files: list[FileResponse]
    findings: list[FindingResponse]
    edges: list[EdgeResponse]

    # Overall confidence — shown prominently in the UI
    overall_confidence: float
    confidence_breakdown: dict[str, float]
    confidence_truth_label: dict

    # Scan metadata
    scan_duration_seconds: float
    total_files_in_repo: int

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict for JSON response."""
        import dataclasses
        return dataclasses.asdict(self)


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------

class ReportBuilder:
    """
    Converts RepoIntelligence + optional scorecard into AnalysisReportResponse.

    Usage:
        builder = ReportBuilder()
        report = builder.build(intelligence, scorecard)
        return JSONResponse(report.to_dict())
    """

    def build(
        self,
        ri: RepoIntelligence,
        scorecard=None,  # ProductionScore from scorecard.py (optional)
    ) -> AnalysisReportResponse:
        files_response = self._build_files(ri)
        findings_response = self._build_findings(ri.findings)
        edges_response = self._build_edges(ri.edges)
        graph_response = self._build_graph_summary(ri)
        scorecard_response = self._build_scorecard(scorecard, ri.confidence) if scorecard else None
        confidence_breakdown = self._build_confidence_breakdown(ri.confidence)
        confidence_truth_label = ri.ui_confidence_label().__dict__

        scan_duration = (
            ri.scan_metadata.scan_duration_seconds if ri.scan_metadata else 0.0
        )
        total_files = ri.scan_metadata.total_files if ri.scan_metadata else 0

        return AnalysisReportResponse(
            repo_url=ri.repo_url,
            repo_owner=ri.repo_owner,
            repo_name=ri.repo_name,
            schema_version=ri.schema_version,
            graph_semantics_version=ri.graph_semantics_version,
            graph=graph_response,
            scorecard=scorecard_response,
            files=files_response,
            findings=findings_response,
            edges=edges_response,
            overall_confidence=ri.overall_confidence,
            confidence_breakdown=confidence_breakdown,
            confidence_truth_label=confidence_truth_label,
            scan_duration_seconds=scan_duration,
            total_files_in_repo=total_files,
        )

    def _build_files(self, ri: RepoIntelligence) -> list[FileResponse]:
        ctx_map = ri.contexts
        responses = []
        for fi in ri.files:
            ctx = ctx_map.get(fi.path)
            is_critical = ctx.is_on_critical_path if ctx else False
            caller_count = ctx.caller_count if ctx else 0

            # Determine truth label for this file
            if fi.confidence == 0.0:
                label = TruthLabels.parse_failed()
            elif fi.was_truncated:
                label = UITruthLabel(
                    variant="degraded",
                    short="Partially scanned",
                    detail="File exceeded size limit and was truncated. "
                           "Analysis covers the first portion only.",
                )
            elif is_critical:
                label = TruthLabels.critical_path_bfs()
            else:
                label = TruthLabels.not_critical_path()

            responses.append(FileResponse(
                path=fi.path,
                language=fi.language,
                role=fi.role,
                is_entrypoint=fi.is_entrypoint,
                is_on_critical_path=is_critical,
                loc=fi.loc,
                complexity_score=fi.complexity_score,
                caller_count=caller_count,
                sensitive_operations=fi.sensitive_operations,
                confidence=fi.confidence,
                was_truncated=fi.was_truncated,
                truth_label=label.__dict__,
            ))

        # Sort: entrypoints first, then by caller_count desc, then path
        responses.sort(key=lambda r: (
            0 if r.is_entrypoint else (1 if r.is_on_critical_path else 2),
            -r.caller_count,
            r.path,
        ))
        return responses

    def _build_findings(self, findings: list[CodeFinding]) -> list[FindingResponse]:
        responses = []
        for f in findings:
            if f.is_suppressed:
                continue
            responses.append(FindingResponse(
                id=f.id,
                file_path=f.file_path,
                category=f.category,
                severity=f.severity,
                source=f.source,
                line_start=f.line_start,
                line_end=f.line_end,
                evidence_snippet=f.evidence_snippet,
                title=f.title,
                explanation=f.explanation,
                remediation=f.remediation,
                score_impact=f.score_impact,
                confidence=f.confidence,
            ))

        # Sort: critical first, then high, medium, low; within severity by file
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        responses.sort(key=lambda r: (
            severity_order.get(r.severity, 9),
            r.file_path,
            r.line_start,
        ))
        return responses

    def _build_edges(self, edges: list[DependencyEdge]) -> list[EdgeResponse]:
        responses = []
        for e in edges:
            if e.confidence == "confirmed":
                label = TruthLabels.confirmed_edge()
            else:
                label = TruthLabels.from_unresolved_reason(e.unresolved_reason)

            responses.append(EdgeResponse(
                source_path=e.source_path,
                target_path=e.target_path,
                raw_import=e.raw_import,
                kind=e.kind,
                confidence=e.confidence,
                unresolved_reason=e.unresolved_reason,
                truth_label=label.__dict__,
            ))
        return responses

    def _build_graph_summary(self, ri: RepoIntelligence) -> GraphSummaryResponse:
        ctx_map = ri.contexts

        entrypoints = [f.path for f in ri.files if f.is_entrypoint]
        critical = [
            f.path for f in ri.files
            if ctx_map.get(f.path) and ctx_map[f.path].is_on_critical_path
        ]

        confirmed_count = len(ri.confirmed_edges)
        unresolved_edges = ri.unresolved_edges
        unresolved_by_reason: dict[str, int] = {}
        for e in unresolved_edges:
            key = e.unresolved_reason or "unknown"
            unresolved_by_reason[key] = unresolved_by_reason.get(key, 0) + 1

        graph_confidence = (
            len(ri.confirmed_edges) / (len(ri.confirmed_edges) + len(unresolved_edges))
            if (ri.confirmed_edges or unresolved_edges) else 0.5
        )

        langs = ri.scan_metadata.languages_detected if ri.scan_metadata else {}

        return GraphSummaryResponse(
            total_files=ri.scan_metadata.total_files if ri.scan_metadata else 0,
            files_scanned=ri.scan_metadata.files_scanned if ri.scan_metadata else 0,
            entrypoints=entrypoints,
            critical_path_files=critical,
            critical_path_algorithm=ri.critical_path_algorithm,
            graph_semantics_version=ri.graph_semantics_version,
            graph_confidence=round(graph_confidence, 3),
            confirmed_edge_count=confirmed_count,
            unresolved_edge_count=len(unresolved_edges),
            unresolved_by_reason=unresolved_by_reason,
            languages=langs,
        )

    def _build_scorecard(self, scorecard, confidence: ConfidenceBreakdown | None) -> ScorecardResponse:
        dimensions = []
        for dim_name, dim_score in scorecard.dimension_scores.items():
            dimensions.append(DimensionScoreResponse(
                dimension=dim_name,
                score=dim_score.adjusted_score,
                label=dim_score.label,
                deductions=dim_score.deductions[:10],  # cap for response size
                finding_count=len(dim_score.finding_ids),
            ))

        # Sort dimensions by score ascending (worst first — most actionable)
        dimensions.sort(key=lambda d: d.score)

        conf_val = scorecard.confidence
        if conf_val >= 0.85:
            conf_label = "HIGH"
        elif conf_val >= 0.65:
            conf_label = "MODERATE"
        else:
            conf_label = "LOW"

        score_truth_label = TruthLabels.from_confidence_breakdown(
            confidence or ConfidenceBreakdown.compute(conf_val, conf_val, conf_val),
            scorecard.total_findings,
        )

        return ScorecardResponse(
            composite_score=scorecard.composite_score,
            composite_label=scorecard.composite_label,
            dimensions=dimensions,
            total_findings=scorecard.total_findings,
            findings_by_severity=scorecard.findings_by_severity,
            confidence=conf_val,
            confidence_label=conf_label,
            truth_label=score_truth_label.__dict__,
        )

    def _build_confidence_breakdown(
        self, cb: ConfidenceBreakdown | None
    ) -> dict[str, float]:
        if not cb:
            return {
                "extraction": 0.0,
                "graph": 0.0,
                "finding": 0.0,
                "score": 0.0,
            }
        return {
            "extraction": cb.extraction_confidence,
            "graph": cb.graph_confidence,
            "finding": cb.finding_confidence,
            "score": cb.score_confidence,
        }
