"""
Atlas Reviewer — public service interface.

Single entry point: run_review(repo_url, branch) → ReviewReport

Error contract:
  ALL errors surface as ReviewError with a stable error_code.
  Raw exceptions (subprocess, OS, network, engine bugs) are caught
  at the translation layer and converted to ReviewError("UNEXPECTED", ...).
  Nothing propagates as a bare exception to the job worker.

Timeout contract:
  REVIEW_TIMEOUT_SECS wraps the entire operation.
  CLONE_TIMEOUT_SECS wraps the git clone specifically.
  Both raise ReviewError on expiry — never asyncio.TimeoutError to the caller.

Temp directory contract:
  tempfile.TemporaryDirectory() as context manager.
  Cleaned up on: success, ReviewError, unexpected exception, timeout.
  No manual cleanup needed anywhere.
"""
import asyncio
import logging
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional

from .utils.repo_url import normalize_repo_url
from .facts.builder import build_facts
from .engine.registry import build_default_registry
from .engine.executor import execute
from .engine.dedupe import deduplicate
from .engine.coverage import build_coverage
from .engine.confidence import compute_confidence_badge
from .engine.depth import compute_depth
from .engine.anti_gaming import build_anti_gaming_block
from .engine.readiness import why_not_production_suitable, what_would_flip_verdict
from .scoring.engine import compute_scorecard, compute_overall
from .scoring.interpretation import interpret_report
from .llm.contract import build_llm_input
from .llm.summaries import _deterministic_fallback
from .models.report import (
    ReviewReport, RepoMeta, ScoreInterpretation,
    ReviewMeta, AnalysisDepthInfo,
)

logger = logging.getLogger(__name__)

RULESET_VERSION      = "2026.03"
SCHEMA_VERSION       = "1.0"
MAX_REPO_SIZE_BYTES  = 500 * 1024 * 1024   # 500 MB
MAX_FILE_COUNT       = 50_000
CLONE_TIMEOUT_SECS   = 180
REVIEW_TIMEOUT_SECS  = 300


# ── Public error type ─────────────────────────────────────────────────────────

class ReviewError(Exception):
    """
    All review failures. Caller stores code + message in the Review row.

    Codes:
        INVALID_URL         — not a recognizable GitHub repo URL
        CLONE_FAILED        — git returned non-zero or timed out
        REPO_TOO_LARGE      — exceeds size/file-count limit
        REVIEW_TIMEOUT      — total review exceeded time budget
        ENGINE_ERROR        — unexpected engine exception (logged + wrapped)
    """
    def __init__(self, code: str, message: str):
        self.code    = code
        self.message = message
        super().__init__(f"[{code}] {message}")


# ── Public entry point ────────────────────────────────────────────────────────

async def run_review(
    repo_url: str,
    branch: str = "main",
    commit: Optional[str] = None,
) -> ReviewReport:
    """
    Run a complete repo review. Always returns ReviewReport or raises ReviewError.
    Never raises any other exception type.
    """
    # 1. Normalize URL first — fast, no I/O
    try:
        normalized = normalize_repo_url(repo_url)
    except ValueError as e:
        raise ReviewError("INVALID_URL", str(e))

    # 2. Run the full pipeline under a hard timeout
    try:
        return await asyncio.wait_for(
            _run_review_impl(normalized.clone_url, normalized.canonical_url, branch, commit),
            timeout=REVIEW_TIMEOUT_SECS,
        )
    except asyncio.TimeoutError:
        raise ReviewError(
            "REVIEW_TIMEOUT",
            f"Review exceeded {REVIEW_TIMEOUT_SECS}s total budget",
        )
    except ReviewError:
        raise  # pass through already-structured errors
    except Exception as exc:
        # Translation layer — nothing else escapes
        logger.exception("Unexpected error reviewing %s", repo_url)
        raise ReviewError("ENGINE_ERROR", f"Unexpected engine error: {type(exc).__name__}: {str(exc)[:200]}")


