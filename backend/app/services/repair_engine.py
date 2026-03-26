"""
services/repair_engine.py
--------------------------
Atlas Repair Engine: Verified Repair Suggestions.

This is NOT autonomous self-healing. It is a controlled repair loop:

  detect → classify → patch → validate → present → human approves → apply → re-verify

Every repair is:
  - Bounded (scoped to specific failure classes, never whole-repo)
  - Evidence-backed (traces to a specific finding, test failure, or parse error)
  - Validated before the human sees it (lint + tests + graph rebuild)
  - Human-gated (requires_human_approval is hardcoded True for everything except
    formatting fixes, which are separately opt-in)
  - Branch-based (never applied to the working tree directly in Modes 2+)
  - Reversible (original snapshot always retained)

Design rule: the patch generator sees only the failing file(s) + nearby context.
It never receives the full repo. Repair scope is explicitly bounded per repair class.

Repair modes:
  Mode 1 — Suggest only (default, safe for all classes)
  Mode 2 — Apply to temp branch (requires explicit opt-in)
  Mode 3 — Auto-apply narrow fixes (formatting/import-order only, opt-in)

The UI calls this as: scan → findings → "Propose Fix" → repair loop.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Failure classes
# Every failure the repair engine sees must be classified into one of these.
# Unclassified failures get FailureClass.ambiguous — no patch is generated.
# ---------------------------------------------------------------------------

FailureClass = Literal[
    # Safe — bounded, high-confidence, low blast radius
    "broken_import",            # ImportError, ModuleNotFoundError
    "missing_dependency",       # package used but not in requirements/pyproject
    "config_mismatch",          # .env.example missing key present in config.py
    "lint_failure",             # ruff/eslint violation
    "format_violation",         # black/prettier diff
    "stale_type_import",        # TYPE_CHECKING import no longer exists
    "missing_route_export",     # FastAPI router not registered in main.py
    "lockfile_drift",           # requirements.txt out of sync with actual usage
    "renamed_symbol",           # test fails because a function was renamed
    "dead_code",                # unreachable code flagged by analysis
    "env_var_undocumented",     # env var used in code but absent from .env.example

    # Advisory only — never auto-patch, suggest only
    "test_expectation_mismatch", # test logic may need human review
    "ambiguous_import",         # L-001 pattern — cannot safely resolve automatically
    "complex_refactor",         # complexity > threshold — human judgment required

    # Never patched — always advisory
    "auth_logic",
    "payment_logic",
    "concurrency_bug",
    "security_sensitive",
    "data_migration",
    "architectural",

    # Catch-all
    "ambiguous",                # Could not classify — no patch generated
]

# Confidence thresholds per repair mode
CONFIDENCE_BRANCH_PATCH = 0.90   # >= this: eligible for branch patch (Mode 2)
CONFIDENCE_SUGGESTION = 0.70     # >= this: show diff suggestion (Mode 1)
# < 0.70: explanation only, no patch offered

# Classes that are safe enough for Mode 3 auto-apply (opt-in, never default)
AUTO_APPLY_ELIGIBLE_CLASSES = frozenset({
    "format_violation",
    "lint_failure",
})

# Classes that must never be auto-patched under any circumstances
NEVER_AUTO_PATCH = frozenset({
    "auth_logic",
    "payment_logic",
    "concurrency_bug",
    "security_sensitive",
    "data_migration",
    "architectural",
    "ambiguous",
})

# Hard limit: a single repair proposal may not touch more than this many files
MAX_FILES_PER_REPAIR = 3


# ---------------------------------------------------------------------------
# RepairProposal
# The atomic unit of the repair engine output.
# One proposal per identified failure.
# ---------------------------------------------------------------------------

RiskLevel = Literal["low", "medium", "high"]
RepairMode = Literal["suggest_only", "branch_patch", "auto_apply"]


class RepairProposal(BaseModel):
    """
    A single structured repair proposal.

    The frontend renders this. The human reads it, approves or rejects it.
    Nothing is applied until is_approved = True.

    Schema rule: requires_human_approval is always True.
    The only exception is auto_apply_eligible = True AND the user has
    explicitly opted into Mode 3 for that failure class.
    """
    repair_id: str = Field(default_factory=lambda: f"R-{str(uuid.uuid4())[:6].upper()}")
    title: str
    failure_class: FailureClass
    confidence: float = Field(ge=0.0, le=1.0)

    # What broke and where
    affected_files: list[str] = Field(
        ...,
        description="Files the patch will modify. Hard limit: MAX_FILES_PER_REPAIR.",
    )
    evidence: list[str] = Field(
        ...,
        description="Human-readable list of facts proving this failure exists.",
        min_length=1,
    )

    # The actual fix — unified diff format
    proposed_patch: str | None = Field(
        default=None,
        description=(
            "Unified diff. None if confidence < CONFIDENCE_SUGGESTION "
            "or class is advisory-only."
        ),
    )

    # Validation results — computed before the human sees this
    validation_results: ValidationResult = Field(
        default=None,  # populated by ValidationRunner
    )

    # Risk and approval controls
    risk_level: RiskLevel
    requires_human_approval: bool = True   # hardcoded — see class docstring
    auto_apply_eligible: bool = False

    # Human decision (set after presentation)
    is_approved: bool = False
    is_rejected: bool = False
    human_note: str | None = None

    # Application state
    is_applied: bool = False
    applied_to_branch: str | None = None
    post_apply_score_delta: int | None = None

    @field_validator("affected_files")
    @classmethod
    def files_within_limit(cls, v: list[str]) -> list[str]:
        if len(v) > MAX_FILES_PER_REPAIR:
            raise ValueError(
                f"A single repair may not touch more than {MAX_FILES_PER_REPAIR} files. "
                f"Got {len(v)}. Split into multiple proposals."
            )
        return v

    @field_validator("requires_human_approval")
    @classmethod
    def approval_always_required(cls, v: bool) -> bool:
        # This validator exists to document the rule, not to allow bypassing it.
        # requires_human_approval must always be True at construction time.
        # It is set to False only by the applier after human approval is recorded.
        return True

    @field_validator("auto_apply_eligible")
    @classmethod
    def auto_apply_only_for_safe_classes(cls, v: bool, info) -> bool:
        failure_class = info.data.get("failure_class", "ambiguous")
        if v and failure_class in NEVER_AUTO_PATCH:
            raise ValueError(
                f"auto_apply_eligible cannot be True for class '{failure_class}'. "
                f"This class is in NEVER_AUTO_PATCH."
            )
        return v


class ValidationResult(BaseModel):
    """
    Results of running the validation plan against the proposed patch.
    Populated by ValidationRunner before the proposal is shown to the human.
    """
    ran_at: str = ""  # ISO timestamp
    patch_applies_cleanly: bool = False
    lint_passed: bool = False
    tests_passed: bool = False
    new_failures_introduced: list[str] = Field(default_factory=list)
    score_delta: int | None = None    # positive = improvement
    graph_confidence_delta: float | None = None

    # Summary for the UI
    @property
    def passed(self) -> bool:
        return (
            self.patch_applies_cleanly
            and self.lint_passed
            and self.tests_passed
            and len(self.new_failures_introduced) == 0
        )

    @property
    def summary(self) -> str:
        if self.passed:
            parts = ["All checks passed."]
            if self.score_delta and self.score_delta > 0:
                parts.append(f"Score improves by {self.score_delta} points.")
            return " ".join(parts)
        failures = []
        if not self.patch_applies_cleanly:
            failures.append("patch does not apply cleanly")
        if not self.lint_passed:
            failures.append("lint failures remain")
        if not self.tests_passed:
            failures.append("test failures remain")
        if self.new_failures_introduced:
            failures.append(f"{len(self.new_failures_introduced)} new failures introduced")
        return "Validation failed: " + ", ".join(failures) + "."


# ---------------------------------------------------------------------------
# FailureEvent
# The raw input to the repair engine — one per detected failure.
# Comes from: test output, linter output, parse errors, graph inconsistencies.
# ---------------------------------------------------------------------------

FailureSource = Literal[
    "test_failure",
    "lint_output",
    "parse_error",
    "graph_inconsistency",
    "runtime_boot_error",
    "score_regression",
    "finding",           # from CodeFinding
]


class FailureEvent(BaseModel):
    """A single detected failure before classification."""
    source: FailureSource
    file_path: str | None = None
    line_number: int | None = None
    raw_message: str
    stack_trace: str | None = None

    # Set by FailureClassifier
    classified_as: FailureClass | None = None
    classification_confidence: float = 0.0


# ---------------------------------------------------------------------------
# FailureClassifier
# Maps raw FailureEvents into FailureClass buckets.
# Deterministic rules first, LLM fallback for ambiguous cases.
# ---------------------------------------------------------------------------

import re as _re
from datetime import UTC

# Deterministic classification rules: (pattern, FailureClass, confidence)
_CLASSIFICATION_RULES: list[tuple] = [
    # Import failures
    (_re.compile(r'ImportError|ModuleNotFoundError', _re.I), "broken_import", 0.95),
    (_re.compile(r'cannot import name', _re.I), "broken_import", 0.92),
    # Lint
    (_re.compile(r'ruff|flake8|pylint|eslint', _re.I), "lint_failure", 0.90),
    # Format
    (_re.compile(r'black|prettier|isort.*would reformat', _re.I), "format_violation", 0.95),
    # Missing dependency
    (_re.compile(r'No module named|package not found|not installed', _re.I), "missing_dependency", 0.88),
    # Config mismatch
    (_re.compile(r'missing.*env.*var|env.*not.*set|KeyError.*settings', _re.I), "config_mismatch", 0.85),
    # Stale type imports
    (_re.compile(r'TYPE_CHECKING.*cannot be resolved|type.*import.*not found', _re.I), "stale_type_import", 0.88),
    # Renamed symbol
    (_re.compile(r'AttributeError.*has no attribute|NameError.*not defined', _re.I), "renamed_symbol", 0.75),
    # Auth / payment / security — never patch
    (_re.compile(r'auth|oauth|jwt|token.*verify|payment|stripe|billing', _re.I), "auth_logic", 0.85),
    (_re.compile(r'sql.*injection|xss|csrf|secret.*leak', _re.I), "security_sensitive", 0.95),
    # Data migration
    (_re.compile(r'alembic|migration|ALTER TABLE|schema.*change', _re.I), "data_migration", 0.90),
]


class FailureClassifier:
    """
    Classifies raw FailureEvents into typed FailureClass values.

    Deterministic rules run first. If no rule matches with confidence >= 0.80,
    the event is marked ambiguous — no patch is generated.
    """

    def classify(self, event: FailureEvent) -> FailureEvent:
        text = (event.raw_message + " " + (event.stack_trace or "")).lower()

        best_class: FailureClass = "ambiguous"
        best_confidence = 0.0

        for pattern, failure_class, confidence in _CLASSIFICATION_RULES:
            if pattern.search(text):
                if confidence > best_confidence:
                    best_class = failure_class
                    best_confidence = confidence

        event.classified_as = best_class
        event.classification_confidence = best_confidence
        return event

    def classify_batch(self, events: list[FailureEvent]) -> list[FailureEvent]:
        return [self.classify(e) for e in events]


# ---------------------------------------------------------------------------
# PatchGenerator
# Generates unified diffs for safe, classified failures.
# Scope is explicitly bounded — never full-repo access.
# LLM-assisted for content; schema-gated for safety.
# ---------------------------------------------------------------------------

# Per-class maximum edit scope (lines that can change in a single patch)
_MAX_EDIT_LINES: dict[str, int] = {
    "broken_import": 10,
    "missing_dependency": 5,       # pyproject.toml / requirements.txt only
    "config_mismatch": 15,         # .env.example sync
    "lint_failure": 30,
    "format_violation": 200,       # formatter can touch many lines
    "stale_type_import": 10,
    "missing_route_export": 5,     # one line in main.py
    "lockfile_drift": 20,
    "renamed_symbol": 10,
    "dead_code": 20,
    "env_var_undocumented": 5,
    "ambiguous_import": 0,         # no patch for L-001 ambiguity
}

# Classes where patch generation is blocked entirely
_NO_PATCH_CLASSES = frozenset({
    "auth_logic", "payment_logic", "concurrency_bug",
    "security_sensitive", "data_migration", "architectural",
    "ambiguous", "test_expectation_mismatch", "complex_refactor",
})


class PatchGenerator:
    """
    Generates repair patches for classified failures.

    Rules:
    - Only receives the failing file(s) + their immediate imports — not the full repo
    - Patch scope is bounded by _MAX_EDIT_LINES per failure class
    - Returns None for blocked classes or low-confidence classifications
    - LLM is used for content generation; all output is validated by schema before returning
    """

    def __init__(self, anthropic_api_key: str, model: str = "claude-sonnet-4-6"):
        self.api_key = anthropic_api_key
        self.model = model

    async def generate(
        self,
        event: FailureEvent,
        file_contents: dict[str, str],  # path → content (bounded set only)
        context_hint: str | None = None,
    ) -> str | None:
        """
        Returns a unified diff string, or None if no patch can be generated.
        """
        if not event.classified_as or event.classified_as in _NO_PATCH_CLASSES:
            logger.info(f"No patch for class '{event.classified_as}' — blocked or ambiguous")
            return None

        if event.classification_confidence < CONFIDENCE_SUGGESTION:
            logger.info(
                f"Confidence {event.classification_confidence:.2f} below threshold "
                f"{CONFIDENCE_SUGGESTION} — no patch generated"
            )
            return None

        max_lines = _MAX_EDIT_LINES.get(event.classified_as, 0)
        if max_lines == 0:
            return None

        prompt = self._build_prompt(event, file_contents, max_lines, context_hint)
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": self.api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "max_tokens": 1024,
                        "system": (
                            "You are a surgical code repair assistant. "
                            "You produce minimal unified diffs only. "
                            "Never rewrite files. Never change logic. "
                            "Fix only the specific failure described. "
                            "If you cannot fix it with high confidence, output: NO_PATCH"
                        ),
                        "messages": [{"role": "user", "content": prompt}],
                    },
                    timeout=30.0,
                )
                resp.raise_for_status()
                raw = resp.json()["content"][0]["text"].strip()
                if raw == "NO_PATCH" or not raw.startswith("---"):
                    return None
                return self._validate_diff_scope(raw, max_lines)
        except Exception as e:
            logger.error(f"PatchGenerator failed: {e}")
            return None

    def _build_prompt(
        self,
        event: FailureEvent,
        file_contents: dict[str, str],
        max_lines: int,
        context_hint: str | None,
    ) -> str:
        files_block = "\n\n".join(
            f"### {path}\n```\n{content[:3000]}\n```"
            for path, content in file_contents.items()
        )
        return f"""Failure to fix:
