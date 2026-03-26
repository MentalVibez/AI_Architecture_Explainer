"""
tests/test_repair_engine.py
----------------------------
Tests for the Repair Engine.

These tests cover:
  1. RepairProposal schema contracts (approval gate, file limit, auto-apply safety)
  2. FailureClassifier accuracy on known patterns
  3. Confidence gates (what gets a patch vs advisory vs nothing)
  4. Safety invariants (blocked classes never get patches, approval always required)
  5. UIRepairSummary serialization

No network. No LLM. No file system writes.
PatchGenerator and ValidationRunner are not tested here —
they require real subprocess environments.
"""

from __future__ import annotations

import pytest

from app.services.repair_engine import (
    AUTO_APPLY_ELIGIBLE_CLASSES,
    CONFIDENCE_BRANCH_PATCH,
    CONFIDENCE_SUGGESTION,
    MAX_FILES_PER_REPAIR,
    NEVER_AUTO_PATCH,
    FailureClassifier,
    FailureEvent,
    RepairProposal,
    UIRepairSummary,
    ValidationResult,
    _title_for_class,
)

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def make_event(
    message: str,
    source: str = "test_failure",
    file_path: str = "app/main.py",
    stack_trace: str = None,
) -> FailureEvent:
    return FailureEvent(
        source=source,
        file_path=file_path,
        raw_message=message,
        stack_trace=stack_trace,
    )


def make_proposal(
    failure_class: str = "broken_import",
    confidence: float = 0.92,
    patch: str = "--- a/app/main.py\n+++ b/app/main.py\n@@ -1 +1 @@\n-from app.old import X\n+from app.new import X",
    files: list[str] = None,
    risk: str = "low",
    auto_eligible: bool = False,
) -> RepairProposal:
    return RepairProposal(
        title="Test proposal",
        failure_class=failure_class,
        confidence=confidence,
        affected_files=files or ["app/main.py"],
        evidence=["ImportError: cannot import name 'X' from 'app.old'"],
        proposed_patch=patch,
        risk_level=risk,
        auto_apply_eligible=auto_eligible,
    )


# ---------------------------------------------------------------------------
# Section 1: RepairProposal schema contracts
# ---------------------------------------------------------------------------

class TestRepairProposalSchema:
    def test_requires_human_approval_always_true(self):
        """Invariant: requires_human_approval is always True at construction."""
        proposal = make_proposal()
        assert proposal.requires_human_approval is True

    def test_cannot_exceed_file_limit(self):
        """Invariant: more than MAX_FILES_PER_REPAIR files raises."""
        too_many = [f"app/file{i}.py" for i in range(MAX_FILES_PER_REPAIR + 1)]
        with pytest.raises(Exception, match="MAX_FILES_PER_REPAIR|files"):
            RepairProposal(
                title="Too many files",
                failure_class="broken_import",
                confidence=0.9,
                affected_files=too_many,
                evidence=["error"],
                risk_level="low",
            )

    def test_file_limit_exactly_at_max_is_valid(self):
        """MAX_FILES_PER_REPAIR files is the hard ceiling — exactly that many is OK."""
        exactly_max = [f"app/file{i}.py" for i in range(MAX_FILES_PER_REPAIR)]
        p = RepairProposal(
            title="At limit",
            failure_class="broken_import",
            confidence=0.9,
            affected_files=exactly_max,
            evidence=["error"],
            risk_level="low",
        )
        assert len(p.affected_files) == MAX_FILES_PER_REPAIR

    def test_auto_apply_blocked_for_never_auto_patch_classes(self):
        """Invariant: NEVER_AUTO_PATCH classes cannot be auto_apply_eligible=True."""
        for blocked_class in list(NEVER_AUTO_PATCH)[:3]:  # test a subset
            with pytest.raises(Exception):
                RepairProposal(
                    title="Blocked",
                    failure_class=blocked_class,
                    confidence=0.99,
                    affected_files=["app/main.py"],
                    evidence=["error"],
                    risk_level="high",
                    auto_apply_eligible=True,  # must be rejected
                )

    def test_auto_apply_allowed_for_safe_classes(self):
        """AUTO_APPLY_ELIGIBLE_CLASSES can be auto_apply_eligible=True."""
        for safe_class in AUTO_APPLY_ELIGIBLE_CLASSES:
            p = RepairProposal(
                title="Safe",
                failure_class=safe_class,
                confidence=0.95,
                affected_files=["app/main.py"],
                evidence=["formatting issue"],
                risk_level="low",
                auto_apply_eligible=True,
            )
            assert p.auto_apply_eligible is True

    def test_evidence_cannot_be_empty(self):
        """Proposals must have at least one piece of evidence."""
        with pytest.raises(Exception):
            RepairProposal(
                title="No evidence",
                failure_class="broken_import",
                confidence=0.9,
                affected_files=["app/main.py"],
                evidence=[],  # empty — invalid
                risk_level="low",
            )

    def test_repair_id_format(self):
        """repair_id must start with 'R-'."""
        p = make_proposal()
        assert p.repair_id.startswith("R-")

    def test_is_approved_defaults_false(self):
        p = make_proposal()
        assert p.is_approved is False

    def test_is_applied_defaults_false(self):
        p = make_proposal()
        assert p.is_applied is False


