"""
app/api/routes/intelligence.py
--------------------------------
FastAPI route handlers for the deep intelligence layer.

These routes extend the existing Atlas API with:
  GET  /api/results/{result_id}/intelligence  — full report
  GET  /api/results/{result_id}/findings      — paginated findings list
  GET  /api/results/{result_id}/score         — scorecard only
  GET  /api/results/{result_id}/graph         — graph summary only
  GET  /api/results/{result_id}/files         — file list with truth labels
  GET  /api/results/{result_id}/edges         — dependency edges

All responses include truth labels. All scores include confidence context.

Integration with existing routes:
  The existing /api/analyze and /api/results/{id} routes remain unchanged.
  These new routes are additive — they read from the new intelligence tables.
"""

from __future__ import annotations

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db as _get_db

router = APIRouter(tags=["intelligence"])


# ---------------------------------------------------------------------------
# Pydantic response models (what the frontend receives)
# These are the serializable versions of the internal response dataclasses.
# ---------------------------------------------------------------------------

class TruthLabelOut(BaseModel):
    variant: str
    short: str
    detail: str
    limitation_ref: Optional[str] = None


class ConfidenceBreakdownOut(BaseModel):
    extraction: float
    graph: float
    finding: float
    score: float


class GraphSummaryOut(BaseModel):
    total_files: int
    files_scanned: int
    entrypoints: List[str]
    critical_path_files: List[str]
    critical_path_algorithm: str
    graph_semantics_version: int
    graph_confidence: float
    confirmed_edge_count: int
    unresolved_edge_count: int
    unresolved_by_reason: dict
    languages: dict


class DimensionScoreOut(BaseModel):
    dimension: str
    score: int
    label: str
    deductions: List[str]
    finding_count: int


class ScorecardOut(BaseModel):
    composite_score: int
    composite_label: str
    dimensions: List[DimensionScoreOut]
    total_findings: int
    findings_by_severity: dict
    confidence: float
    confidence_label: str
    truth_label: TruthLabelOut


class FindingOut(BaseModel):
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
    remediation: Optional[str] = None
    score_impact: int
    confidence: float


class FileOut(BaseModel):
    path: str
    language: str
    role: str
    is_entrypoint: bool
    is_on_critical_path: bool
    loc: int
    complexity_score: float
    caller_count: int
    sensitive_operations: List[str]
    confidence: float
    was_truncated: bool
    truth_label: TruthLabelOut


class EdgeOut(BaseModel):
    source_path: str
    target_path: Optional[str]
    raw_import: str
    kind: str
    confidence: str
    unresolved_reason: Optional[str] = None
    truth_label: TruthLabelOut


class IntelligenceReportOut(BaseModel):
    repo_url: str
    repo_owner: str
    repo_name: str
    schema_version: str
    graph_semantics_version: int
    graph: GraphSummaryOut
    scorecard: Optional[ScorecardOut]
    overall_confidence: float
    confidence_breakdown: ConfidenceBreakdownOut
    confidence_truth_label: TruthLabelOut
    scan_duration_seconds: float
    total_files_in_repo: int


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get(
    "/results/{result_id}/intelligence",
    response_model=IntelligenceReportOut,
    summary="Full intelligence report",
    description=(
        "Returns the complete analysis report including graph summary, "
        "scorecard, and confidence breakdown. Files, findings, and edges "
        "are available at their dedicated endpoints."
    ),
)
async def get_intelligence_report(
    result_id: str,
    db: AsyncSession = Depends(_get_db),
) -> IntelligenceReportOut:
    """
    Full intelligence report for a completed analysis job.

    This is the primary endpoint the frontend calls when rendering the
    results page. It excludes the full files/findings/edges lists to
    keep the response size manageable — those are loaded separately.
    """
    ri, scorecard = await _load_result(result_id, db)
    from app.services.report_builder import ReportBuilder
    builder = ReportBuilder()
    report = builder.build(ri, scorecard)
    return _report_to_out(report)


