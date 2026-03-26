"""
app/schemas/intelligence.py
-----------------------
Core data contracts for the Codebase Atlas deep intelligence pipeline.

These schemas are the single source of truth that flows through:
  Ingest → Extract → DeepScan → RepoGraph → Review → Explain → Optimize

Rule: Every downstream system consumes these. Never bypass them.
"""

from __future__ import annotations

import uuid
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

# Schema version — bump on any breaking change to these contracts.
# Downstream consumers (DB, API, frontend) check this before deserializing.
SCHEMA_VERSION = "1.1.0"

# Graph semantics version — bump when traversal algorithm or depth rules change.
# Separate from SCHEMA_VERSION so field additions don't pollute algorithm history.
# History:
#   1 — DFS, depth cap 10 (deprecated: ordering artifact)
#   2 — BFS, depth cap 2, shortest-path semantics, dynamic imports excluded
#         from confidence denominator
GRAPH_SEMANTICS_VERSION = 2
CRITICAL_PATH_ALGORITHM = "bfs_depth_2"

# Human-readable description of current semantics — shown in UI debug panel
GRAPH_SEMANTICS_DESCRIPTION = (
    "BFS from each entrypoint, depth cap 2. "
    "Criticality is determined by shortest-path distance. "
    "Dynamic imports excluded from graph confidence."
)


# ---------------------------------------------------------------------------
# FileIntelligence
# The atomic unit of repo knowledge. One per file. 100% deterministic.
# LLM never writes this — only reads it.
# ---------------------------------------------------------------------------

FileRole = Literal[
    "entrypoint",
    "service",
    "module",
    "utility",
    "config",
    "test",
    "infra",
    "migration",
    "schema",
    "unknown",
]

LanguageTag = Literal[
    "python", "typescript", "javascript", "go", "rust",
    "java", "ruby", "php", "csharp", "c", "cpp",
    "shell", "yaml", "toml", "json", "markdown",
    "dockerfile", "sql", "unknown",
]


class FileIntelligence(BaseModel):
    # Identity
    path: str = Field(..., description="Repo-relative path, e.g. backend/app/main.py")
    language: LanguageTag
    role: FileRole

    # Structural facts — extracted deterministically
    imports: list[str] = Field(default_factory=list)
    exports: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(
        default_factory=list,
        description="External packages/modules this file depends on",
    )

    # Complexity signals — computed, not guessed
    complexity_score: float = Field(
        default=0.0,
        ge=0.0,
        description="Cyclomatic complexity estimate. 0=unknown, 1-10=low, 10-20=medium, 20+=high",
    )
    loc: int = Field(default=0, ge=0, description="Lines of code (non-blank, non-comment)")
    nesting_depth_max: int = Field(default=0, ge=0)
    function_count: int = Field(default=0, ge=0)
    class_count: int = Field(default=0, ge=0)

    # Risk signals — patterns found, not inferred
    external_calls: list[str] = Field(
        default_factory=list,
        description="Outbound HTTP calls, DB queries, subprocess calls, etc.",
    )
    sensitive_operations: list[str] = Field(
        default_factory=list,
        description="Patterns like: exec(), eval(), os.system(), raw SQL, hardcoded secrets",
    )

    # Framework fingerprints
    framework_signals: list[str] = Field(
        default_factory=list,
        description="e.g. ['fastapi', 'sqlalchemy', 'pytest']",
    )

    # Boolean classifiers
    is_entrypoint: bool = False
    is_executable: bool = False
    is_test: bool = False
    has_type_annotations: bool = False
    has_docstrings: bool = False
    has_error_handling: bool = False

    # Scan metadata
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="How reliably was this file parsed? 1.0=fully parsed, <0.5=partial/failed",
    )
    parse_errors: list[str] = Field(
        default_factory=list,
        description="Any parsing errors encountered — never silently dropped",
    )
    size_bytes: int = Field(default=0, ge=0)
    was_truncated: bool = Field(
        default=False,
        description="True if file exceeded size limit and was partially scanned",
    )


# ---------------------------------------------------------------------------
# CodeContext
# How a file relates to the rest of the repo.
# This is what makes the reviewer smart — it reasons about relationships,
# not files in isolation.
# ---------------------------------------------------------------------------