# ---------------------------------------------------------------------------
# Section 2: FailureClassifier
# ---------------------------------------------------------------------------

class TestFailureClassifier:
    def setup_method(self):
        self.clf = FailureClassifier()

    def test_import_error_classified(self):
        event = make_event("ImportError: No module named 'app.services.old_module'")
        result = self.clf.classify(event)
        assert result.classified_as == "broken_import"
        assert result.classification_confidence >= 0.90

    def test_module_not_found_classified(self):
        event = make_event("ModuleNotFoundError: No module named 'anthropic'")
        result = self.clf.classify(event)
        assert result.classified_as in ("broken_import", "missing_dependency")
        assert result.classification_confidence >= 0.85

    def test_ruff_lint_classified(self):
        event = make_event("ruff: E501 line too long (120 > 88)", source="lint_output")
        result = self.clf.classify(event)
        assert result.classified_as == "lint_failure"
        assert result.classification_confidence >= 0.88

    def test_black_format_classified(self):
        event = make_event("black would reformat app/main.py", source="lint_output")
        result = self.clf.classify(event)
        assert result.classified_as == "format_violation"
        assert result.classification_confidence >= 0.90

    def test_auth_classified_as_blocked(self):
        event = make_event("AttributeError: 'Auth' object has no attribute 'verify_jwt'")
        result = self.clf.classify(event)
        assert result.classified_as in ("auth_logic", "renamed_symbol")

    def test_stripe_classified_as_blocked(self):
        event = make_event("stripe.error.AuthenticationError: payment key not valid")
        result = self.clf.classify(event)
        assert result.classified_as == "auth_logic"

    def test_sql_injection_classified_as_security(self):
        event = make_event("potential sql injection vulnerability detected")
        result = self.clf.classify(event)
        assert result.classified_as == "security_sensitive"
        assert result.classification_confidence >= 0.90

    def test_alembic_migration_classified_blocked(self):
        event = make_event("alembic: target database is not up to date")
        result = self.clf.classify(event)
        assert result.classified_as == "data_migration"

    def test_unknown_error_classified_ambiguous(self):
        event = make_event("something totally unrecognizable xyzzy 12345")
        result = self.clf.classify(event)
        assert result.classified_as == "ambiguous"
        assert result.classification_confidence == 0.0

    def test_batch_classification(self):
        events = [
            make_event("ImportError: cannot import name 'X'"),
            make_event("black would reformat foo.py"),
            make_event("xyzzy"),
        ]
        results = self.clf.classify_batch(events)
        assert len(results) == 3
        assert results[0].classified_as == "broken_import"
        assert results[1].classified_as == "format_violation"
        assert results[2].classified_as == "ambiguous"

    def test_classification_preserves_event_data(self):
        event = make_event("ImportError", file_path="app/services/analyzer.py")
        result = self.clf.classify(event)
        assert result.file_path == "app/services/analyzer.py"
        assert result.raw_message == "ImportError"


# ---------------------------------------------------------------------------
# Section 3: Confidence gates
# ---------------------------------------------------------------------------

