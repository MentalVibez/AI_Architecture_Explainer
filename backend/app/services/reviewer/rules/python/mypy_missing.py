from ...models.evidence import EvidenceItem
from ...models.finding import Finding
from ..base import Rule


class MypyMissingRule(Rule):
    rule_id = "PY-TYPING-001"
    title = "Type checking not enforced"
    category = "type-safety"
    severity = "medium"
    ecosystems = ["python"]
    tags = ["typing", "mypy", "quality"]

    def applies(self, facts) -> bool:
        return "Python" in facts.languages.primary

    def evaluate(self, facts) -> list[Finding]:
        if facts.tooling.has_type_checker:
            return []
        return [Finding(
            id="finding-py-typing-no-mypy",
            rule_id=self.rule_id, title=self.title, category=self.category,
            severity="medium", confidence="high", layer="rule",
            summary="No mypy, pyright, or type checker configuration found.",
            why_it_matters="Untyped Python hides contract violations and raises regression risk as the codebase grows.",
            suggested_fix="Add mypy to pyproject.toml. Start with --ignore-missing-imports, tighten over sprints.",
            evidence=[
                EvidenceItem(kind="config", value="No mypy.ini / pyrightconfig.json found"),
                EvidenceItem(kind="config", value="No [tool.mypy] in pyproject.toml"),
            ],
            score_impact={"maintainability": -8, "reliability": -5},
            tags=self.tags,
        )]
