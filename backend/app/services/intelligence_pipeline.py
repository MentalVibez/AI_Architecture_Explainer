"""
app/services/pipeline.py
---------------------
IntelligencePipeline: The top-level orchestrator.

Sequence:
  1. DeepScanner  — deterministic file extraction (no LLM)
  2. ContextReviewer — evidence-gated findings (LLM conditional)
  3. Scorecard    — evidence-backed scoring (no LLM)
  4. RepoIntelligence — aggregate result with confidence breakdown

This is the single entry point for a full analysis job.
The API layer calls pipeline.run() and gets back RepoIntelligence.
Nothing else in the API layer talks to the individual services directly.

Rules:
  - Every stage is independently failable with partial results returned
  - Timeouts at each stage — never let one slow repo hang the queue
  - Confidence degrades honestly when stages fail or return partial data
  - LLM is never called with unvetted data
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field

from app.schemas.intelligence import (
    CRITICAL_PATH_ALGORITHM,
    GRAPH_SEMANTICS_VERSION,
    SCHEMA_VERSION,
    ConfidenceBreakdown,
    RepoIntelligence,
    UITruthLabel,
)

logger = logging.getLogger(__name__)

# Stage timeouts — a single stage exceeding these returns partial results
DEEP_SCAN_TIMEOUT_SECONDS = 120
REVIEW_TIMEOUT_SECONDS = 180
SCORECARD_TIMEOUT_SECONDS = 30


@dataclass
class PipelineConfig:
    """Runtime configuration for a single pipeline execution."""
    # GitHub access
    github_token: str | None = None
    # Anthropic access — required for ContextReviewer LLM stage
    anthropic_api_key: str | None = None
    # LLM model to use for reviews
    llm_model: str = "claude-sonnet-4-6"
    # Whether to run LLM review at all
    enable_llm_review: bool = True
    # Max files to scan (hard ceiling from HARD_MAX_FILES in deep_scanner)
    max_files: int = 500
    # Stage timeouts (seconds)
    scan_timeout: float = DEEP_SCAN_TIMEOUT_SECONDS
    review_timeout: float = REVIEW_TIMEOUT_SECONDS
    # TypeScript path aliases (if known ahead of time)
    ts_aliases: dict[str, str] | None = None


@dataclass
class PipelineResult:
    """
    The output of a full pipeline run.
    Always returned — even if stages fail, partial results are included.
    """
    intelligence: RepoIntelligence
    scorecard: object | None = None  # ProductionScore from scorecard.py
    stage_timings: dict[str, float] = field(default_factory=dict)
    stage_errors: dict[str, str] = field(default_factory=dict)
    total_duration_seconds: float = 0.0

    @property
    def succeeded(self) -> bool:
        """True if no stages failed with unrecoverable errors."""
        return len(self.stage_errors) == 0

    @property
    def confidence_label(self) -> UITruthLabel:
        return self.intelligence.ui_confidence_label()


class IntelligencePipeline:
    """
    Orchestrates the full analysis pipeline for a single repository.

    Usage:
        config = PipelineConfig(
            github_token="ghp_...",
            anthropic_api_key="sk-ant-...",
        )
        pipeline = IntelligencePipeline(config)
        result = await pipeline.run(
            repo_url="https://github.com/owner/repo",
            file_tree=[...],  # from GitHub API
        )
        ri = result.intelligence
    """

    def __init__(self, config: PipelineConfig):
        self.config = config
        self._init_services()

    def _init_services(self) -> None:
        """Lazy import services to avoid circular deps and allow testing."""
        from app.services.context_reviewer import ContextReviewer
        from app.services.deep_scanner import DeepScanner
        from app.services.scorecard import build_scorecard

        self._scanner = DeepScanner(github_token=self.config.github_token)
        self._reviewer = ContextReviewer(
            anthropic_api_key=self.config.anthropic_api_key or "",
            model=self.config.llm_model,
            enable_llm=self.config.enable_llm_review and bool(self.config.anthropic_api_key),
        )
        self._build_scorecard = build_scorecard

    async def run(
        self,
        repo_url: str,
        file_tree: list[dict],
        ref: str = "HEAD",
    ) -> PipelineResult:
        """
        Execute the full pipeline. Returns partial results on stage failure.

        Stages:
          1. deep_scan   — file extraction, graph building
          2. review      — deterministic + conditional LLM findings
          3. scorecard   — evidence-backed scoring
        """
        start = time.monotonic()
        timings: dict[str, float] = {}
        errors: dict[str, str] = {}

        # Parse repo URL into owner/name
        owner, name = _parse_repo_url(repo_url)

        # ---------------------------------------------------------------
        # Stage 1: DeepScan
        # ---------------------------------------------------------------
        scan_result = None
        t0 = time.monotonic()
        try:
            scan_result = await asyncio.wait_for(
                self._scanner.scan(
                    owner=owner,
                    repo=name,
                    file_tree=file_tree,
                    ref=ref,
                    max_files=self.config.max_files,
                ),
                timeout=self.config.scan_timeout,
            )
            timings["deep_scan"] = round(time.monotonic() - t0, 2)
            logger.info(
                f"DeepScan complete: {scan_result.scan_metadata.files_scanned} files, "
                f"gc={scan_result.graph_confidence:.3f}"
            )
        except TimeoutError:
            timings["deep_scan"] = round(time.monotonic() - t0, 2)
            errors["deep_scan"] = f"Timeout after {self.config.scan_timeout}s"
            logger.error(f"DeepScan timed out for {repo_url}")
        except Exception as e:
            timings["deep_scan"] = round(time.monotonic() - t0, 2)
            errors["deep_scan"] = f"{type(e).__name__}: {e}"
            logger.error(f"DeepScan failed for {repo_url}: {e}", exc_info=True)

        if scan_result is None:
            # Cannot proceed without scan results — return empty intelligence
            return self._empty_result(repo_url, owner, name, timings, errors, start)

        # ---------------------------------------------------------------
        # Stage 2: ContextReview
        # ---------------------------------------------------------------
        findings = []
        t0 = time.monotonic()
        try:
            repo_summary = _build_repo_summary(scan_result)
            findings = await asyncio.wait_for(
                self._reviewer.review_repo(
                    files=scan_result.files,
                    contexts=scan_result.contexts,
                    file_contents=scan_result.contents,
                    repo_summary=repo_summary,
                ),
                timeout=self.config.review_timeout,
            )
            timings["review"] = round(time.monotonic() - t0, 2)
            logger.info(f"Review complete: {len(findings)} findings")
        except TimeoutError:
            timings["review"] = round(time.monotonic() - t0, 2)
            errors["review"] = f"Timeout after {self.config.review_timeout}s"
            logger.warning("Review timed out — proceeding with empty findings")
        except Exception as e:
            timings["review"] = round(time.monotonic() - t0, 2)
            errors["review"] = f"{type(e).__name__}: {e}"
            logger.error(f"Review failed for {repo_url}: {e}", exc_info=True)

        # ---------------------------------------------------------------
        # Stage 3: Scorecard
        # ---------------------------------------------------------------
        score = None
        t0 = time.monotonic()
        try:
            score = self._build_scorecard(
                findings=findings,
                files=scan_result.files,
                scan_metadata=scan_result.scan_metadata,
            )
            timings["scorecard"] = round(time.monotonic() - t0, 3)
            logger.info(
                f"Scorecard complete: {score.composite_score}/100 "
                f"({score.composite_label}), confidence={score.confidence:.3f}"
            )
        except Exception as e:
            timings["scorecard"] = round(time.monotonic() - t0, 3)
            errors["scorecard"] = f"{type(e).__name__}: {e}"
            logger.error(f"Scorecard failed for {repo_url}: {e}", exc_info=True)

        # ---------------------------------------------------------------
        # Assemble RepoIntelligence
        # ---------------------------------------------------------------
        extraction_confidence = (
            sum(f.confidence for f in scan_result.files) / len(scan_result.files)
            if scan_result.files else 0.0
        )
        finding_confidence = (
            sum(f.confidence for f in findings) / len(findings)
            if findings else 1.0
        )
        confidence_breakdown = ConfidenceBreakdown.compute(
            extraction=round(extraction_confidence, 3),
            graph=scan_result.graph_confidence,
            finding=round(finding_confidence, 3),
        )

        ri = RepoIntelligence(
            repo_url=repo_url,
            repo_owner=owner,
            repo_name=name,
            default_branch=ref,
            schema_version=SCHEMA_VERSION,
            graph_semantics_version=GRAPH_SEMANTICS_VERSION,
            critical_path_algorithm=CRITICAL_PATH_ALGORITHM,
            files=scan_result.files,
            contexts=scan_result.contexts,
            edges=scan_result.edges,
            findings=findings,
            scan_metadata=scan_result.scan_metadata,
            confidence=confidence_breakdown,
        )

        total = round(time.monotonic() - start, 2)
        logger.info(
            f"Pipeline complete for {repo_url}: "
            f"{total}s, score={score.composite_score if score else 'N/A'}, "
            f"confidence={confidence_breakdown.score_confidence:.3f}"
        )

        return PipelineResult(
            intelligence=ri,
            scorecard=score,
            stage_timings=timings,
            stage_errors=errors,
            total_duration_seconds=total,
        )

    def _empty_result(
        self,
        repo_url: str,
        owner: str,
        name: str,
        timings: dict[str, float],
        errors: dict[str, str],
        start: float,
    ) -> PipelineResult:
        """Minimal result when the scan stage itself fails."""
        ri = RepoIntelligence(
            repo_url=repo_url,
            repo_owner=owner,
            repo_name=name,
            default_branch="HEAD",
            confidence=ConfidenceBreakdown.compute(0.0, 0.0, 0.0),
        )
        return PipelineResult(
            intelligence=ri,
            stage_timings=timings,
            stage_errors=errors,
            total_duration_seconds=round(time.monotonic() - start, 2),
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_repo_url(repo_url: str) -> tuple[str, str]:
    """
    Parse 'https://github.com/owner/name' or 'owner/name' → (owner, name).
    Raises ValueError on unrecognisable format.
    """
    url = repo_url.strip().rstrip("/")
    # Strip protocol and host
    for prefix in ("https://github.com/", "http://github.com/", "github.com/"):
        if url.startswith(prefix):
            url = url[len(prefix):]
            break
    parts = url.split("/")
    if len(parts) < 2:
        raise ValueError(f"Cannot parse repo URL: {repo_url!r}")
    return parts[0], parts[1]


def _build_repo_summary(scan_result) -> dict:
    """
    Build the structured summary passed to ContextReviewer.
    This is what the LLM sees about the repo — it must be facts, not guesses.
    """
    from collections import Counter

    # Primary language by file count
    lang_counts = Counter(f.language for f in scan_result.files if f.language != "unknown")
    primary_language = lang_counts.most_common(1)[0][0] if lang_counts else "unknown"

    # Aggregate framework signals
    all_signals: list = []
    for fi in scan_result.files:
        all_signals.extend(fi.framework_signals)
    top_signals = [s for s, _ in Counter(all_signals).most_common(10)]

    # Entrypoints
    entrypoints = [f.path for f in scan_result.files if f.is_entrypoint]

    # High-risk files (have sensitive operations)
    high_risk = [f.path for f in scan_result.files if f.sensitive_operations]

    return {
        "primary_language": primary_language,
        "framework_signals": top_signals,
        "total_files": scan_result.scan_metadata.total_files,
        "files_scanned": scan_result.scan_metadata.files_scanned,
        "entrypoints": entrypoints[:5],
        "high_risk_files": high_risk[:10],
        "graph_confidence": scan_result.graph_confidence,
        "languages_detected": scan_result.scan_metadata.languages_detected,
    }