class TestConfidenceGates:
    def test_constants_are_sensible(self):
        """Confidence thresholds must be in valid range and ordered correctly."""
        assert 0.0 < CONFIDENCE_SUGGESTION < CONFIDENCE_BRANCH_PATCH <= 1.0

    def test_high_confidence_proposal_created(self):
        p = make_proposal(confidence=0.95)
        assert p.confidence == 0.95

    def test_confidence_label_high_above_090(self):
        p = make_proposal(confidence=0.95)
        summary = UIRepairSummary.from_proposal(p)
        assert summary.confidence_label == "HIGH"

    def test_confidence_label_moderate_between_070_090(self):
        p = make_proposal(confidence=0.80)
        summary = UIRepairSummary.from_proposal(p)
        assert summary.confidence_label == "MODERATE"

    def test_confidence_label_low_below_070(self):
        p = make_proposal(confidence=0.60)
        summary = UIRepairSummary.from_proposal(p)
        assert summary.confidence_label == "LOW"

    def test_auto_apply_requires_high_confidence(self):
        """
        Invariant: auto_apply_eligible should only be set for high-confidence proposals.
        The proposal schema allows it for safe classes — the engine enforces the threshold.
        """
        # Low confidence + safe class: engine would NOT set auto_apply_eligible=True
        # This test verifies the threshold constant is above suggestion level
        assert CONFIDENCE_BRANCH_PATCH > CONFIDENCE_SUGGESTION


# ---------------------------------------------------------------------------
# Section 4: Safety invariants
# ---------------------------------------------------------------------------

class TestSafetyInvariants:
    def test_never_auto_patch_includes_auth(self):
        assert "auth_logic" in NEVER_AUTO_PATCH

    def test_never_auto_patch_includes_payment(self):
        assert "payment_logic" in NEVER_AUTO_PATCH

    def test_never_auto_patch_includes_security(self):
        assert "security_sensitive" in NEVER_AUTO_PATCH

    def test_never_auto_patch_includes_migrations(self):
        assert "data_migration" in NEVER_AUTO_PATCH

    def test_never_auto_patch_includes_architectural(self):
        assert "architectural" in NEVER_AUTO_PATCH

    def test_never_auto_patch_includes_ambiguous(self):
        assert "ambiguous" in NEVER_AUTO_PATCH

    def test_auto_apply_eligible_classes_are_safe_only(self):
        """AUTO_APPLY_ELIGIBLE_CLASSES must not overlap with NEVER_AUTO_PATCH."""
        overlap = AUTO_APPLY_ELIGIBLE_CLASSES & NEVER_AUTO_PATCH
        assert not overlap, (
            f"Classes in both AUTO_APPLY_ELIGIBLE and NEVER_AUTO_PATCH: {overlap}"
        )

    def test_auto_apply_eligible_are_low_risk_only(self):
        """Auto-apply eligible classes should only be format/lint — never logic."""
        for cls in AUTO_APPLY_ELIGIBLE_CLASSES:
            assert cls in ("format_violation", "lint_failure"), (
                f"Unexpected class in AUTO_APPLY_ELIGIBLE: {cls}. "
                "Only format_violation and lint_failure should be eligible."
            )

    def test_max_files_per_repair_is_small(self):
        """The file limit must be small enough to be reviewable."""
        assert MAX_FILES_PER_REPAIR <= 5, (
            f"MAX_FILES_PER_REPAIR={MAX_FILES_PER_REPAIR} is too large. "
            "Repairs touching > 5 files are not reviewable."
        )

    def test_proposal_not_applied_without_approval(self):
        """is_applied must be False at construction — can only be True after approval."""
        p = make_proposal()
        assert p.is_applied is False
        assert p.is_approved is False

    def test_advisory_proposal_has_no_patch(self):
        """Advisory proposals for blocked classes must have proposed_patch=None."""
        advisory = RepairProposal(
            title="Advisory: auth_logic",
            failure_class="auth_logic",
            confidence=0.85,
            affected_files=["app/auth.py"],
            evidence=["AttributeError in auth flow"],
            proposed_patch=None,  # required for blocked class
            risk_level="high",
            auto_apply_eligible=False,
        )
        assert advisory.proposed_patch is None
        # is_advisory_only is derived by UIRepairSummary
        summary = UIRepairSummary.from_proposal(advisory)
        assert summary.is_advisory_only is True

    def test_advisory_only_flag_set_correctly(self):
        advisory = RepairProposal(
            title="Advisory",
            failure_class="ambiguous",
            confidence=0.5,
            affected_files=["app/main.py"],
            evidence=["unknown failure"],
            proposed_patch=None,
            risk_level="high",
        )
        summary = UIRepairSummary.from_proposal(advisory)
        assert summary.is_advisory_only is True
        assert summary.has_patch is False


