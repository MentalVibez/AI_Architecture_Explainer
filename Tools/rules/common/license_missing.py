from ..base import Rule
from ...models.finding import Finding
from ...models.evidence import EvidenceItem


class LicenseMissingRule(Rule):
    rule_id = "HYGIENE-LICENSE-001"
    title = "Repository is missing a LICENSE file"
    category = "hygiene"
    severity = "medium"
    ecosystems = ["all"]
    tags = ["legal", "open-source"]

    def applies(self, facts) -> bool:
        return True

    def evaluate(self, facts) -> list[Finding]:
        if facts.tooling.has_license:
            return []
        return [Finding(
            id="finding-hygiene-license-missing",
            rule_id=self.rule_id, title=self.title, category=self.category,
            severity="medium", confidence="high", layer="rule",
            summary="No LICENSE file found.",
            why_it_matters="Without a license, legal status is ambiguous. Blocks adoption in corporate environments.",
            suggested_fix="Add a LICENSE file. MIT or Apache 2.0 are common permissive choices.",
            evidence=[EvidenceItem(kind="file", value="LICENSE not found", location="/")],
            score_impact={"developer_experience": -5},
            tags=self.tags,
        )]
