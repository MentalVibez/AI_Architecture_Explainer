"""
app/services/intelligence_persistence.py
-----------------------------------------
Saves a completed PipelineResult to the five intelligence DB tables.
Called from routes_analysis.run_analysis_job() after AnalysisResult is committed.

Also provides _load_result() for reconstructing RepoIntelligence + ProductionScore
from those rows — used by the intelligence API endpoints.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

async def persist_intelligence(
    result_id: int,
    repo_url: str,
    repo_owner: str,
    repo_name: str,
    intel_result: Any,  # PipelineResult
    db: AsyncSession,
) -> None:
    """
    Persist all intelligence data for a completed analysis result.

    Silently skips on any error so a persistence failure never breaks
    the main analysis job. Logs a warning instead.
    """
    from app.models.intelligence import (
        CodeFindingORM,
        DependencyEdgeORM,
        DimensionScoreORM,
        FileIntelligenceORM,
        ProductionScoreORM,
    )

    try:
        ri = intel_result.intelligence
        scorecard = intel_result.scorecard

        # --- FileIntelligence rows ---
        for fi in ri.files:
            row = FileIntelligenceORM(
                result_id=result_id,
                path=fi.path,
                language=fi.language,
                role=fi.role,
                is_entrypoint=fi.is_entrypoint,
                is_test=fi.is_test,
                is_on_critical_path=(
                    ri.contexts.get(fi.path).is_on_critical_path
                    if ri.contexts.get(fi.path) else False
                ),
                loc=fi.loc,
                complexity_score=fi.complexity_score,
                function_count=fi.function_count,
                caller_count=(
                    ri.contexts.get(fi.path).caller_count
                    if ri.contexts.get(fi.path) else 0
                ),
                has_type_annotations=fi.has_type_annotations,
                has_error_handling=fi.has_error_handling,
                was_truncated=fi.was_truncated,
                confidence=fi.confidence,
                sensitive_operations=",".join(fi.sensitive_operations),
                framework_signals=",".join(fi.framework_signals),
            )
            db.add(row)

        # --- DependencyEdge rows ---
        for edge in ri.edges:
            row = DependencyEdgeORM(
                result_id=result_id,
                source_path=edge.source_path,
                target_path=edge.target_path,
                raw_import=edge.raw_import,
                kind=edge.kind,
                confidence=edge.confidence,
                unresolved_reason=edge.unresolved_reason,
            )
            db.add(row)

        # --- CodeFinding rows (non-suppressed only) ---
        for finding in ri.findings:
            if getattr(finding, "is_suppressed", False):
                continue
            row = CodeFindingORM(
                id=finding.id,
                result_id=result_id,
                file_path=finding.file_path,
                category=finding.category,
                severity=finding.severity,
                source=finding.source,
                line_start=finding.line_start,
                line_end=finding.line_end,
                evidence_snippet=finding.evidence_snippet[:500],
                title=finding.title,
                explanation=finding.explanation,
                remediation=getattr(finding, "remediation", None),
                score_impact=getattr(finding, "score_impact", 0),
                confidence=getattr(finding, "confidence", 1.0),
            )
            db.add(row)

        await db.flush()  # get file_intelligence rows in DB before scorecard

        # --- ProductionScore + DimensionScore rows ---
        if scorecard is not None:
            cb = ri.confidence
            sev_counts = getattr(scorecard, "findings_by_severity", {})

            score_row = ProductionScoreORM(
                result_id=result_id,
                composite_score=scorecard.composite_score,
                composite_label=scorecard.composite_label,
                confidence_extraction=cb.extraction_confidence if cb else 0.0,
                confidence_graph=cb.graph_confidence if cb else 0.0,
                confidence_finding=cb.finding_confidence if cb else 0.0,
                confidence_score=cb.score_confidence if cb else 0.0,
                critical_count=sev_counts.get("critical", 0),
                high_count=sev_counts.get("high", 0),
                medium_count=sev_counts.get("medium", 0),
                low_count=sev_counts.get("low", 0),
                total_findings=scorecard.total_findings,
                graph_semantics_version=ri.graph_semantics_version,
                critical_path_algorithm=ri.critical_path_algorithm,
                graph_confidence=ri.overall_confidence,
                confirmed_edge_count=len(ri.confirmed_edges),
                unresolved_edge_count=len(ri.unresolved_edges),
                overall_confidence=ri.overall_confidence,
                repo_url=repo_url,
                repo_owner=repo_owner,
                repo_name=repo_name,
            )
            db.add(score_row)
            await db.flush()  # get score_row.id

            for dim_name, dim_score in scorecard.dimension_scores.items():
                dim_row = DimensionScoreORM(
                    score_id=score_row.id,
                    dimension=dim_name,
                    raw_score=dim_score.raw_score,
                    adjusted_score=dim_score.adjusted_score,
                    label=dim_score.label,
                    finding_count=len(getattr(dim_score, "finding_ids", [])),
                    deductions_text="\n".join(
                        getattr(dim_score, "deductions", [])
                    ),
                )
                db.add(dim_row)

        await db.commit()
        logger.info("Intelligence persisted for result_id=%d", result_id)

    except Exception:
        await db.rollback()
        logger.warning(
            "Failed to persist intelligence for result_id=%d — skipping",
            result_id,
            exc_info=True,
        )


# ---------------------------------------------------------------------------
# Load (Option B — reconstruct RepoIntelligence from DB rows)
# ---------------------------------------------------------------------------

async def load_intelligence(
    result_id: int,
    db: AsyncSession,
) -> Tuple[Any, Any]:
    """
    Load RepoIntelligence + ProductionScore from the five intelligence tables.

    Returns (RepoIntelligence, ProductionScore | None).
    Raises ValueError if result_id has no intelligence data yet.
    """
    from app.models.intelligence import (
        CodeFindingORM,
        DependencyEdgeORM,
        DimensionScoreORM,
        FileIntelligenceORM,
        ProductionScoreORM,
    )
    from app.schemas.intelligence import (
        CRITICAL_PATH_ALGORITHM,
        GRAPH_SEMANTICS_VERSION,
        SCHEMA_VERSION,
        CodeContext,
        CodeFinding,
        ConfidenceBreakdown,
        DependencyEdge,
        FileIntelligence,
        RepoIntelligence,
        ScanMetadata,
    )

    # --- Load file intelligence rows ---
    file_rows: List[FileIntelligenceORM] = (
        await db.execute(
            select(FileIntelligenceORM).where(FileIntelligenceORM.result_id == result_id)
        )
    ).scalars().all()

    if not file_rows:
        raise ValueError(f"No intelligence data for result_id={result_id}")

    # --- Load dependency edge rows ---
    edge_rows: List[DependencyEdgeORM] = (
        await db.execute(
            select(DependencyEdgeORM).where(DependencyEdgeORM.result_id == result_id)
        )
    ).scalars().all()

    # --- Load finding rows ---
    finding_rows: List[CodeFindingORM] = (
        await db.execute(
            select(CodeFindingORM).where(CodeFindingORM.result_id == result_id)
        )
    ).scalars().all()

    # --- Load scorecard (eager-loads dimension_scores via selectin) ---
    score_row: Optional[ProductionScoreORM] = (
        await db.execute(
            select(ProductionScoreORM).where(ProductionScoreORM.result_id == result_id)
        )
    ).scalar_one_or_none()

    # --- Reconstruct FileIntelligence objects ---
    files = []
    contexts: Dict[str, CodeContext] = {}

    for row in file_rows:
        fi = FileIntelligence(
            path=row.path,
            language=row.language,
            role=row.role,
            is_entrypoint=row.is_entrypoint,
            is_test=row.is_test,
            loc=row.loc,
            complexity_score=row.complexity_score,
            function_count=row.function_count,
            has_type_annotations=row.has_type_annotations,
            has_error_handling=row.has_error_handling,
            was_truncated=row.was_truncated,
            confidence=row.confidence,
            sensitive_operations=(
                [s for s in row.sensitive_operations.split(",") if s]
                if row.sensitive_operations else []
            ),
            framework_signals=(
                [s for s in row.framework_signals.split(",") if s]
                if row.framework_signals else []
            ),
        )
        files.append(fi)

        contexts[row.path] = CodeContext(
            is_on_critical_path=row.is_on_critical_path,
            caller_count=row.caller_count,
        )

    # --- Reconstruct DependencyEdge objects ---
    edges = []
    for row in edge_rows:
        edge = DependencyEdge(
            source_path=row.source_path,
            target_path=row.target_path,
            raw_import=row.raw_import,
            kind=row.kind,
            confidence=row.confidence,
            unresolved_reason=row.unresolved_reason,
        )
        edges.append(edge)

    # --- Reconstruct CodeFinding objects ---
    findings = []
    for row in finding_rows:
        finding = CodeFinding(
            id=row.id,
            file_path=row.file_path,
            category=row.category,
            severity=row.severity,
            source=row.source,
            line_start=row.line_start,
            line_end=row.line_end,
            evidence_snippet=row.evidence_snippet,
            title=row.title,
            explanation=row.explanation,
            remediation=row.remediation,
            score_impact=row.score_impact,
            confidence=row.confidence,
        )
        findings.append(finding)

    # --- Reconstruct ConfidenceBreakdown ---
    confidence = None
    if score_row:
        confidence = ConfidenceBreakdown(
            extraction_confidence=score_row.confidence_extraction,
            graph_confidence=score_row.confidence_graph,
            finding_confidence=score_row.confidence_finding,
            score_confidence=score_row.confidence_score,
        )

    # --- Reconstruct ScanMetadata ---
    scan_metadata = ScanMetadata(
        total_files=len(file_rows),
        files_scanned=len(file_rows),
        parse_success_rate=(
            sum(r.confidence for r in file_rows) / len(file_rows) if file_rows else 1.0
        ),
        languages_detected={},
        scan_duration_seconds=0.0,
    )

    # --- Assemble RepoIntelligence ---
    repo_url = score_row.repo_url if score_row and score_row.repo_url else ""
    repo_owner = score_row.repo_owner if score_row and score_row.repo_owner else ""
    repo_name = score_row.repo_name if score_row and score_row.repo_name else ""

    ri = RepoIntelligence(
        repo_url=repo_url,
        repo_owner=repo_owner,
        repo_name=repo_name,
        schema_version=SCHEMA_VERSION,
        graph_semantics_version=GRAPH_SEMANTICS_VERSION,
        critical_path_algorithm=CRITICAL_PATH_ALGORITHM,
        files=files,
        contexts=contexts,
        edges=edges,
        findings=findings,
        scan_metadata=scan_metadata,
        confidence=confidence,
    )

    # --- Reconstruct ProductionScore ---
    scorecard = None
    if score_row is not None:
        from app.services.scorecard import DimensionScore, ProductionScore

        dimension_scores: Dict[str, DimensionScore] = {}
        for dim_row in score_row.dimension_scores:
            deductions = (
                [d for d in dim_row.deductions_text.split("\n") if d]
                if dim_row.deductions_text else []
            )
            dimension_scores[dim_row.dimension] = DimensionScore(
                dimension=dim_row.dimension,
                raw_score=dim_row.raw_score,
                adjusted_score=dim_row.adjusted_score,
                base=100,
                deductions=deductions,
                finding_ids=[],
                explanation=f"{dim_row.label} ({dim_row.adjusted_score}/100)",
            )

        sev_counts = {
            "critical": score_row.critical_count,
            "high": score_row.high_count,
            "medium": score_row.medium_count,
            "low": score_row.low_count,
        }
        scorecard = ProductionScore(
            dimension_scores=dimension_scores,
            composite_score=score_row.composite_score,
            composite_label=score_row.composite_label,
            confidence=score_row.confidence_score,
            confidence_explanation="Loaded from DB",
            total_findings=score_row.total_findings,
            findings_by_severity=sev_counts,
        )

    return ri, scorecard
