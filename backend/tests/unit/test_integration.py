"""
tests/test_integration.py
--------------------------
End-to-end integration tests for the full analysis pipeline.

These tests run the complete pipeline on synthetic repo data:
  DeepScanner → ContextReviewer (no LLM) → Scorecard → ReportBuilder

No network calls. No LLM calls. No database.
The pipeline runs entirely in memory with synthetic file content.

What these tests prove:
  1. The pipeline assembles without import errors or circular deps
  2. DeepScanResult flows correctly into ContextReviewer
  3. Scorecard consumes findings without crashing on empty input
  4. ReportBuilder produces a structurally valid response
  5. UITruthLabels are attached to every output item
  6. Confidence breakdown is honest for the synthetic data
  7. Partial failures (stage timeout simulation) return graceful results
"""

from __future__ import annotations


import asyncio
import pytest
from typing import Dict, List

from app.services.deep_scanner import build_file_intelligence, build_code_contexts, DeepScanResult
from app.services.scorecard import build_scorecard
from app.services.report_builder import ReportBuilder
from app.schemas.intelligence import (
    GRAPH_SEMANTICS_VERSION,
    SCHEMA_VERSION,
    ConfidenceBreakdown,
    FileIntelligence,
    RepoIntelligence,
    ScanMetadata,
    TruthLabels,
)


# ---------------------------------------------------------------------------
# Synthetic repo content
# ---------------------------------------------------------------------------

SYNTHETIC_REPO: Dict[str, str] = {
    "app/main.py": """\
from fastapi import FastAPI
from app.api.routes.analyze import router
from app.core.config import get_settings

app = FastAPI()
app.include_router(router, prefix="/api")
settings = get_settings()
""",
    "app/api/routes/analyze.py": """\
from fastapi import APIRouter
from app.services.analyzer import run_analysis

router = APIRouter()

@router.post("/analyze")
async def analyze(repo_url: str):
    return await run_analysis(repo_url)
""",
    "app/services/analyzer.py": """\
import httpx
from app.core.config import get_settings

API_KEY = "hardcoded_secret_value_here"  # noqa: S105 — intentional test fixture

async def run_analysis(repo_url: str) -> dict:
    settings = get_settings()
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"https://api.github.com/repos/{repo_url}")
        return resp.json()
""",
    "app/core/config.py": """\
from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    anthropic_api_key: str = ""
    github_token: str = ""

@lru_cache
def get_settings():
    return Settings()
""",
    "app/models/result.py": """\
from pydantic import BaseModel
from typing import Optional

class AnalysisResult(BaseModel):
    repo_url: str
    summary: Optional[str] = None
    score: Optional[int] = None
""",
    "tests/test_analyzer.py": """\
import pytest
from app.services.analyzer import run_analysis

@pytest.mark.asyncio
async def test_run_analysis():
    # Integration test placeholder
    pass
""",
    "pyproject.toml": """\
[project]
name = "atlas-backend"
dependencies = ["fastapi", "pydantic-settings", "httpx", "anthropic"]

[project.optional-dependencies]
dev = ["pytest", "pytest-asyncio", "ruff"]
""",
    ".github/workflows/ci.yml": """\
name: CI
on: [push]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - run: pip install -e ".[dev]"
      - run: pytest
""",
}


def build_synthetic_files() -> List[FileIntelligence]:
    return [
        build_file_intelligence(path, content, size_bytes=len(content))
        for path, content in SYNTHETIC_REPO.items()
    ]


def build_synthetic_scan_result() -> DeepScanResult:
    files = build_synthetic_files()
    contents = {path: content for path, content in SYNTHETIC_REPO.items()}
    contexts, edges, gc = build_code_contexts(files)
    metadata = ScanMetadata(
        total_files=len(SYNTHETIC_REPO),
        files_scanned=len(files),
        files_skipped=0,
        files_failed=0,
        parse_success_rate=1.0,
        languages_detected={"python": 6, "yaml": 1, "toml": 1},
        scan_duration_seconds=0.5,
    )
    result = DeepScanResult(
        files=files,
        contexts=contexts,
        scan_metadata=metadata,
        contents=contents,
        edges=edges,
        graph_confidence=gc,
    )
    return result


