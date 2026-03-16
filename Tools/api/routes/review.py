from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import tempfile, subprocess

from ...facts.builder import build_facts
from ...engine.registry import build_default_registry
from ...engine.executor import execute
from ...engine.dedupe import deduplicate
from ...engine.coverage import build_coverage
from ...engine.confidence import compute_confidence_badge
from ...engine.depth import compute_depth
from ...engine.anti_gaming import build_anti_gaming_block
from ...engine.readiness import why_not_production_suitable, what_would_flip_verdict
from ...scoring.engine import compute_scorecard, compute_overall
from ...scoring.interpretation import interpret_report
from ...models.report import ReviewReport, RepoMeta, ScoreInterpretation, ReviewMeta, AnalysisDepthInfo
from ...exports.json_exporter import export as export_json
from ...exports.markdown_exporter import export as export_markdown

router = APIRouter(prefix="/review", tags=["review"])
RULESET_VERSION = "2026.03"
SCHEMA_VERSION  = "1.0"


class ReviewRequest(BaseModel):
    repo_url: str
    branch: str = "main"
    export_format: str = "json"


@router.post("/")
async def review_repo(req: ReviewRequest):
    try:
        with tempfile.TemporaryDirectory() as tmp:
            clone = subprocess.run(
                ["git", "clone", "--depth", "1", "--branch", req.branch, req.repo_url, tmp],
                capture_output=True, text=True, timeout=120,
            )
            if clone.returncode != 0:
                raise HTTPException(status_code=400, detail=f"Clone failed: {clone.stderr}")

            commit = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd=tmp, capture_output=True, text=True,
            ).stdout.strip()

            facts, adapter_results = build_facts(repo_url=req.repo_url, repo_path=tmp, commit=commit)

            registry = build_default_registry()
            applicable = registry.for_facts(facts)
            raw_findings = execute(registry, facts)
            findings = deduplicate(raw_findings)

            confidence = compute_confidence_badge(facts, adapter_results, len(applicable), len(registry.all()))
            depth_profile = compute_depth(confidence.adapters_succeeded, confidence.adapters_failed)

            # Depth-aware scoring — caps applied based on what was actually measured
            scorecard = compute_scorecard(findings, depth=depth_profile.level)
            overall = compute_overall(scorecard)

            coverage = build_coverage(facts, adapter_results, tmp)
            interpreted = interpret_report(scorecard, overall, findings)
            anti_gaming = build_anti_gaming_block(findings, scorecard)

            interpretation = ScoreInterpretation(
                overall_label=interpreted.overall_band.label,
                trust_recommendation=interpreted.trust_recommendation,
                color_hint=interpreted.overall_band.color_hint,
                production_suitable=interpreted.production_suitable,
                top_concern=interpreted.top_concern,
                developer_meaning=interpreted.overall_band.developer_meaning,
                manager_meaning=interpreted.overall_band.manager_meaning,
                hiring_meaning=interpreted.overall_band.hiring_meaning,
                category_interpretations=interpreted.category_interpretations,
            )

            depth_info = AnalysisDepthInfo(
                level=depth_profile.level.value,
                label=depth_profile.label,
                description=depth_profile.description,
                verdict_note=depth_profile.verdict_note,
                adapters_succeeded=confidence.adapters_succeeded,
                allowed_strong_claims=depth_profile.allowed_strong_claims,
            )

            meta = ReviewMeta(
                ruleset_version=RULESET_VERSION,
                schema_version=SCHEMA_VERSION,
                applicable_rule_count=len(applicable),
                executed_rule_count=len(applicable),
                adapters_run=list(adapter_results.keys()),
                overall_score=overall,
                confidence_label=confidence.label,
                confidence_score=confidence.score,
                confidence_rationale=confidence.rationale,
            )

            sorted_findings = sorted(
                findings,
                key=lambda f: ["critical","high","medium","low","info"].index(f.severity),
            )

            report = ReviewReport(
                schema_version=SCHEMA_VERSION,
                ruleset_version=RULESET_VERSION,
                repo=RepoMeta(url=req.repo_url, commit=commit,
                              primary_languages=facts.languages.primary),
                coverage=coverage,
                depth=depth_info,
                scorecard=scorecard,
                interpretation=interpretation,
                meta=meta,
                findings=sorted_findings,
                anti_gaming=anti_gaming,
                priority_actions=[
                    f.suggested_fix for f in sorted_findings
                    if f.severity in ("critical", "high")
                ][:5],
            )

            if req.export_format == "markdown":
                return {"format": "markdown", "content": export_markdown(report)}
            return {
                "format": "json",
                "overall_score": overall,
                "analysis_depth": depth_info.label,
                "report": report.model_dump(),
            }

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
