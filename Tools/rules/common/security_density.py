"""
Tool-aware rule: detects when Bandit or Ruff-security findings are concentrated
in entrypoint files, suggesting systemic rather than isolated security gaps.
"""
from collections import Counter
from ..base import Rule
from ...models.finding import Finding
from ...models.evidence import EvidenceItem

ENTRYPOINT_NAMES = {"main.py", "app.py", "server.py", "wsgi.py", "asgi.py", "index.ts", "index.js"}
SECURITY_SEVERITY_THRESHOLD = ("critical", "high")
MIN_SECURITY_FINDINGS = 3


class SecurityDensityRule(Rule):
    rule_id = "SEC-DENSITY-001"
    title = "Security findings concentrated in critical entrypoints"
    category = "security"
    severity = "high"
    ecosystems = ["all"]
    tags = ["security", "architecture", "entrypoints"]
    score_domains = ["security", "reliability"]

    def applies(self, facts) -> bool:
        return bool(facts.tool_results.bandit or facts.tool_results.ruff)

    def evaluate(self, facts) -> list[Finding]:
        all_issues = list(facts.tool_results.bandit) + list(facts.tool_results.ruff)
        sec_issues = [
            i for i in all_issues
            if i.severity in SECURITY_SEVERITY_THRESHOLD and i.file
        ]

        if len(sec_issues) < MIN_SECURITY_FINDINGS:
            return []

        from pathlib import Path
        entrypoint_hits = [
            i for i in sec_issues
            if Path(i.file or "").name in ENTRYPOINT_NAMES
        ]

        if len(entrypoint_hits) < 2:
            return []

        file_counts = Counter(i.file for i in entrypoint_hits)
        evidence = [
            EvidenceItem(kind="tool", value=f"{fname}: {count} security issue(s)", location=fname)
            for fname, count in file_counts.most_common(4)
        ]
        evidence.append(EvidenceItem(
            kind="metric",
            value=f"Total security findings in entrypoints: {len(entrypoint_hits)}"
        ))

        return [Finding(
            id="finding-sec-density-entrypoints",
            rule_id=self.rule_id,
            title=self.title,
            category=self.category,
            severity="high",
            confidence="medium",
            layer="heuristic",
            summary=f"{len(entrypoint_hits)} security findings in application entrypoint files.",
            why_it_matters="Security issues in entrypoints affect every request path and are hardest to isolate.",
            suggested_fix="Prioritize remediating security findings in entrypoint files. Consider extracting sensitive operations into audited middleware.",
            evidence=evidence,
            affected_files=list(file_counts.keys()),
            score_impact={"security": -10, "reliability": -5},
            tags=self.tags,
        )]