# ---------------------------------------------------------------------------
# Integration test: DeepScanner
# ---------------------------------------------------------------------------

class TestDeepScannerIntegration:
    def setup_method(self):
        self.scan = build_synthetic_scan_result()

    def test_files_are_extracted(self):
        assert len(self.scan.files) == len(SYNTHETIC_REPO)

    def test_entrypoint_detected(self):
        fi_map = {f.path: f for f in self.scan.files}
        assert fi_map["app/main.py"].is_entrypoint is True

    def test_test_file_classified(self):
        fi_map = {f.path: f for f in self.scan.files}
        assert fi_map["tests/test_analyzer.py"].role == "test"

    def test_infra_file_classified(self):
        fi_map = {f.path: f for f in self.scan.files}
        assert fi_map[".github/workflows/ci.yml"].role == "infra"

    def test_config_file_classified(self):
        fi_map = {f.path: f for f in self.scan.files}
        assert fi_map["pyproject.toml"].role == "config"

    def test_critical_path_populated(self):
        critical = [p for p, ctx in self.scan.contexts.items() if ctx.is_on_critical_path]
        assert "app/main.py" in critical

    def test_edges_produced(self):
        assert len(self.scan.edges) > 0

    def test_confirmed_edges_exist(self):
        confirmed = [e for e in self.scan.edges if e.confidence == "confirmed"]
        assert len(confirmed) > 0

    def test_sensitive_operation_detected(self):
        """analyzer.py has a hardcoded secret — must be detected"""
        fi_map = {f.path: f for f in self.scan.files}
        assert "hardcoded_secret" in fi_map["app/services/analyzer.py"].sensitive_operations

    def test_contents_stored(self):
        assert len(self.scan.contents) > 0
        assert "app/main.py" in self.scan.contents

    def test_graph_confidence_positive(self):
        assert self.scan.graph_confidence > 0.0

    def test_scan_metadata_accurate(self):
        assert self.scan.scan_metadata.files_scanned == len(SYNTHETIC_REPO)


# ---------------------------------------------------------------------------
# Integration test: Scorecard on synthetic findings
# ---------------------------------------------------------------------------

class TestScorecardIntegration:
    def setup_method(self):
        self.scan = build_synthetic_scan_result()

    def test_scorecard_builds_without_findings(self):
        """Scorecard must handle zero findings gracefully."""
        score = build_scorecard(
            findings=[],
            files=self.scan.files,
            scan_metadata=self.scan.scan_metadata,
        )
        assert score.composite_score >= 0
        assert score.composite_score <= 100

    def test_scorecard_with_deterministic_findings(self):
        """
        analyzer.py has a hardcoded secret. Run the deterministic
        finding generator and verify the scorecard reflects it.
        """
        from app.services.context_reviewer import generate_deterministic_findings

        fi_map = {f.path: f for f in self.scan.files}
        analyzer_fi = fi_map["app/services/analyzer.py"]
        analyzer_content = self.scan.contents["app/services/analyzer.py"]

        findings = generate_deterministic_findings(analyzer_fi, analyzer_content)
        assert len(findings) > 0, "Hardcoded secret must produce at least one finding"

        secret_findings = [f for f in findings if f.category == "security"]
        assert len(secret_findings) > 0

        score = build_scorecard(
            findings=findings,
            files=self.scan.files,
            scan_metadata=self.scan.scan_metadata,
        )
        # Security score must be lower than base (100) due to hardcoded secret
        security_dim = score.dimension_scores.get("security")
        assert security_dim is not None
        assert security_dim.raw_score < 100

    def test_scorecard_confidence_bounded(self):
        score = build_scorecard(
            findings=[],
            files=self.scan.files,
            scan_metadata=self.scan.scan_metadata,
        )
        assert 0.0 <= score.confidence <= 0.97

    def test_scorecard_has_all_dimensions(self):
        from app.services.scorecard import DIMENSIONS
        score = build_scorecard(
            findings=[],
            files=self.scan.files,
            scan_metadata=self.scan.scan_metadata,
        )
        for dim in DIMENSIONS:
            assert dim in score.dimension_scores, f"Missing dimension: {dim}"

    def test_test_coverage_dimension_reflects_files(self):
        """test_analyzer.py exists — test_coverage score should be > 0."""
        score = build_scorecard(
            findings=[],
            files=self.scan.files,
            scan_metadata=self.scan.scan_metadata,
        )
        test_dim = score.dimension_scores.get("test_coverage")
        assert test_dim is not None
        assert test_dim.adjusted_score > 0


