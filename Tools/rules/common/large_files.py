from ..base import Rule
from ...models.finding import Finding
from ...models.evidence import EvidenceItem

LARGE_THRESHOLD = 600


class LargeFilesRule(Rule):
    rule_id = "HYGIENE-LARGE-FILES-001"
    title = "Oversized source files detected"
    category = "hygiene"
    severity = "medium"
    ecosystems = ["all"]
    tags = ["maintainability", "complexity"]

    def applies(self, facts) -> bool:
        return True

    def evaluate(self, facts) -> list[Finding]:
        large = [f for f in facts.metrics.large_files if f.line_count >= LARGE_THRESHOLD]
        if not large:
            return []
        evidence = [
            EvidenceItem(kind="file", value=f"{f.path}: {f.line_count} lines", location=f.path)
            for f in large[:5]
        ]
        return [Finding(
            id="finding-hygiene-large-files",
            rule_id=self.rule_id, title=self.title, category=self.category,
            severity="medium", confidence="high", layer="rule",
            summary=f"{len(large)} source file(s) exceed {LARGE_THRESHOLD} lines.",
            why_it_matters="Large files signal missing abstraction and make review and ownership harder.",
            suggested_fix="Identify distinct responsibilities and extract into focused modules.",
            evidence=evidence,
            affected_files=[f.path for f in large],
            score_impact={"maintainability": min(-4 * len(large), -20)},
            tags=self.tags,
        )]
