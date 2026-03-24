"""
onboarding_models.py

Data contracts for the onboarding analysis pipeline.

Design rules:
- ScanState is the only way to represent presence/absence — no raw booleans.
- EvidenceSignal ties every claim to a source file and a rule.
- RiskItem carries a reason and a source rule, not free-form text.
- SetupRisk separates raw evidence (what was found) from scored output
  (what it means) so detector tests and scorer tests can be split cleanly.
- Confidence is NOT risk level. A repo can be high-risk / high-confidence
  or medium-risk / low-confidence. Both fields are required.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


# ─────────────────────────────────────────────────────────
# Core enums
# ─────────────────────────────────────────────────────────

class ScanState(str, Enum):
    FOUND       = "found"
    NOT_FOUND   = "not_found"
    SCAN_FAILED = "scan_failed"


class RiskLevel(str, Enum):
    LOW    = "low"
    MEDIUM = "medium"
    HIGH   = "high"


# ─────────────────────────────────────────────────────────
# Evidence primitive
# Every claim in SetupRisk traces back to one of these.
# ─────────────────────────────────────────────────────────

class EvidenceSignal(BaseModel):
    """
    A single verifiable observation.

    source_file: the repo-relative path that produced this signal,
                 or a synthetic key like "<repo_root>" when the signal
                 is absence of a file rather than presence.
    rule:        the detector rule that emitted this signal.
                 Use snake_case names, e.g. "python_os_getenv".
    detail:      optional human-readable note, e.g. the matched string.
    """
    source_file: str
    rule: str
    detail: Optional[str] = None


# ─────────────────────────────────────────────────────────
# Risk item
# ─────────────────────────────────────────────────────────

class RiskItem(BaseModel):
    """
    A single risk signal with a machine-readable category
    and a human-readable reason.

    category: coarse grouping for UI bucketing.
    reason:   one sentence.  Must be a template-filled string,
              not free-form LLM output.
    rule:     the rule name that generated this risk.
    evidence: signals that support this risk item.
    """
    category: str           # e.g. "env_vars", "start_commands", "services"
    reason: str
    rule: str
    evidence: list[EvidenceSignal] = Field(default_factory=list)


# ─────────────────────────────────────────────────────────
# Detector output
# Raw findings before any scoring.  Scorer reads this.
# ─────────────────────────────────────────────────────────

class SetupRiskEvidence(BaseModel):
    """
    Raw detector output.  No scores, no levels here.

    This is what the detector tests assert against.
    The scorer receives this and produces SetupRisk.
    """
    missing_env_vars: list[str]         = Field(default_factory=list)
    env_example_present: bool           = False
    likely_start_commands: list[str]    = Field(default_factory=list)
    required_services: list[str]        = Field(default_factory=list)
    detected_manifests: list[str]       = Field(default_factory=list)
    signals: list[EvidenceSignal]       = Field(default_factory=list)
    scan_errors: list[str]              = Field(default_factory=list)


# ─────────────────────────────────────────────────────────
# Final scored output
# Produced by the scorer from SetupRiskEvidence.
# ─────────────────────────────────────────────────────────

class SetupRisk(BaseModel):
    """
    Scored output of the setup risk analyzer.

    scan_state:  overall state of the scan.
                 SCAN_FAILED means we could not reliably collect evidence —
                 no score or level should be trusted.
    score:       0–100.  Higher = more risk.
    level:       human-readable band derived from score.
                 None only when scan_state == SCAN_FAILED.
    confidence:  0.0–1.0.  How much evidence we had to base the score on.
                 Distinct from risk level — a well-evidenced low-risk repo
                 has high confidence.  A sparse repo with few signals has
                 low confidence even if no risks were found.
    """
    scan_state: ScanState

    score: Optional[int]        = None      # None only if SCAN_FAILED
    level: Optional[RiskLevel]  = None      # None only if SCAN_FAILED
    confidence: float           = Field(default=0.0, ge=0.0, le=1.0)

    missing_env_vars: list[str]         = Field(default_factory=list)
    env_example_present: bool           = False
    likely_start_commands: list[str]    = Field(default_factory=list)
    required_services: list[str]        = Field(default_factory=list)
    detected_manifests: list[str]       = Field(default_factory=list)

    risks: list[RiskItem]               = Field(default_factory=list)
    evidence: list[EvidenceSignal]      = Field(default_factory=list)
    scan_errors: list[str]              = Field(default_factory=list)


# ─────────────────────────────────────────────────────────
# DebugReadiness — subsection models
#
# Each subsection is a discrete detector result.
# scan_state drives rendering — never infer from other fields.
# framework / tool fields are None when scan_state != FOUND.
# ─────────────────────────────────────────────────────────

class LoggingSignal(BaseModel):
    """
    Result of the structured logging detector.

    Plain print() calls do NOT set scan_state=FOUND.
    Only a recognizable structured logging framework does.
    print_only_detected is an explicit weak signal, not a positive result.
    """
    scan_state: ScanState                   = ScanState.NOT_FOUND
    framework: Optional[str]               = None   # "structlog"|"loguru"|"stdlib_logging"|"pino"|"winston"
    signals: list[EvidenceSignal]          = Field(default_factory=list)
    print_only_detected: bool              = False


class ErrorHandlingSignal(BaseModel):
    """Result of the exception handler / error middleware detector."""
    scan_state: ScanState                   = ScanState.NOT_FOUND
    framework: Optional[str]               = None
    handler_type: Optional[str]            = None   # "exception_handler"|"middleware"|"error_boundary"
    signals: list[EvidenceSignal]          = Field(default_factory=list)


class HealthCheckSignal(BaseModel):
    """Result of the health endpoint detector."""
    scan_state: ScanState                   = ScanState.NOT_FOUND
    routes_found: list[str]                = Field(default_factory=list)
    signals: list[EvidenceSignal]          = Field(default_factory=list)


class TracingSignal(BaseModel):
    """
    Result of the observability / tracing detector.
    sentry_found and otel_found are independent — both can be true.
    """
    scan_state: ScanState                   = ScanState.NOT_FOUND
    sentry_found: bool                     = False
    otel_found: bool                       = False
    signals: list[EvidenceSignal]          = Field(default_factory=list)


class TestHarnessSignal(BaseModel):
    """Result of the test framework detector."""
    __test__ = False  # prevent pytest collection
    scan_state: ScanState                   = ScanState.NOT_FOUND
    frameworks: list[str]                  = Field(default_factory=list)
    signals: list[EvidenceSignal]          = Field(default_factory=list)


# ─────────────────────────────────────────────────────────
# DebugReadinessEvidence — raw detector output, no scores
# ─────────────────────────────────────────────────────────

class DebugReadinessEvidence(BaseModel):
    """
    Aggregated raw output from all debug readiness detectors.
    Each subsection carries its own scan_state — one section failing
    does not corrupt others.
    """
    logging:         LoggingSignal         = Field(default_factory=LoggingSignal)
    error_handling:  ErrorHandlingSignal   = Field(default_factory=ErrorHandlingSignal)
    health_checks:   HealthCheckSignal     = Field(default_factory=HealthCheckSignal)
    tracing:         TracingSignal         = Field(default_factory=TracingSignal)
    test_harness:    TestHarnessSignal     = Field(default_factory=TestHarnessSignal)
    scan_errors:     list[str]             = Field(default_factory=list)


# ─────────────────────────────────────────────────────────
# DebugReadiness — scored output
# ─────────────────────────────────────────────────────────

class DebugReadiness(BaseModel):
    """
    Scored output of the debug readiness analyzer.
    score: 0-100. Higher = harder to debug (more risk).
    Same scan_state / score / level / confidence contract as SetupRisk.
    """
    scan_state: ScanState

    score: Optional[int]        = None
    level: Optional[RiskLevel]  = None
    confidence: float           = Field(default=0.0, ge=0.0, le=1.0)

    logging:        LoggingSignal        = Field(default_factory=LoggingSignal)
    error_handling: ErrorHandlingSignal  = Field(default_factory=ErrorHandlingSignal)
    health_checks:  HealthCheckSignal    = Field(default_factory=HealthCheckSignal)
    tracing:        TracingSignal        = Field(default_factory=TracingSignal)
    test_harness:   TestHarnessSignal    = Field(default_factory=TestHarnessSignal)

    risks:       list[RiskItem]          = Field(default_factory=list)
    evidence:    list[EvidenceSignal]    = Field(default_factory=list)
    scan_errors: list[str]              = Field(default_factory=list)
