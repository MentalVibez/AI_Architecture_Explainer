"""
Category-aware analysis depth model.

Depth is computed from which CATEGORIES of adapters ran, not just how many.
Running 3 lint adapters is not the same as running lint + security + dependency.

Adapter categories:
  lint        ruff, eslint
  security    bandit, semgrep
  secrets     gitleaks
  dependency  pip-audit, npm-audit
  typing      mypy, pyright

Depth levels:
  structural_only    No adapters ran
  lint_augmented     Lint only (ruff/eslint)
  security_augmented Lint + security/secrets
  full_toolchain     Lint + security + dependency (or secrets + dependency)

Why categories matter:
  - "3 adapters" could mean 3 lint tools → still shallow for production risk
  - "2 adapters" of lint + secrets → much stronger security signal
  - The depth label must reflect evidence quality, not just quantity
"""
from dataclasses import dataclass, field
from enum import Enum


class AnalysisDepth(str, Enum):
    STRUCTURAL_ONLY    = "structural_only"
    LINT_AUGMENTED     = "lint_augmented"
    SECURITY_AUGMENTED = "security_augmented"
    FULL_TOOLCHAIN     = "full_toolchain"


# Adapter → category mapping
ADAPTER_CATEGORIES: dict[str, str] = {
    "ruff":        "lint",
    "eslint":      "lint",
    "bandit":      "security",
    "semgrep":     "security",
    "gitleaks":    "secrets",
    "secret_patterns": "secrets",
    "pip_audit":   "dependency",
    "npm_audit":   "dependency",
    "mypy":        "typing",
    "pyright":     "typing",
    "hadolint":    "container",
    "actionlint":  "ci",
}


@dataclass
class DepthProfile:
    level: AnalysisDepth
    label: str
    description: str
    hiring_qualifier: str
    verdict_note: str
    confidence_floor: str
    allowed_strong_claims: bool
    categories_covered: list[str] = field(default_factory=list)


DEPTH_PROFILES: dict[AnalysisDepth, DepthProfile] = {
    AnalysisDepth.STRUCTURAL_ONLY: DepthProfile(
        level=AnalysisDepth.STRUCTURAL_ONLY,
        label="Structural only",
        description="Repository structure, hygiene, and process signals — no static analysis ran",
        hiring_qualifier="shows structural signals of",
        verdict_note="This verdict is based on structural signals only. Static analysis was unavailable, so code-level depth was not measured.",
        confidence_floor="Low",
        allowed_strong_claims=False,
    ),
    AnalysisDepth.LINT_AUGMENTED: DepthProfile(
        level=AnalysisDepth.LINT_AUGMENTED,
        label="Structural + lint analysis",
        description="Structure and hygiene signals plus code quality and style analysis",
        hiring_qualifier="shows signals of",
        verdict_note="This verdict combines structural analysis with code quality scanning. Security and dependency risk were not measured.",
        confidence_floor="Medium",
        allowed_strong_claims=False,
    ),
    AnalysisDepth.SECURITY_AUGMENTED: DepthProfile(
        level=AnalysisDepth.SECURITY_AUGMENTED,
        label="Structural + lint + security",
        description="Structure, lint, and security scanning — dependency risk not measured",
        hiring_qualifier="shows evidence of",
        verdict_note="This verdict includes security scanning. Dependency vulnerability assessment was not performed.",
        confidence_floor="Medium",
        allowed_strong_claims=False,
    ),
    AnalysisDepth.FULL_TOOLCHAIN: DepthProfile(
        level=AnalysisDepth.FULL_TOOLCHAIN,
        label="Full supported toolchain",
        description="Complete structural analysis with lint, security, secrets, and dependency scanning",
        hiring_qualifier="demonstrates",
        verdict_note="This verdict is backed by full structural, security, and dependency analysis.",
        confidence_floor="High",
        allowed_strong_claims=True,
    ),
}


def compute_depth(
    adapter_results: dict,
    succeeded_tools: list[str] | None = None,
) -> DepthProfile:
    """
    Compute analysis depth from which adapter categories were successfully covered.

    Args:
        adapter_results: dict[tool_name, AdapterResult] OR dict[tool_name, AdapterStatus]
        succeeded_tools: optional pre-computed list of succeeded tool names
    """
    from .depth import ADAPTER_CATEGORIES  # avoid circular

    if succeeded_tools is not None:
        tools = succeeded_tools
    else:
        tools = []
        for tool_name, result in adapter_results.items():
            # Handle both AdapterResult and AdapterStatus shapes
            if hasattr(result, "status"):
                from ..adapters.base import AdapterStatus
                if result.status.value == "success":
                    tools.append(tool_name)
            elif hasattr(result, "value"):
                # It's an AdapterStatus enum directly
                from ..adapters.base import AdapterStatus
                if result == AdapterStatus.SUCCESS:
                    tools.append(tool_name)

    categories = {ADAPTER_CATEGORIES.get(t, "other") for t in tools}

    has_lint       = "lint" in categories
    has_security   = "security" in categories
    has_secrets    = "secrets" in categories
    has_dependency = "dependency" in categories

    if (has_lint or has_security or has_secrets) and has_dependency:
        return DEPTH_PROFILES[AnalysisDepth.FULL_TOOLCHAIN]
    elif has_security or has_secrets:
        return DEPTH_PROFILES[AnalysisDepth.SECURITY_AUGMENTED]
    elif has_lint:
        return DEPTH_PROFILES[AnalysisDepth.LINT_AUGMENTED]
    else:
        return DEPTH_PROFILES[AnalysisDepth.STRUCTURAL_ONLY]


# Backward compat shim for tests that call compute_depth(succeeded, failed)
def compute_depth_from_counts(adapters_succeeded: int, adapters_failed: int) -> DepthProfile:
    """Backward compatible — use compute_depth(adapter_results) instead."""
    if adapters_succeeded >= 3:
        return DEPTH_PROFILES[AnalysisDepth.FULL_TOOLCHAIN]
    elif adapters_succeeded >= 1:
        return DEPTH_PROFILES[AnalysisDepth.LINT_AUGMENTED]
    else:
        return DEPTH_PROFILES[AnalysisDepth.STRUCTURAL_ONLY]
