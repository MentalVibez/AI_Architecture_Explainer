"""
Suppresses duplicate findings from overlapping rules/adapters.

Dedup key uses rule_id as the primary discriminator so that distinct
rules (SEC-SECRETS vs SEC-DENSITY vs SEC-BANDIT) never collapse together,
even if they share a category tag.

Grouping is reserved for findings that share:
  - same rule_id (exact same rule fired twice)
  - same root_cause_tag (explicitly tagged as same root cause)
  - overlapping affected files + same category + same primary tag

This is deliberately conservative — false merges are worse than duplicates.
"""
from ..models.finding import Finding

SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
CONFIDENCE_ORDER = {"high": 0, "medium": 1, "low": 2}


def deduplicate(findings: list[Finding]) -> list[Finding]:
    seen: dict[str, Finding] = {}
    for finding in findings:
        key = _dedup_key(finding)
        if key not in seen:
            seen[key] = finding
        else:
            existing = seen[key]
            if SEVERITY_ORDER[finding.severity] < SEVERITY_ORDER[existing.severity]:
                seen[key] = finding
            elif (
                SEVERITY_ORDER[finding.severity] == SEVERITY_ORDER[existing.severity]
                and CONFIDENCE_ORDER[finding.confidence] < CONFIDENCE_ORDER[existing.confidence]
            ):
                seen[key] = finding
    return list(seen.values())


def _dedup_key(finding: Finding) -> str:
    """
    Primary key: rule_id — each distinct rule gets its own slot.
    This prevents SEC-SECRETS, SEC-DENSITY, and SEC-BANDIT from
    collapsing into one finding just because they share a "security" tag.

    Exception: findings from the SAME rule_id that affect the same
    primary file are merged (e.g. gitleaks finding same secret twice).
    """
    primary_file = finding.affected_files[0] if finding.affected_files else ""
    # For rules that intentionally fire once per instance (secrets, bandit individual)
    # we include a file discriminator so distinct instances are not merged.
    if finding.layer == "adapter" and primary_file:
        return f"{finding.rule_id}::{primary_file}::{finding.evidence[0].value[:30] if finding.evidence else ''}"
    return finding.rule_id