@router.get(
    "/results/{result_id}/score",
    response_model=Optional[ScorecardOut],
    summary="Production readiness scorecard",
    description=(
        "Returns the scorecard for this analysis. Every dimension score "
        "includes confidence context. Low confidence scores are clearly labelled."
    ),
)
async def get_scorecard(
    result_id: str,
    db: AsyncSession = Depends(_get_db),
) -> Optional[ScorecardOut]:
    ri, scorecard = await _load_result(result_id, db)
    if scorecard is None:
        raise HTTPException(404, detail="Scorecard not available for this result")
    from app.services.report_builder import ReportBuilder
    builder = ReportBuilder()
    report = builder.build(ri, scorecard)
    return _scorecard_to_out(report.scorecard)


@router.get(
    "/results/{result_id}/findings",
    response_model=List[FindingOut],
    summary="Code findings",
    description=(
        "Returns all non-suppressed findings for this analysis, "
        "sorted by severity (critical first). "
        "Each finding includes the exact evidence snippet and line numbers."
    ),
)
async def get_findings(
    result_id: str,
    severity: Optional[str] = Query(None, description="Filter by severity: critical|high|medium|low"),
    category: Optional[str] = Query(None, description="Filter by category"),
    file_path: Optional[str] = Query(None, description="Filter by file path prefix"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(_get_db),
) -> List[FindingOut]:
    ri, scorecard = await _load_result(result_id, db)
    from app.services.report_builder import ReportBuilder
    builder = ReportBuilder()
    report = builder.build(ri, scorecard)

    findings = report.findings
    if severity:
        findings = [f for f in findings if f.severity == severity]
    if category:
        findings = [f for f in findings if f.category == category]
    if file_path:
        findings = [f for f in findings if f.file_path.startswith(file_path)]

    paginated = findings[offset:offset + limit]
    return [_finding_to_out(f) for f in paginated]


@router.get(
    "/results/{result_id}/graph",
    response_model=GraphSummaryOut,
    summary="Dependency graph summary",
    description=(
        "Returns the graph topology summary including entrypoints, "
        "critical path files, edge counts, and confidence breakdown. "
        "The full edge list is at /edges."
    ),
)
async def get_graph_summary(
    result_id: str,
    db: AsyncSession = Depends(_get_db),
) -> GraphSummaryOut:
    ri, scorecard = await _load_result(result_id, db)
    from app.services.report_builder import ReportBuilder
    builder = ReportBuilder()
    report = builder.build(ri, scorecard)
    return _graph_to_out(report.graph)


@router.get(
    "/results/{result_id}/files",
    response_model=List[FileOut],
    summary="Scanned files with truth labels",
    description=(
        "Returns all scanned files sorted by importance (entrypoints first, "
        "then critical path, then rest). Each file includes its truth label "
        "indicating how it was classified."
    ),
)
async def get_files(
    result_id: str,
    critical_only: bool = Query(False, description="Return only critical path files"),
    role: Optional[str] = Query(None, description="Filter by role: entrypoint|service|module|test|..."),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(_get_db),
) -> List[FileOut]:
    ri, scorecard = await _load_result(result_id, db)
    from app.services.report_builder import ReportBuilder
    builder = ReportBuilder()
    report = builder.build(ri, scorecard)

    files = report.files
    if critical_only:
        files = [f for f in files if f.is_on_critical_path]
    if role:
        files = [f for f in files if f.role == role]

    paginated = files[offset:offset + limit]
    return [_file_to_out(f) for f in paginated]


@router.get(
    "/results/{result_id}/edges",
    response_model=List[EdgeOut],
    summary="Dependency edges",
    description=(
        "Returns all dependency edges (confirmed and unresolved). "
        "Unresolved edges include a reason code and truth label explaining "
        "why the import could not be resolved."
    ),
)
async def get_edges(
    result_id: str,
    confidence: Optional[str] = Query(None, description="Filter by confidence: confirmed|unresolved"),
    reason: Optional[str] = Query(None, description="Filter unresolved by reason code"),
    limit: int = Query(500, ge=1, le=5000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(_get_db),
) -> List[EdgeOut]:
    ri, scorecard = await _load_result(result_id, db)
    from app.services.report_builder import ReportBuilder
    builder = ReportBuilder()
    report = builder.build(ri, scorecard)

    edges = report.edges
    if confidence:
        edges = [e for e in edges if e.confidence == confidence]
    if reason:
        edges = [e for e in edges if e.unresolved_reason == reason]

    paginated = edges[offset:offset + limit]
    return [_edge_to_out(e) for e in paginated]


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------

def _truth_label_to_out(label_dict: dict) -> TruthLabelOut:
    return TruthLabelOut(
        variant=label_dict["variant"],
        short=label_dict["short"],
        detail=label_dict["detail"],
        limitation_ref=label_dict.get("limitation_ref"),
    )


def _report_to_out(report) -> IntelligenceReportOut:
    return IntelligenceReportOut(
        repo_url=report.repo_url,
        repo_owner=report.repo_owner,
        repo_name=report.repo_name,
        schema_version=report.schema_version,
        graph_semantics_version=report.graph_semantics_version,
        graph=_graph_to_out(report.graph),
        scorecard=_scorecard_to_out(report.scorecard) if report.scorecard else None,
        overall_confidence=report.overall_confidence,
        confidence_breakdown=ConfidenceBreakdownOut(**report.confidence_breakdown),
        confidence_truth_label=_truth_label_to_out(report.confidence_truth_label),
        scan_duration_seconds=report.scan_duration_seconds,
        total_files_in_repo=report.total_files_in_repo,
    )


def _graph_to_out(graph) -> GraphSummaryOut:
    return GraphSummaryOut(
        total_files=graph.total_files,
        files_scanned=graph.files_scanned,
        entrypoints=graph.entrypoints,
        critical_path_files=graph.critical_path_files,
        critical_path_algorithm=graph.critical_path_algorithm,
        graph_semantics_version=graph.graph_semantics_version,
        graph_confidence=graph.graph_confidence,
        confirmed_edge_count=graph.confirmed_edge_count,
        unresolved_edge_count=graph.unresolved_edge_count,
        unresolved_by_reason=graph.unresolved_by_reason,
        languages=graph.languages,
    )


def _scorecard_to_out(scorecard) -> Optional[ScorecardOut]:
    if scorecard is None:
        return None
    return ScorecardOut(
        composite_score=scorecard.composite_score,
        composite_label=scorecard.composite_label,
        dimensions=[
            DimensionScoreOut(
                dimension=d.dimension,
                score=d.score,
                label=d.label,
                deductions=d.deductions,
                finding_count=d.finding_count,
            )
            for d in scorecard.dimensions
        ],
        total_findings=scorecard.total_findings,
        findings_by_severity=scorecard.findings_by_severity,
        confidence=scorecard.confidence,
        confidence_label=scorecard.confidence_label,
        truth_label=_truth_label_to_out(scorecard.truth_label),
    )


def _finding_to_out(f) -> FindingOut:
    return FindingOut(
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
    )


def _file_to_out(f) -> FileOut:
    return FileOut(
        path=f.path,
        language=f.language,
        role=f.role,
        is_entrypoint=f.is_entrypoint,
        is_on_critical_path=f.is_on_critical_path,
        loc=f.loc,
        complexity_score=f.complexity_score,
        caller_count=f.caller_count,
        sensitive_operations=f.sensitive_operations,
        confidence=f.confidence,
        was_truncated=f.was_truncated,
        truth_label=_truth_label_to_out(f.truth_label),
    )


def _edge_to_out(e) -> EdgeOut:
    return EdgeOut(
        source_path=e.source_path,
        target_path=e.target_path,
        raw_import=e.raw_import,
        kind=e.kind,
        confidence=e.confidence,
        unresolved_reason=e.unresolved_reason,
        truth_label=_truth_label_to_out(e.truth_label),
    )


# ---------------------------------------------------------------------------
# DB dependency + result loader
# ---------------------------------------------------------------------------

async def _load_result(result_id: str, db: AsyncSession):
    """
    Load RepoIntelligence + ProductionScore from the intelligence tables.
    Raises 404 if no data has been persisted for this result yet.
    """
    from app.services.intelligence_persistence import load_intelligence

    try:
        result_id_int = int(result_id)
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail="result_id must be an integer")

    try:
        return await load_intelligence(result_id_int, db)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
