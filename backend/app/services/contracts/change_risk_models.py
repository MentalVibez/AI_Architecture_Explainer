"""
app/services/contracts/change_risk_models.py

Data contracts for the change risk analyzer.

Follows the same design rules as onboarding_models.py:
- ScanState is the only way to represent presence/absence.
- EvidenceSignal ties every claim to a source file and a rule.
- Absence evidence is explicit: when something was checked and not found,
  a signal with source_file="<repo_root>" records what was checked.
- Detector output (ChangeRiskEvidence) is separate from scored output
  (ChangeRisk) so detector tests and scorer tests can be split cleanly.
- BlastRadiusHotspot carries a reason — never just a path.
- RiskItem evidence list must not be empty — use absence signal if needed.

Change risk answers one question: "How safe is it to make a change here?"
It does not answer "will this change break things." That is a runtime claim.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field

# Re-use shared primitives from onboarding_models
# In your real repo these live in the same contracts package
from app.services.contracts.onboarding_models import (
    EvidenceSignal,
    RiskItem,
    RiskLevel,
    ScanState,
)


# ─────────────────────────────────────────────────────────
# Hotspot model
# A file or directory that, if changed, likely affects many other parts.
# ─────────────────────────────────────────────────────────

class HotspotCategory(str, Enum):
    AUTH        = "auth"        # auth middleware, session handling, permissions
    CONFIG      = "config"      # central config, env loading, settings classes
    CORE        = "core"        # shared utilities, base classes, common imports
    MIGRATION   = "migration"   # DB schema change files
    ROUTE_HUB   = "route_hub"   # single file registering many routes


class BlastRadiusHotspot(BaseModel):
    """
    A location in the repo that, if changed, has wide-reaching impact.

    path:     repo-relative path to the file or directory.
    category: coarse grouping for UI bucketing.
    reason:   one sentence — why is this a hotspot?
              Must be derived from evidence, not LLM inference.
    evidence: signals that identified this as a hotspot.
    """
    path:     str
    category: HotspotCategory
    reason:   str
    evidence: list[EvidenceSignal] = Field(default_factory=list)


# ─────────────────────────────────────────────────────────
# Subsection signal models — one per detector
# ─────────────────────────────────────────────────────────

class CISignal(BaseModel):
    """Result of CI workflow detection."""
    scan_state:     ScanState           = ScanState.NOT_FOUND
    platforms:      list[str]           = Field(default_factory=list)  # ["github_actions", "gitlab_ci"]
    has_test_gate:  bool                = False   # true if CI runs tests before merge
    has_lint_gate:  bool                = False
    signals:        list[EvidenceSignal] = Field(default_factory=list)


class TestGateSignal(BaseModel):
    """Result of test gate detection — separate from CI presence."""
    __test__ = False  # prevent pytest collection
    scan_state:     ScanState           = ScanState.NOT_FOUND
    frameworks:     list[str]           = Field(default_factory=list)
    has_coverage:   bool                = False
    signals:        list[EvidenceSignal] = Field(default_factory=list)


class MigrationRiskSignal(BaseModel):
    """
    Result of migration folder detection.

    migration_paths: directories or files identified as containing migrations.
    has_migration_tests: True if test files referencing migrations were found.
    A migration folder without tests is a medium/high risk signal.
    """
    scan_state:           ScanState           = ScanState.NOT_FOUND
    migration_paths:      list[str]           = Field(default_factory=list)
    has_migration_tests:  bool                = False
    signals:              list[EvidenceSignal] = Field(default_factory=list)


class ConfigRiskSignal(BaseModel):
    """
    Result of central config / env loading detection.

    config_paths: files that centralise app configuration.
    These are not automatically hotspots — they become hotspots only
    when they are imported by many other modules (that requires an
    import graph, which is a future detector).
    For v1: flag presence of central config as a signal, not a hotspot.
    """
    scan_state:    ScanState            = ScanState.NOT_FOUND
    config_paths:  list[str]            = Field(default_factory=list)
    signals:       list[EvidenceSignal] = Field(default_factory=list)


class HotspotSignal(BaseModel):
    """
    Aggregated blast radius hotspots from pattern detection.

    hotspots: files/dirs flagged as high-impact change points.
    Sorted by category then path for determinism.
    """
    scan_state: ScanState                   = ScanState.NOT_FOUND
    hotspots:   list[BlastRadiusHotspot]    = Field(default_factory=list)
    signals:    list[EvidenceSignal]        = Field(default_factory=list)


# ─────────────────────────────────────────────────────────
# ChangeRiskEvidence — raw detector output, no scores
# ─────────────────────────────────────────────────────────

class ChangeRiskEvidence(BaseModel):
    """
    Aggregated raw output from all change risk detectors.

    Each subsection carries its own scan_state.
    A failure in one section does not corrupt others.
    """
    ci:             CISignal            = Field(default_factory=CISignal)
    test_gates:     TestGateSignal      = Field(default_factory=TestGateSignal)
    migration_risk: MigrationRiskSignal = Field(default_factory=MigrationRiskSignal)
    config_risk:    ConfigRiskSignal    = Field(default_factory=ConfigRiskSignal)
    hotspots:       HotspotSignal       = Field(default_factory=HotspotSignal)
    scan_errors:    list[str]           = Field(default_factory=list)


# ─────────────────────────────────────────────────────────
# ChangeRisk — scored output
# ─────────────────────────────────────────────────────────

class ChangeRisk(BaseModel):
    """
    Scored output of the change risk analyzer.

    score: 0–100. Higher = riskier to make changes.
    Same scan_state / score / level / confidence contract as SetupRisk.

    safe_to_change:  list of path patterns that are lower-risk touch points.
    risky_to_change: list of path patterns with known blast radius.

    Neither list makes runtime guarantees — they reflect static signals only.
    """
    scan_state: ScanState

    score:      Optional[int]       = None
    level:      Optional[RiskLevel] = None
    confidence: float               = Field(default=0.0, ge=0.0, le=1.0)

    ci:             CISignal            = Field(default_factory=CISignal)
    test_gates:     TestGateSignal      = Field(default_factory=TestGateSignal)
    migration_risk: MigrationRiskSignal = Field(default_factory=MigrationRiskSignal)
    config_risk:    ConfigRiskSignal    = Field(default_factory=ConfigRiskSignal)
    hotspots:       HotspotSignal       = Field(default_factory=HotspotSignal)

    blast_radius_hotspots: list[BlastRadiusHotspot] = Field(default_factory=list)
    safe_to_change:        list[str]                 = Field(default_factory=list)
    risky_to_change:       list[str]                 = Field(default_factory=list)

    risks:       list[RiskItem]      = Field(default_factory=list)
    evidence:    list[EvidenceSignal] = Field(default_factory=list)
    scan_errors: list[str]           = Field(default_factory=list)