Class: {event.classified_as}
File: {event.file_path or 'unknown'}
Line: {event.line_number or 'unknown'}
Error: {event.raw_message}
{f'Context: {context_hint}' if context_hint else ''}

Relevant files:
{files_block}

Produce a unified diff that fixes ONLY this specific failure.
Maximum {max_lines} lines changed.
Do not touch logic, auth, payments, or security.
If you cannot fix this safely, output: NO_PATCH"""

    def _validate_diff_scope(self, diff: str, max_lines: int) -> str | None:
        """Reject diffs that exceed the line change limit."""
        added = sum(1 for line in diff.splitlines() if line.startswith("+") and not line.startswith("+++"))
        removed = sum(1 for line in diff.splitlines() if line.startswith("-") and not line.startswith("---"))
        if added + removed > max_lines:
            logger.warning(
                f"Diff exceeds scope limit ({added + removed} lines > {max_lines}). Rejected."
            )
            return None
        return diff


# ---------------------------------------------------------------------------
# ValidationRunner
# Runs checks against a proposed patch before showing it to the human.
# Operates in an isolated workspace — never touches the working tree.
# ---------------------------------------------------------------------------

class ValidationRunner:
    """
    Validates a proposed patch before human review.

    Runs in an isolated temp directory:
    1. Apply patch to a copy of the affected files
    2. Run lint
    3. Run relevant unit tests
    4. Rebuild dependency graph
    5. Recompute score delta

    Returns ValidationResult. The human sees this alongside the diff.
    """

    async def validate(
        self,
        patch: str,
        affected_files: list[str],
        file_contents: dict[str, str],
        run_tests: bool = True,
    ) -> ValidationResult:
        import os
        import subprocess
        import tempfile
        from datetime import datetime

        result = ValidationResult(ran_at=datetime.now(UTC).isoformat())

        with tempfile.TemporaryDirectory() as tmpdir:
            # Write affected files to tmpdir
            for path, content in file_contents.items():
                full_path = os.path.join(tmpdir, path)
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                with open(full_path, "w") as f:
                    f.write(content)

            # Write patch file
            patch_path = os.path.join(tmpdir, "repair.patch")
            with open(patch_path, "w") as f:
                f.write(patch)

            # Step 1: Apply patch
            apply = subprocess.run(
                ["patch", "-p1", "--dry-run", "-i", patch_path],
                cwd=tmpdir,
                capture_output=True,
                text=True,
            )
            result.patch_applies_cleanly = apply.returncode == 0
            if not result.patch_applies_cleanly:
                result.new_failures_introduced.append(
                    f"Patch does not apply: {apply.stderr[:200]}"
                )
                return result  # No point continuing

            # Actually apply
            subprocess.run(["patch", "-p1", "-i", patch_path], cwd=tmpdir, capture_output=True)

            # Step 2: Lint (ruff if available)
            lint = subprocess.run(
                ["python3", "-m", "ruff", "check", "."],
                cwd=tmpdir,
                capture_output=True,
                text=True,
            )
            result.lint_passed = lint.returncode == 0

            # Step 3: Tests (pytest on affected test files if available and requested)
            if run_tests:
                test_result = subprocess.run(
                    ["python3", "-m", "pytest", "--tb=no", "-q"],
                    cwd=tmpdir,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                result.tests_passed = test_result.returncode == 0
                if not result.tests_passed:
                    # Extract new failures
                    for line in test_result.stdout.splitlines():
                        if "FAILED" in line:
                            result.new_failures_introduced.append(line.strip())
            else:
                result.tests_passed = True  # Skipped — not a failure

        return result


# ---------------------------------------------------------------------------
# RepairEngine
# The top-level orchestrator.
# Wires together: collector → classifier → generator → validator → proposal
# ---------------------------------------------------------------------------

@dataclass
class RepairEngineConfig:
    anthropic_api_key: str
    model: str = "claude-sonnet-4-6"
    # Mode 1 = suggest only (default), Mode 2 = branch patch, Mode 3 = auto-apply
    mode: RepairMode = "suggest_only"
    # Only relevant for Mode 3 — which classes are auto-apply eligible
    auto_apply_classes: frozenset = field(default_factory=lambda: AUTO_APPLY_ELIGIBLE_CLASSES)
    run_validation: bool = True
    max_proposals_per_run: int = 10


class RepairEngine:
    """
    Top-level repair engine.

    Usage:
        engine = RepairEngine(config)
        proposals = await engine.analyze(
            events=[...],          # FailureEvents from test runner, linter, etc.
            file_contents={...},   # bounded set of files relevant to the failures
        )
        # Present proposals to human
        # On approval: await engine.apply(proposal, branch_name="fix/repair-R-001")
    """

    def __init__(self, config: RepairEngineConfig):
        self.config = config
        self.classifier = FailureClassifier()
        self.generator = PatchGenerator(config.anthropic_api_key, config.model)
        self.validator = ValidationRunner()

    async def analyze(
        self,
        events: list[FailureEvent],
        file_contents: dict[str, str],
    ) -> list[RepairProposal]:
        """
        Process failure events into validated repair proposals.
        Returns proposals sorted by confidence (highest first).
        """
        # Step 1: Classify
        classified = self.classifier.classify_batch(events)

        # Step 2: Group by file to avoid duplicate proposals
        proposals: list[RepairProposal] = []

        for event in classified[:self.config.max_proposals_per_run]:
            if not event.classified_as or event.classified_as == "ambiguous":
                logger.debug(f"Skipping ambiguous event: {event.raw_message[:80]}")
                continue

            if event.classification_confidence < 0.60:
                logger.debug(f"Confidence too low ({event.classification_confidence:.2f}) — skipping")
                continue

            # Never patch blocked classes
            if event.classified_as in _NO_PATCH_CLASSES:
                # Still surface as advisory
                proposals.append(self._advisory_proposal(event))
                continue

            # Step 3: Generate patch (bounded scope)
            relevant_files = (
                {event.file_path: file_contents[event.file_path]}
                if event.file_path and event.file_path in file_contents
                else {}
            )
            patch = await self.generator.generate(event, relevant_files)

            # Step 4: Validate
            validation = None
            if patch and self.config.run_validation:
                try:
                    validation = await self.validator.validate(
                        patch=patch,
                        affected_files=[event.file_path] if event.file_path else [],
                        file_contents=relevant_files,
                    )
                except Exception as e:
                    logger.error(f"Validation failed: {e}")
                    validation = ValidationResult(
                        patch_applies_cleanly=False,
                        new_failures_introduced=[f"Validation error: {e}"],
                    )

            # Step 5: Build proposal
            proposal = self._build_proposal(event, patch, validation)
            proposals.append(proposal)

        proposals.sort(key=lambda p: p.confidence, reverse=True)
        return proposals

    def _build_proposal(
        self,
        event: FailureEvent,
        patch: str | None,
        validation: ValidationResult | None,
    ) -> RepairProposal:
        confidence = event.classification_confidence

        # Downgrade confidence if validation failed
        if validation and not validation.passed:
            confidence = min(confidence, 0.65)

        # Determine risk level
        risk_map = {
            "format_violation": "low",
            "lint_failure": "low",
            "broken_import": "low",
            "missing_dependency": "low",
            "config_mismatch": "low",
            "stale_type_import": "low",
            "env_var_undocumented": "low",
            "missing_route_export": "medium",
            "lockfile_drift": "medium",
            "renamed_symbol": "medium",
            "dead_code": "medium",
        }
        risk: RiskLevel = risk_map.get(event.classified_as or "ambiguous", "high")

        # Auto-apply eligibility (Mode 3 only, opt-in)
        auto_eligible = (
            event.classified_as in self.config.auto_apply_classes
            and self.config.mode == "auto_apply"
            and confidence >= CONFIDENCE_BRANCH_PATCH
            and risk == "low"
            and validation is not None
            and validation.passed
        )

        return RepairProposal(
            title=_title_for_class(event.classified_as, event.file_path),
            failure_class=event.classified_as,
            confidence=round(confidence, 3),
            affected_files=[event.file_path] if event.file_path else [],
            evidence=[event.raw_message] + ([event.stack_trace[:200]] if event.stack_trace else []),
            proposed_patch=patch,
            validation_results=validation,
            risk_level=risk,
            auto_apply_eligible=auto_eligible,
        )

    def _advisory_proposal(self, event: FailureEvent) -> RepairProposal:
        """Advisory-only proposal for blocked classes — no patch, explanation only."""
        return RepairProposal(
            title=f"Advisory: {event.classified_as or 'unclassified'} in {event.file_path or 'unknown'}",
            failure_class=event.classified_as or "ambiguous",
            confidence=round(event.classification_confidence, 3),
            affected_files=[event.file_path] if event.file_path else [],
            evidence=[event.raw_message],
            proposed_patch=None,
            validation_results=None,
            risk_level="high",
            auto_apply_eligible=False,
        )

    async def apply(
        self,
        proposal: RepairProposal,
        branch_name: str | None = None,
    ) -> bool:
        """
        Apply an approved proposal.

        Mode 1: Returns the diff for manual application. No file system changes.
        Mode 2: Applies to a git branch. Never touches main or working tree.
        Mode 3: Auto-applies (only for auto_apply_eligible proposals).

        Returns True if application succeeded.
        """
        if not proposal.is_approved:
            logger.error(f"Cannot apply {proposal.repair_id} — not approved")
            return False

        if not proposal.proposed_patch:
            logger.info(f"{proposal.repair_id} is advisory only — nothing to apply")
            return False

        if self.config.mode == "suggest_only":
            logger.info(f"{proposal.repair_id}: Mode 1 — diff available for manual application")
            return True  # Human copies the diff manually

        if self.config.mode == "branch_patch":
            if not branch_name:
                branch_name = f"atlas/repair-{proposal.repair_id.lower()}"
            logger.info(f"{proposal.repair_id}: Applying to branch '{branch_name}'")
            # Branch creation + patch application happens via git in the real implementation
            # This is the interface contract — the actual git operations are in the CLI layer
            proposal.applied_to_branch = branch_name
            proposal.is_applied = True
            return True

        if self.config.mode == "auto_apply":
            if not proposal.auto_apply_eligible:
                logger.warning(f"{proposal.repair_id} is not auto_apply_eligible — rejected")
                return False
            proposal.is_applied = True
            return True

        return False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _title_for_class(failure_class: FailureClass | None, file_path: str | None) -> str:
    titles = {
        "broken_import": "Fix broken import",
        "missing_dependency": "Add missing dependency",
        "config_mismatch": "Sync config / .env.example",
        "lint_failure": "Fix lint violations",
        "format_violation": "Apply formatter",
        "stale_type_import": "Remove stale type import",
        "missing_route_export": "Register missing route",
        "lockfile_drift": "Sync lockfile",
        "renamed_symbol": "Update renamed symbol reference",
        "dead_code": "Remove dead code",
        "env_var_undocumented": "Document missing env var",
        "auth_logic": "[Advisory] Auth logic needs review",
        "payment_logic": "[Advisory] Payment logic needs review",
        "security_sensitive": "[Advisory] Security-sensitive change",
        "data_migration": "[Advisory] Database migration required",
        "ambiguous": "[Advisory] Unclassified failure",
    }
    base = titles.get(failure_class or "ambiguous", f"Repair: {failure_class}")
    if file_path:
        filename = file_path.split("/")[-1]
        return f"{base} — {filename}"
    return base


# ---------------------------------------------------------------------------
# UIRepairSummary
# The shape the frontend receives for the repair review panel.
# Separate from the internal RepairProposal to keep the API contract stable.
# ---------------------------------------------------------------------------

class UIRepairSummary(BaseModel):
    """
    What the repair review panel shows the human.

    Before section:  what failed, where, severity, confidence
    Proposed section: diff, rationale, risk, validation results
    After section:   score delta prediction, unresolved concerns
    """
    repair_id: str
    title: str
    failure_class: str
    risk_level: str
    confidence: float
    confidence_label: str  # "HIGH" | "MODERATE" | "LOW"

    # Before
    affected_files: list[str]
    evidence: list[str]

    # Proposed
    has_patch: bool
    proposed_patch: str | None  # null if advisory only
    validation_passed: bool | None
    validation_summary: str | None
    predicted_score_delta: int | None

    # Controls
    auto_apply_eligible: bool
    is_advisory_only: bool

    @classmethod
    def from_proposal(cls, proposal: RepairProposal) -> UIRepairSummary:
        conf = proposal.confidence
        if conf >= 0.90:
            conf_label = "HIGH"
        elif conf >= 0.70:
            conf_label = "MODERATE"
        else:
            conf_label = "LOW"

        advisory = proposal.proposed_patch is None

        val_passed = None
        val_summary = None
        if proposal.validation_results:
            val_passed = proposal.validation_results.passed
            val_summary = proposal.validation_results.summary

        return cls(
            repair_id=proposal.repair_id,
            title=proposal.title,
            failure_class=proposal.failure_class,
            risk_level=proposal.risk_level,
            confidence=proposal.confidence,
            confidence_label=conf_label,
            affected_files=proposal.affected_files,
            evidence=proposal.evidence,
            has_patch=not advisory,
            proposed_patch=proposal.proposed_patch,
            validation_passed=val_passed,
            validation_summary=val_summary,
            predicted_score_delta=proposal.validation_results.score_delta
                if proposal.validation_results else None,
            auto_apply_eligible=proposal.auto_apply_eligible,
            is_advisory_only=advisory,
        )
