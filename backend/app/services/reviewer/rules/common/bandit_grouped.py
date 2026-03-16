"""
Tool-aware rule: groups Bandit security findings by severity cluster
instead of emitting one card per finding.

Grouping law:
  - critical/high findings surfaced individually (via SecretScanFindingsRule or directly)
  - medium/low findings grouped into one "security hygiene" finding
"""
from collections import Counter
from ..base import Rule
from ...models.finding import Finding
from ...models.evidence import EvidenceItem


class BanditGroupedRule(Rule):
    rule_id = "SEC-BANDIT-GROUPED-001"
    title = "Security hygiene issues detected"
    category = "security"
    severity = "medium"
    ecosystems = ["python"]
    tags = ["security", "bandit"]
    score_domains = ["security"]

    def applies(self, facts) -> bool:
        return bool(facts.tool_results.bandit)

    def evaluate(self, facts) -> list[Finding]:
        issues = facts.tool_results.bandit
        critical_high = [i for i in issues if i.severity in ("critical", "high")]
        medium_low = [i for i in issues if i.severity in ("medium", "low")]

        findings = []

        # Surface critical/high individually
        for issue in critical_high:
            findings.append(Finding(
                id=f"finding-bandit-{issue.rule_code}-{issue.line or 0}",
                rule_id=self.rule_id,
                title=f"Security: {issue.message[:80]}",
                category=self.category,
                severity=issue.severity,
                confidence="high",
                layer="adapter",
                summary=issue.message,
                why_it_matters="Bandit classified this as high-severity with sufficient confidence.",
                suggested_fix="Review the flagged code and apply security-safe alternatives.",
                evidence=[
                    EvidenceItem(kind="tool", value=f"bandit {issue.rule_code}: {issue.message[:60]}", location=issue.file),
                    EvidenceItem(kind="file", value=f"line {issue.line}", location=issue.file),
                ],
                affected_files=[issue.file] if issue.file else [],
                score_impact={"security": -12 if issue.severity == "critical" else -8},
                tags=self.tags,
            ))

        # Group medium/low into one finding
        if len(medium_low) >= 3:
            rule_counts = Counter(i.rule_code for i in medium_low)
            evidence = [
                EvidenceItem(kind="metric", value=f"Total medium/low security issues: {len(medium_low)}"),
            ] + [
                EvidenceItem(kind="tool", value=f"{code}: {count} occurrence(s)")
                for code, count in rule_counts.most_common(5)
            ]

            findings.append(Finding(
                id="finding-bandit-security-hygiene",
                rule_id=self.rule_id,
                title="Security hygiene issues detected",
                category=self.category,
                severity="medium",
                confidence="medium",
                layer="adapter",
                summary=f"Bandit found {len(medium_low)} medium/low severity security issues.",
                why_it_matters="Security hygiene issues often indicate patterns that could be elevated by an attacker with context.",
                suggested_fix="Review Bandit output with `bandit -r -f text .` and address patterns systematically rather than one-by-one.",
                evidence=evidence,
                affected_files=list({i.file for i in medium_low if i.file})[:5],
                score_impact={"security": -min(len(medium_low) * 2, 10)},
                tags=self.tags,
            ))

        return findings