class CodeContext(BaseModel):
    file_path: str

    # Relationship graph
    upstream_callers: list[str] = Field(
        default_factory=list,
        description="Files that import or call this file",
    )
    downstream_dependencies: list[str] = Field(
        default_factory=list,
        description="Files this file imports or calls",
    )
    related_files: list[str] = Field(
        default_factory=list,
        description="Sibling files with high coupling (same module, same domain)",
    )

    # Architectural positioning
    service_boundary: str | None = Field(
        default=None,
        description="Which service or module owns this file, e.g. 'auth', 'payments'",
    )
    entrypoint_chain: list[str] = Field(
        default_factory=list,
        description="Execution path from the nearest entrypoint to this file",
    )

    # Risk amplification
    is_on_critical_path: bool = Field(
        default=False,
        description="True if this file is in the call chain of a public-facing entrypoint",
    )
    caller_count: int = Field(
        default=0,
        ge=0,
        description="How many other files depend on this one — higher = higher blast radius",
    )


# ---------------------------------------------------------------------------
# DependencyEdge
# An explicit, typed edge in the dependency graph.
# Every downstream claim about architecture MUST trace to one or more edges.
# "inferred" edges are allowed but must be labelled — they can never drive
# security or scoring decisions without a "confirmed" edge as corroboration.
# ---------------------------------------------------------------------------

EdgeKind = Literal[
    "import",          # Explicit import statement
    "dynamic_import",  # require() / importlib / __import__
    "re_export",       # barrel file re-exporting another module
    "inheritance",     # class B(A) — B depends on A's file
    "instantiation",   # A() called inside B — heuristic
]

EdgeConfidence = Literal[
    "confirmed",   # Resolved to an exact file path in the repo
    "inferred",    # Matched by heuristic — may be wrong
    "unresolved",  # Import string found but could not map to a file
]


class DependencyEdge(BaseModel):
    """
    A single directed edge: source_file → target_file.

    This is the atomic unit of the dependency graph.
    The graph is a list of these edges — nothing more.
    Architecture claims are only valid if they can be expressed
    as a path through confirmed edges.
    """
    source_path: str = Field(..., description="Repo-relative path of the importing file")
    target_path: str | None = Field(
        default=None,
        description="Repo-relative path of the imported file. None if unresolved.",
    )
    raw_import: str = Field(
        ...,
        description="The exact import string as written in source. Never modified.",
    )
    kind: EdgeKind
    confidence: EdgeConfidence

    # Evidence anchor — where in the source file this edge was found
    source_line: int = Field(default=0, ge=0, description="Line number of the import statement")


    # Unresolved reason — only set when confidence == 'unresolved'.
    # These reason codes map directly to entries in docs/LIMITATIONS.md.
    unresolved_reason: Optional[Literal[
        # L-001, L-005: `from pkg import mod` or namespace package.
        # Import string points to a directory, not a file. Cannot determine
        # which submodule is intended without parsing the imported names.
        # Does count against graph_confidence.
        "ambiguous_package_import",

        # L-003: Dynamic import — path contains a runtime variable.
        # Structurally unresolvable by static analysis.
        # Does NOT count against graph_confidence.
        "dynamic_import",

        # L-004: TypeScript path alias not in the known alias map.
        # The alias prefix was not in tsconfig defaults or provided ts_aliases.
        # Does count against graph_confidence.
        "alias_unknown",

        # General: import string resolved to a valid-looking internal path
        # but no file with that path exists in the scanned file set.
        # May mean the file was skipped, failed to fetch, or does not exist.
        # Does count against graph_confidence.
        "file_not_scanned",

        # The source file itself had a parse error — imports could not be
        # extracted reliably, so resolution was not attempted.
        # Does count against graph_confidence.
        "parse_error",
    ]] = None

    @model_validator(mode="after")
    def target_required_if_confirmed(self) -> DependencyEdge:
        if self.confidence == "confirmed" and not self.target_path:
            raise ValueError("target_path is required when confidence is 'confirmed'")
        return self


