"""
backend/app/services/pipeline/claim_enforcer.py

ClaimEnforcer attaches the allowed claim boundary to every API response
and provides the tier disclosure text.

This is the mechanism that makes "we don't claim runtime correctness from
static analysis" an enforced contract rather than documentation.

Usage:
    enforcer = ClaimEnforcer(AnalysisTier.STATIC)
    assert enforcer.is_allowed(ClaimBoundary.SETUP_RISK)   # True
    assert not enforcer.is_allowed(ClaimBoundary.TESTS_PASS)  # True — blocked on static

The ClaimEnforcer is attached to every assembled result. The LLM
explanation layer must check it before generating any claim. If the
LLM receives a prompt asking it to state "this repo is safe to deploy,"
the enforcer gates that claim at the response layer.
"""

from __future__ import annotations

import os

from app.services.policy.tier_policy import (
    AnalysisTier,
    ClaimBoundary,
    NEVER_ALLOWED_CLAIMS,
    allowed_claims,
    is_claim_allowed,
)

class ClaimEnforcer:
    """
    Attached to every assembled result.
    Provides:
    - allowed: frozenset of ClaimBoundary values permitted for this tier
    - is_allowed(claim): check one claim
    - assert_allowed(claim): raises if not permitted
    - as_response_fields(): dict ready to merge into an API response
    """

    def __init__(self, tier: AnalysisTier):
        self.tier    = tier
        self.allowed = allowed_claims(tier)

    def is_allowed(self, claim: ClaimBoundary) -> bool:
        if claim in NEVER_ALLOWED_CLAIMS:
            return False
        return claim in self.allowed

    def assert_allowed(self, claim: ClaimBoundary) -> None:
        if not self.is_allowed(claim):
            raise ClaimViolation(
                f"Claim '{claim.value}' is not permitted for tier '{self.tier.value}'. "
                f"Allowed: {[c.value for c in self.allowed]}"
            )

    def as_response_fields(self) -> dict:
        """
        Returns a dict to merge into every API response.
        These fields make overclaiming impossible at the client level.
        """
        is_verified = self.tier == AnalysisTier.VERIFIED
        return {
            "analysis_tier":     self.tier.value,
            "runtime_verified":  is_verified,
            "executed_checks":   [],    # populated by verified worker if applicable
            "claim_boundary":    sorted(c.value for c in self.allowed),
            "never_claimed":     sorted(c.value for c in NEVER_ALLOWED_CLAIMS),
            "tier_disclosure":   (
                build_verified_disclosure() if is_verified
                else build_public_static_disclosure()
            ),
        }

class ClaimViolation(Exception):
    """Raised when a code path attempts to emit a disallowed claim."""
    pass

# ─────────────────────────────────────────────────────────
# Disclosure text
# These are the strings rendered in the UI and API response.
# They are policy — do not soften them.
# ─────────────────────────────────────────────────────────

def build_public_static_disclosure() -> str:
    return (
        "This analysis is based on static code inspection only. "
        "It detects structure, configuration, and likely risk signals from "
        "files and manifests. It does not execute code, run tests, or verify "
        "runtime behavior. Findings represent likely conditions, not confirmed facts."
    )

def build_verified_disclosure() -> str:
    return (
        "This analysis includes sandboxed runtime checks for the selected stack. "
        "Results reflect the checks that were executed in the isolated environment. "
        "A passing result means the selected checks passed under controlled conditions. "
        "It does not guarantee production correctness, deployment safety, or "
        "coverage of all possible runtime conditions."
    )
