"""
Tool-aware rule: surfaces high-confidence gitleaks findings as first-class findings.
One gitleaks match = one finding. This is the exception to grouping —
each credential leak is an independent critical signal.
"""
from ...models.evidence import EvidenceItem
from ...models.finding import Finding
from ..base import Rule


class SecretScanFindingsRule(Rule):
    rule_id = "SEC-SECRETS-SCAN-001"
    title = "Secret or credential pattern detected"
    category = "security"
    severity = "critical"
    ecosystems = ["all"]
    tags = ["security", "secrets", "credentials"]
    score_domains = ["security"]

    def applies(self, facts) -> bool:
        return True

    def evaluate(self, facts) -> list[Finding]:
        secrets = facts.tool_results.gitleaks
        if not secrets:
            return []

        findings = []
        for issue in secrets:
            sev = issue.severity if issue.severity in ("critical", "high") else "high"
            findings.append(Finding(
                id=f"finding-secrets-{issue.rule_code}-{issue.line or 0}",
                rule_id=self.rule_id,
                title=f"Secret pattern matched: {issue.rule_code}",
                category=self.category,
                severity=sev,
                confidence="high",
                layer="adapter",
                summary=issue.message,
                why_it_matters="Credentials in the repository are accessible to anyone with read access. In git history, they are permanent unless history is rewritten.",
                suggested_fix="Revoke the credential immediately. Remove from history with git-filter-repo. Add pre-commit gitleaks hook.",
                evidence=[
                    EvidenceItem(kind="tool", value=f"gitleaks: {issue.rule_code}", location=issue.file),
                    EvidenceItem(kind="file", value=f"line {issue.line}", location=issue.file),
                ],
                affected_files=[issue.file] if issue.file else [],
                score_impact={"security": -20},
                tags=self.tags,
            ))
        return findings