# ---------------------------------------------------------------------------
# ConfidenceBreakdown
# Four distinct confidence dimensions — replaces the single global float.
# Each dimension can degrade independently.
#
# extraction_confidence: how well we parsed individual files
# graph_confidence:      how complete the dependency graph is
# finding_confidence:    average confidence of CodeFindings (deterministic=1.0)
# score_confidence:      composite — a function of the other three
# ---------------------------------------------------------------------------

class ConfidenceBreakdown(BaseModel):
    extraction_confidence: float = Field(
        ge=0.0, le=1.0,
        description=(
            "Average FileIntelligence.confidence across scanned files. "
            "Drops when files fail to parse or are truncated."
        ),
    )
    graph_confidence: float = Field(
        ge=0.0, le=1.0,
        description=(
            "Fraction of dependency edges that are 'confirmed' vs total edges found. "
            "Low when many imports are unresolved (external packages are excluded from denominator)."
        ),
    )
    finding_confidence: float = Field(
        ge=0.0, le=1.0,
        description=(
            "Average CodeFinding.confidence across all non-suppressed findings. "
            "Deterministic findings are 1.0. LLM-assisted are 0.75."
        ),
    )
    score_confidence: float = Field(
        ge=0.0, le=0.97,
        description=(
            "Composite confidence for the scorecard. "
            "Weighted: extraction × 0.4, graph × 0.35, finding × 0.25. "
            "Capped at 0.97 — static analysis is never certain."
        ),
    )

    # Human-readable labels
    @property
    def score_label(self) -> Literal["HIGH", "MODERATE", "LOW"]:
        if self.score_confidence >= 0.85:
            return "HIGH"
        elif self.score_confidence >= 0.65:
            return "MODERATE"
        return "LOW"

    # UI disclosure strings — what the frontend shows per dimension
    @property
    def extraction_label(self) -> str:
        pct = int(self.extraction_confidence * 100)
        return f"Files parsed: {pct}% quality"

    @property
    def graph_label(self) -> str:
        pct = int(self.graph_confidence * 100)
        return f"Dependency edges confirmed: {pct}%"

    @property
    def finding_label(self) -> str:
        pct = int(self.finding_confidence * 100)
        return f"Finding evidence quality: {pct}%"

    @staticmethod
    def compute(
        extraction: float,
        graph: float,
        finding: float,
    ) -> ConfidenceBreakdown:
        score = min(
            0.97,
            round(
                (extraction * 0.40)
                + (graph * 0.35)
                + (finding * 0.25),
                3,
            ),
        )
        return ConfidenceBreakdown(
            extraction_confidence=round(extraction, 3),
            graph_confidence=round(graph, 3),
            finding_confidence=round(finding, 3),
            score_confidence=score,
        )
# A single issue. Evidence-mandatory.
# Rule: No line reference = this object cannot be constructed.
# ---------------------------------------------------------------------------

FindingCategory = Literal[
    "security",
    "performance",
    "reliability",
    "maintainability",
    "dead_code",
    "type_safety",
    "error_handling",
]

FindingSeverity = Literal["low", "medium", "high", "critical"]

FindingSource = Literal[
    "deterministic",   # Found by static analysis rule
    "heuristic",       # Found by pattern matching
    "llm_assisted",    # LLM flagged with evidence citation
]