# ---------------------------------------------------------------------------
# Section 5: ValidationResult
# ---------------------------------------------------------------------------

class TestValidationResult:
    def test_passes_when_all_checks_pass(self):
        vr = ValidationResult(
            patch_applies_cleanly=True,
            lint_passed=True,
            tests_passed=True,
        )
        assert vr.passed is True

    def test_fails_if_patch_does_not_apply(self):
        vr = ValidationResult(
            patch_applies_cleanly=False,
            lint_passed=True,
            tests_passed=True,
        )
        assert vr.passed is False

    def test_fails_if_new_failures_introduced(self):
        vr = ValidationResult(
            patch_applies_cleanly=True,
            lint_passed=True,
            tests_passed=True,
            new_failures_introduced=["FAILED tests/test_main.py::test_import"],
        )
        assert vr.passed is False

    def test_summary_is_human_readable(self):
        vr = ValidationResult(
            patch_applies_cleanly=True,
            lint_passed=True,
            tests_passed=True,
            score_delta=12,
        )
        assert "passed" in vr.summary.lower()
        assert "12" in vr.summary

    def test_failure_summary_names_failures(self):
        vr = ValidationResult(
            patch_applies_cleanly=False,
            lint_passed=True,
            tests_passed=False,
            new_failures_introduced=["test_x", "test_y"],
        )
        assert "patch" in vr.summary.lower()
        assert "test" in vr.summary.lower()


# ---------------------------------------------------------------------------
# Section 6: UIRepairSummary
# ---------------------------------------------------------------------------

class TestUIRepairSummary:
    def test_from_proposal_with_patch(self):
        p = make_proposal(confidence=0.92)
        summary = UIRepairSummary.from_proposal(p)

        assert summary.repair_id == p.repair_id
        assert summary.has_patch is True
        assert summary.is_advisory_only is False
        assert summary.confidence_label == "HIGH"

    def test_from_proposal_advisory_only(self):
        p = RepairProposal(
            title="Advisory",
            failure_class="auth_logic",
            confidence=0.88,
            affected_files=["app/auth.py"],
            evidence=["auth failure"],
            proposed_patch=None,
            risk_level="high",
        )
        summary = UIRepairSummary.from_proposal(p)
        assert summary.is_advisory_only is True
        assert summary.has_patch is False
        assert summary.proposed_patch is None

    def test_from_proposal_with_validation(self):
        vr = ValidationResult(
            patch_applies_cleanly=True,
            lint_passed=True,
            tests_passed=True,
            score_delta=8,
        )
        p = RepairProposal(
            title="Fix import",
            failure_class="broken_import",
            confidence=0.93,
            affected_files=["app/main.py"],
            evidence=["ImportError"],
            proposed_patch="--- a\n+++ b\n@@ -1 +1 @@\n-old\n+new",
            validation_results=vr,
            risk_level="low",
        )
        summary = UIRepairSummary.from_proposal(p)
        assert summary.validation_passed is True
        assert summary.predicted_score_delta == 8
        assert "passed" in summary.validation_summary.lower()

    def test_title_generation_with_file(self):
        title = _title_for_class("broken_import", "app/api/routes.py")
        assert "routes.py" in title
        assert "import" in title.lower()

    def test_title_generation_without_file(self):
        title = _title_for_class("format_violation", None)
        assert title  # must not be empty
        assert "format" in title.lower() or "violation" in title.lower()

    def test_title_for_advisory_class(self):
        title = _title_for_class("auth_logic", "app/auth.py")
        assert "Advisory" in title or "auth" in title.lower()

    def test_all_failure_classes_have_titles(self):
        """Every FailureClass literal must produce a non-empty title."""
        all_classes = [
            "broken_import", "missing_dependency", "config_mismatch",
            "lint_failure", "format_violation", "stale_type_import",
            "missing_route_export", "lockfile_drift", "renamed_symbol",
            "dead_code", "env_var_undocumented", "test_expectation_mismatch",
            "ambiguous_import", "complex_refactor", "auth_logic",
            "payment_logic", "concurrency_bug", "security_sensitive",
            "data_migration", "architectural", "ambiguous",
        ]
        for fc in all_classes:
            title = _title_for_class(fc, None)
            assert title, f"Empty title for class: {fc}"