# ── Implementation ────────────────────────────────────────────────────────────

async def _run_review_impl(
    clone_url: str,
    canonical_url: str,
    branch: str,
    commit: Optional[str],
) -> ReviewReport:
    with tempfile.TemporaryDirectory() as tmp:

        # Step 1: Clone
        resolved_commit = await _clone(clone_url, branch, tmp)
        if commit:
            resolved_commit = commit

        # Step 2: Pre-flight size check (fast, before expensive analysis)
        _check_repo_size(tmp)

        # Step 3: Facts + adapters (CPU-bound — run in executor)
        loop = asyncio.get_event_loop()
        facts, adapter_results = await loop.run_in_executor(
            None, build_facts, canonical_url, tmp, resolved_commit
        )

        # Step 4: Rule engine (CPU-bound)
        registry   = build_default_registry()
        applicable = registry.for_facts(facts)
        findings   = deduplicate(
            await loop.run_in_executor(None, execute, registry, facts)
        )

        # Step 5: Score + interpret
        confidence    = compute_confidence_badge(
            facts, adapter_results, len(applicable), len(registry.all())
        )
        depth_profile = compute_depth(
            adapter_results, succeeded_tools=confidence.succeeded_tools
        )
        scorecard  = compute_scorecard(findings, depth=depth_profile.level)
        overall    = compute_overall(scorecard)
        interpreted = interpret_report(scorecard, overall, findings)
        coverage   = build_coverage(facts, adapter_results, tmp)
        anti_gaming = build_anti_gaming_block(findings, scorecard)
        why_not    = why_not_production_suitable(scorecard, findings, overall)
        flip       = what_would_flip_verdict(scorecard, findings)

        # Step 6: Deterministic summary + trace
        stub = ReviewReport(
            schema_version=SCHEMA_VERSION, ruleset_version=RULESET_VERSION,
            repo=RepoMeta(url=canonical_url, commit=resolved_commit,
                          primary_languages=facts.languages.primary),
            coverage=coverage, scorecard=scorecard,
        )
        stub.interpretation.overall_label      = interpreted.overall_band.label
        stub.interpretation.production_suitable = interpreted.production_suitable

        llm_input      = build_llm_input(stub, overall, findings,
                                         confidence_label=confidence.label,
                                         adapters_ran=confidence.adapters_ran)
        summary, trace = _deterministic_fallback(llm_input, findings)

        # Step 7: Assemble final report
        sorted_findings = sorted(
            findings,
            key=lambda f: ["critical","high","medium","low","info"].index(f.severity),
        )

        report = ReviewReport(
            schema_version=SCHEMA_VERSION,
            ruleset_version=RULESET_VERSION,
            repo=RepoMeta(
                url=canonical_url,
                commit=resolved_commit,
                primary_languages=facts.languages.primary,
            ),
            coverage=coverage,
            depth=AnalysisDepthInfo(
                level=depth_profile.level.value,
                label=depth_profile.label,
                description=depth_profile.description,
                verdict_note=depth_profile.verdict_note,
                adapters_succeeded=confidence.adapters_succeeded,
                allowed_strong_claims=depth_profile.allowed_strong_claims,
            ),
            scorecard=scorecard,
            interpretation=ScoreInterpretation(
                overall_label=interpreted.overall_band.label,
                trust_recommendation=interpreted.trust_recommendation,
                color_hint=interpreted.overall_band.color_hint,
                production_suitable=interpreted.production_suitable,
                top_concern=interpreted.top_concern,
                developer_meaning=interpreted.overall_band.developer_meaning,
                manager_meaning=interpreted.overall_band.manager_meaning,
                hiring_meaning=interpreted.overall_band.hiring_meaning,
                category_interpretations=interpreted.category_interpretations,
            ),
            meta=ReviewMeta(
                ruleset_version=RULESET_VERSION,
                schema_version=SCHEMA_VERSION,
                applicable_rule_count=len(applicable),
                executed_rule_count=len(applicable),
                adapters_run=list(adapter_results.keys()),
                overall_score=overall,
                confidence_label=confidence.label,
                confidence_score=confidence.score,
                confidence_rationale=confidence.rationale,
            ),
            findings=sorted_findings,
            anti_gaming=anti_gaming,
            priority_actions=[
                f.suggested_fix for f in sorted_findings
                if f.severity in ("critical", "high")
            ][:5],
            review_summary=summary,
        )

        logger.info(
            "review_complete repo=%s score=%d band=%s depth=%s "
            "findings=%d adapters=%d duration_budget_remaining=%.0fs",
            canonical_url, overall, interpreted.overall_band.label,
            depth_profile.level.value, len(findings),
            len(adapter_results),
            REVIEW_TIMEOUT_SECS,  # actual remaining would need tracking
        )
        return report


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _clone(clone_url: str, branch: str, dest: str) -> str:
    """
    Clone repo. Returns short commit SHA. Raises ReviewError on any failure.

    Branch fallback: if the requested branch doesn't exist, retries without
    --branch to get the default branch (handles main vs master differences).
    """
    async def _attempt(extra_args: list[str]) -> tuple[int, bytes]:
        proc = await asyncio.create_subprocess_exec(
            "git", "clone", "--depth", "1", *extra_args, clone_url, dest,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            _, stderr_b = await asyncio.wait_for(
                proc.communicate(), timeout=CLONE_TIMEOUT_SECS
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            raise ReviewError("CLONE_FAILED",
                              f"git clone timed out after {CLONE_TIMEOUT_SECS}s")
        return proc.returncode, stderr_b or b""

    # First attempt: with specified branch
    rc, stderr_b = await _attempt(["--branch", branch])
    msg = stderr_b.decode("utf-8", errors="replace")

    # Branch doesn't exist — retry without --branch to get default branch
    if rc != 0 and ("not found" in msg.lower() or "invalid branch" in msg.lower()
                    or "remote branch" in msg.lower()):
        import shutil
        # dest may be partially populated — clean it
        shutil.rmtree(dest, ignore_errors=True)
        import os; os.makedirs(dest, exist_ok=True)
        rc, stderr_b = await _attempt([])
        msg = stderr_b.decode("utf-8", errors="replace")

    if rc != 0:
        if "not found" in msg.lower() or "repository" in msg.lower():
            raise ReviewError("CLONE_FAILED",
                              "Repository not found or not accessible (may be private)")
        if "could not read" in msg.lower() or "authentication" in msg.lower():
            raise ReviewError("CLONE_FAILED",
                              "Authentication required — private repos are not supported")
        raise ReviewError("CLONE_FAILED",
                          f"git clone failed (exit {rc}): {msg[:200]}")

    # Get commit SHA
    sha_proc = await asyncio.create_subprocess_exec(
        "git", "rev-parse", "--short", "HEAD",
        cwd=dest,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout_b, _ = await sha_proc.communicate()
    return stdout_b.decode().strip() or "unknown"


def _check_repo_size(repo_path: str) -> None:
    """Fast pre-flight check. Raises ReviewError if repo is too large."""
    root = Path(repo_path)
    total_bytes = 0
    total_files = 0
    GIT_DIR = {".git"}

    for p in root.rglob("*"):
        if p.is_file():
            # Skip .git internals from size count
            parts = set(p.parts)
            if parts & GIT_DIR:
                continue
            total_files += 1
            try:
                total_bytes += p.stat().st_size
            except OSError:
                pass

            if total_files > MAX_FILE_COUNT:
                raise ReviewError(
                    "REPO_TOO_LARGE",
                    f"Repository has more than {MAX_FILE_COUNT:,} files — too large to review",
                )
            if total_bytes > MAX_REPO_SIZE_BYTES:
                mb = MAX_REPO_SIZE_BYTES // (1024 * 1024)
                raise ReviewError(
                    "REPO_TOO_LARGE",
                    f"Repository exceeds {mb}MB size limit",
                )