class CodeFinding(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    file_path: str
    category: FindingCategory
    severity: FindingSeverity
    source: FindingSource

    # Evidence — MANDATORY. Validator enforces this.
    line_start: int = Field(..., ge=1)
    line_end: int = Field(..., ge=1)
    evidence_snippet: str = Field(
        ...,
        min_length=1,
        description="Exact code excerpt from the file. No paraphrasing.",
    )

    # Human-readable outputs
    title: str
    explanation: str = Field(
        ...,
        description="Why this is a problem. Must reference the specific code pattern.",
    )
    remediation: str | None = Field(
        default=None,
        description="Concrete fix suggestion. Optional but strongly preferred.",
    )

    # Scoring impact — used by scorecard engine
    score_impact: int = Field(
        default=0,
        le=0,
        description="Negative integer. How much this finding deducts from the relevant score dimension.",
    )

    confidence: float = Field(ge=0.0, le=1.0)

    # Suppression
    is_suppressed: bool = False
    suppression_reason: str | None = None

    @field_validator("line_end")
    @classmethod
    def end_gte_start(cls, v: int, info) -> int:
        start = info.data.get("line_start", 1)
        if v < start:
            raise ValueError(f"line_end ({v}) must be >= line_start ({start})")
        return v

    @field_validator("evidence_snippet")
    @classmethod
    def snippet_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("evidence_snippet cannot be empty or whitespace")
        return v


# ---------------------------------------------------------------------------
# OptimizationCandidate
# A proposed change. Always tied to a finding. Always requires approval.
# Rule: No full-file rewrites. Targeted patches only.
# ---------------------------------------------------------------------------

ChangeType = Literal[
    "refactor",
    "remove_dead_code",
    "security_fix",
    "performance_improvement",
    "error_handling_addition",
    "type_annotation_addition",
]

RiskLevel = Literal["low", "medium", "high"]


class OptimizationCandidate(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    finding_id: str = Field(..., description="Must reference a valid CodeFinding.id")
    file_path: str

    change_type: ChangeType

    # The actual change — unified diff format
    patch_diff: str = Field(
        ...,
        min_length=10,
        description="Unified diff string. Must be directly applicable via `patch`.",
    )

    # Human explanation
    explanation: str = Field(
        ...,
        description="Why this change improves the code. Plain language.",
    )
    before_snippet: str = Field(..., description="Exact original code being replaced")
    after_snippet: str = Field(..., description="Exact replacement code")

    # Impact prediction — honest estimates, not guarantees
    expected_score_impact: dict[str, int] = Field(
        default_factory=dict,
        description="e.g. {'security': +20, 'maintainability': +5}",
    )

    risk: RiskLevel = Field(
        ...,
        description="Risk of applying this change. High = needs manual review before applying.",
    )

    # Human-in-the-loop gate — cannot be bypassed
    requires_user_approval: bool = True
    is_approved: bool = False
    is_applied: bool = False

    # Breaking change detection
    may_break_callers: bool = Field(
        default=False,
        description="True if this change modifies a public API or exported function signature",
    )
    affected_files: list[str] = Field(
        default_factory=list,
        description="Other files that may need updates if this change is applied",
    )


# ---------------------------------------------------------------------------
# RepoIntelligence
# The aggregate. What RepoGraph produces after consuming all FileIntelligence
# and CodeContext objects.
# ---------------------------------------------------------------------------

class ScanMetadata(BaseModel):
    total_files: int
    files_scanned: int
    files_skipped: int
    files_failed: int
    parse_success_rate: float = Field(ge=0.0, le=1.0)
    languages_detected: dict[str, int] = Field(
        default_factory=dict,
        description="Language → file count",
    )
    scan_duration_seconds: float


# ---------------------------------------------------------------------------
# UITruthLabel
# The data contract the frontend uses to show honest state labels per item.
#
# This is NOT a display component — it's structured data that the frontend
# renders. The backend controls the label text and variant; the frontend
# controls how it looks.
#
# Design principle: every fact shown to the user must have a truth label.
# "Confirmed from code" is different from "Inferred from structure" is
# different from "Could not be determined." Users need to know which is which.
# ---------------------------------------------------------------------------

TruthLabelVariant = Literal[
    "confirmed",    # Directly traced to file evidence
    "inferred",     # Derived from structure, not direct evidence
    "degraded",     # Evidence exists but quality is reduced
    "excluded",     # Intentionally not analyzed
    "unknown",      # Could not be determined
]


class UITruthLabel(BaseModel):
    """
    A single truth label for one piece of information in the analysis output.

    Usage examples:
      edge.truth_label = UITruthLabel(
          variant="confirmed",
          short="Confirmed from code",
          detail="Import statement on line 12 resolves to this file.",
      )

      file.truth_label = UITruthLabel(
          variant="excluded",
          short="Generated — excluded",
          detail="poetry.lock is a generated lockfile. Not parsed.",
          limitation_ref="L-001",
      )

      score.truth_label = UITruthLabel(
          variant="degraded",
          short="Confidence reduced",
          detail="23 imports could not be resolved (ambiguous package imports). "
                 "Score may be incomplete.",
          limitation_ref="L-001",
      )
    """
    variant: TruthLabelVariant
    short: str = Field(
        ...,
        description="Short display text. Max 40 chars. Shown inline in the UI.",
        max_length=40,
    )
    detail: str = Field(
        ...,
        description="Full explanation shown on hover/expand.",
    )
    limitation_ref: str | None = Field(
        default=None,
        description=(
            "Reference to LIMITATIONS.md entry if this label indicates a known gap. "
            "Format: 'L-001', 'L-003', etc."
        ),
    )


# ---------------------------------------------------------------------------
# Standard truth label factories
# Pre-built labels for the most common states in the graph output.
# Use these instead of constructing UITruthLabel manually to keep text consistent.
# ---------------------------------------------------------------------------

class TruthLabels:
    """
    Factory for standard UITruthLabel instances.
    Import this and use TruthLabels.confirmed_edge() etc.
    All text here is UI copy — changes here propagate everywhere.
    """

    @staticmethod
    def confirmed_edge() -> UITruthLabel:
        return UITruthLabel(
            variant="confirmed",
            short="Confirmed from code",
            detail="This dependency was resolved from an explicit import statement in the source file.",
        )

    @staticmethod
    def unresolved_package_import() -> UITruthLabel:
        return UITruthLabel(
            variant="degraded",
            short="Unresolved — package import",
            detail=(
                "Import uses 'from package import module' syntax. "
                "Atlas cannot determine which file is intended without parsing imported names. "
                "This may reduce graph confidence."
            ),
            limitation_ref="L-001",
        )

    @staticmethod
    def unresolved_dynamic_import() -> UITruthLabel:
        return UITruthLabel(
            variant="unknown",
            short="Dynamic import",
            detail=(
                "Import path is constructed at runtime (e.g. importlib.import_module, template literal). "
                "Static analysis cannot resolve this. Not counted against graph confidence."
            ),
            limitation_ref="L-003",
        )

    @staticmethod
    def unresolved_alias_unknown() -> UITruthLabel:
        return UITruthLabel(
            variant="degraded",
            short="Unknown path alias",
            detail=(
                "Import uses a TypeScript path alias (@something/) that is not in the "
                "known alias map. Add the alias to tsconfig.json paths or provide it explicitly."
            ),
            limitation_ref="L-004",
        )

    @staticmethod
    def unresolved_file_not_scanned() -> UITruthLabel:
        return UITruthLabel(
            variant="degraded",
            short="File not in scan",
            detail=(
                "Import resolved to a path that was not in the scanned file set. "
                "The file may have been skipped, failed to fetch, or does not exist."
            ),
        )

    @staticmethod
    def generated_excluded() -> UITruthLabel:
        return UITruthLabel(
            variant="excluded",
            short="Generated — excluded",
            detail=(
                "This file is generated output (lockfile, minified bundle, .d.ts declaration). "
                "It is visible in the file inventory but not analyzed."
            ),
        )

    @staticmethod
    def vendor_excluded() -> UITruthLabel:
        return UITruthLabel(
            variant="excluded",
            short="Vendor — excluded",
            detail="This file is in a vendor or dependency directory and was not scanned.",
        )

    @staticmethod
    def parse_failed() -> UITruthLabel:
        return UITruthLabel(
            variant="unknown",
            short="Parse failed",
            detail=(
                "This file could not be fetched or parsed. "
                "It exists in the repository tree but its contents are unknown."
            ),
        )

    @staticmethod
    def critical_path_bfs() -> UITruthLabel:
        return UITruthLabel(
            variant="confirmed",
            short="On critical path",
            detail=(
                "This file is reachable from a public entrypoint within 2 hops "
                "(BFS shortest-path). Issues here have the highest impact."
            ),
        )

    @staticmethod
    def not_critical_path() -> UITruthLabel:
        return UITruthLabel(
            variant="inferred",
            short="Not on critical path",
            detail=(
                "This file is not reachable from any entrypoint within 2 hops. "
                "Issues here have lower blast radius."
            ),
        )

    @staticmethod
    def confidence_high() -> UITruthLabel:
        return UITruthLabel(
            variant="confirmed",
            short="High confidence",
            detail=(
                "The analysis covered most of the repository with high parse quality. "
                "Results are reliable."
            ),
        )

    @staticmethod
    def confidence_moderate(unresolved_count: int = 0) -> UITruthLabel:
        detail = "Some files or imports could not be fully analyzed."
        if unresolved_count > 0:
            detail += f" {unresolved_count} imports were unresolved."
        return UITruthLabel(
            variant="degraded",
            short="Moderate confidence",
            detail=detail,
        )

    @staticmethod
    def confidence_low(reason: str = "") -> UITruthLabel:
        detail = (
            "Significant portions of the repository were not analyzed. "
            "Treat results as directional, not definitive."
        )
        if reason:
            detail += f" Reason: {reason}"
        return UITruthLabel(
            variant="unknown",
            short="Low confidence",
            detail=detail,
        )

    @staticmethod
    def from_unresolved_reason(reason: str | None) -> UITruthLabel:
        """Map an UnresolvedReason code to the correct UITruthLabel."""
        dispatch = {
            "ambiguous_package_import": TruthLabels.unresolved_package_import,
            "dynamic_import": TruthLabels.unresolved_dynamic_import,
            "alias_unknown": TruthLabels.unresolved_alias_unknown,
            "file_not_scanned": TruthLabels.unresolved_file_not_scanned,
            "parse_error": TruthLabels.parse_failed,
        }
        factory = dispatch.get(reason or "", TruthLabels.unresolved_file_not_scanned)
        return factory()

    @staticmethod
    def from_confidence_breakdown(cb: ConfidenceBreakdown, unresolved_count: int = 0) -> UITruthLabel:
        """Map a ConfidenceBreakdown to the appropriate confidence label."""
        if cb.score_label == "HIGH":
            return TruthLabels.confidence_high()
        elif cb.score_label == "MODERATE":
            return TruthLabels.confidence_moderate(unresolved_count)
        else:
            return TruthLabels.confidence_low()


class RepoIntelligence(BaseModel):
    repo_url: str
    repo_owner: str
    repo_name: str
    default_branch: str

    # Schema and semantics versioning
    schema_version: str = SCHEMA_VERSION
    graph_semantics_version: int = GRAPH_SEMANTICS_VERSION
    critical_path_algorithm: str = CRITICAL_PATH_ALGORITHM

    # Core outputs
    files: list[FileIntelligence] = Field(default_factory=list)
    contexts: dict[str, CodeContext] = Field(
        default_factory=dict,
        description="file_path → CodeContext",
    )
    edges: list[DependencyEdge] = Field(
        default_factory=list,
        description="All dependency edges. Includes confirmed, inferred, and unresolved.",
    )
    findings: list[CodeFinding] = Field(default_factory=list)
    candidates: list[OptimizationCandidate] = Field(default_factory=list)

    # Scan quality
    scan_metadata: ScanMetadata | None = None
    confidence: ConfidenceBreakdown | None = None

    # Convenience accessors
    @property
    def confirmed_edges(self) -> list[DependencyEdge]:
        return [e for e in self.edges if e.confidence == "confirmed"]

    @property
    def unresolved_edges(self) -> list[DependencyEdge]:
        return [e for e in self.edges if e.confidence == "unresolved"]

    @property
    def unresolved_by_reason(self) -> dict[str, list[DependencyEdge]]:
        """Group unresolved edges by their reason code for reporting."""
        result: dict[str, list[DependencyEdge]] = {}
        for edge in self.unresolved_edges:
            key = edge.unresolved_reason or "unknown"
            result.setdefault(key, []).append(edge)
        return result

    @property
    def overall_confidence(self) -> float:
        """Backward-compat single float — use .confidence for the full breakdown."""
        if self.confidence:
            return self.confidence.score_confidence
        if not self.scan_metadata:
            return 0.0
        m = self.scan_metadata
        if m.total_files == 0:
            return 0.0
        return round(
            (m.parse_success_rate * 0.6)
            + ((m.files_scanned / m.total_files) * 0.4),
            3,
        )

    def ui_confidence_label(self) -> UITruthLabel:
        """The truth label to show next to the confidence score in the UI."""
        unresolved_count = len(self.unresolved_edges)
        if self.confidence:
            return TruthLabels.from_confidence_breakdown(self.confidence, unresolved_count)
        return TruthLabels.confidence_low("Scan metadata unavailable")