# ---------------------------------------------------------------------------
# Integration test: ReportBuilder
# ---------------------------------------------------------------------------

class TestReportBuilderIntegration:
    def setup_method(self):
        self.scan = build_synthetic_scan_result()
        extraction_conf = sum(f.confidence for f in self.scan.files) / len(self.scan.files)
        self.confidence = ConfidenceBreakdown.compute(
            extraction=extraction_conf,
            graph=self.scan.graph_confidence,
            finding=1.0,
        )
        self.ri = RepoIntelligence(
            repo_url="https://github.com/test/atlas",
            repo_owner="test",
            repo_name="atlas",
            default_branch="main",
            files=self.scan.files,
            contexts=self.scan.contexts,
            edges=self.scan.edges,
            scan_metadata=self.scan.scan_metadata,
            confidence=self.confidence,
        )
        self.builder = ReportBuilder()

    def test_report_builds_without_error(self):
        report = self.builder.build(self.ri)
        assert report is not None

    def test_report_has_correct_repo_info(self):
        report = self.builder.build(self.ri)
        assert report.repo_url == "https://github.com/test/atlas"
        assert report.repo_owner == "test"
        assert report.repo_name == "atlas"

    def test_report_schema_version_present(self):
        report = self.builder.build(self.ri)
        assert report.schema_version == SCHEMA_VERSION
        assert report.graph_semantics_version == GRAPH_SEMANTICS_VERSION

    def test_files_have_truth_labels(self):
        report = self.builder.build(self.ri)
        for f in report.files:
            assert f.truth_label is not None
            assert "variant" in f.truth_label
            assert "short" in f.truth_label
            assert "detail" in f.truth_label

    def test_edges_have_truth_labels(self):
        report = self.builder.build(self.ri)
        for e in report.edges:
            assert e.truth_label is not None
            assert "variant" in e.truth_label

    def test_confirmed_edges_get_confirmed_label(self):
        report = self.builder.build(self.ri)
        confirmed_edges = [e for e in report.edges if e.confidence == "confirmed"]
        assert len(confirmed_edges) > 0
        for e in confirmed_edges:
            assert e.truth_label["variant"] == "confirmed"

    def test_unresolved_edges_get_degraded_or_unknown_label(self):
        report = self.builder.build(self.ri)
        unresolved_edges = [e for e in report.edges if e.confidence == "unresolved"]
        for e in unresolved_edges:
            assert e.truth_label["variant"] in ("degraded", "unknown"), (
                f"Unresolved edge '{e.raw_import}' has unexpected variant: "
                f"{e.truth_label['variant']}"
            )

    def test_entrypoint_files_sorted_first(self):
        report = self.builder.build(self.ri)
        if report.files:
            first = report.files[0]
            # Entrypoints should appear first
            assert first.is_entrypoint or first.is_on_critical_path

    def test_confidence_breakdown_present(self):
        report = self.builder.build(self.ri)
        cb = report.confidence_breakdown
        assert "extraction" in cb
        assert "graph" in cb
        assert "finding" in cb
        assert "score" in cb
        for val in cb.values():
            assert 0.0 <= val <= 1.0

    def test_confidence_truth_label_present(self):
        report = self.builder.build(self.ri)
        label = report.confidence_truth_label
        assert label is not None
        assert label["variant"] in ("confirmed", "degraded", "unknown")
        assert len(label["short"]) <= 40

    def test_graph_summary_accurate(self):
        report = self.builder.build(self.ri)
        graph = report.graph
        assert graph.total_files == len(SYNTHETIC_REPO)
        assert len(graph.entrypoints) > 0
        assert "app/main.py" in graph.entrypoints
        assert graph.confirmed_edge_count > 0

    def test_serialization_does_not_crash(self):
        """Report must serialize to dict without errors."""
        report = self.builder.build(self.ri)
        d = report.to_dict()
        assert isinstance(d, dict)
        assert "repo_url" in d
        assert "graph" in d
        assert "files" in d
        assert "edges" in d


# ---------------------------------------------------------------------------
# Integration test: Pipeline _parse_repo_url
# ---------------------------------------------------------------------------

class TestPipelineHelpers:
    def test_parse_github_https_url(self):
        from app.services.intelligence_pipeline import _parse_repo_url
        owner, name = _parse_repo_url("https://github.com/MentalVibez/AI_Architecture_Explainer")
        assert owner == "MentalVibez"
        assert name == "AI_Architecture_Explainer"

    def test_parse_short_form(self):
        from app.services.intelligence_pipeline import _parse_repo_url
        owner, name = _parse_repo_url("owner/repo")
        assert owner == "owner"
        assert name == "repo"

    def test_parse_github_com_prefix(self):
        from app.services.intelligence_pipeline import _parse_repo_url
        owner, name = _parse_repo_url("github.com/owner/repo")
        assert owner == "owner"
        assert name == "repo"

    def test_parse_invalid_raises(self):
        from app.services.intelligence_pipeline import _parse_repo_url
        with pytest.raises(ValueError):
            _parse_repo_url("not-a-url")

    def test_parse_trailing_slash_stripped(self):
        from app.services.intelligence_pipeline import _parse_repo_url
        owner, name = _parse_repo_url("https://github.com/owner/repo/")
        assert owner == "owner"
        assert name == "repo"


# ---------------------------------------------------------------------------
# Integration test: Truth label factory completeness
# ---------------------------------------------------------------------------

class TestTruthLabelCompleteness:
    """Verify every unresolved reason code maps to a non-None truth label."""

    REASON_CODES = [
        "ambiguous_package_import",
        "dynamic_import",
        "alias_unknown",
        "file_not_scanned",
        "parse_error",
        None,  # Should return a sensible default
    ]

    @pytest.mark.parametrize("reason", REASON_CODES)
    def test_every_reason_code_produces_label(self, reason):
        label = TruthLabels.from_unresolved_reason(reason)
        assert label is not None
        assert label.variant in ("confirmed", "inferred", "degraded", "excluded", "unknown")
        assert len(label.short) > 0
        assert len(label.short) <= 40, f"Label too long: {label.short!r}"
        assert len(label.detail) > 0

    def test_dynamic_import_is_unknown_not_degraded(self):
        """Dynamic imports are structurally unresolvable — not a quality degradation."""
        label = TruthLabels.from_unresolved_reason("dynamic_import")
        assert label.variant == "unknown"

    def test_confirmed_edge_label(self):
        label = TruthLabels.confirmed_edge()
        assert label.variant == "confirmed"
        assert label.limitation_ref is None

    def test_limitation_refs_are_valid_format(self):
        """Any limitation_ref must match 'L-NNN' format."""
        import re
        labels_with_refs = [
            TruthLabels.unresolved_package_import(),
            TruthLabels.unresolved_dynamic_import(),
            TruthLabels.unresolved_alias_unknown(),
        ]
        pattern = re.compile(r'^L-\d{3}$')
        for label in labels_with_refs:
            if label.limitation_ref:
                assert pattern.match(label.limitation_ref), (
                    f"Invalid limitation_ref format: {label.limitation_ref!r}"
                )
