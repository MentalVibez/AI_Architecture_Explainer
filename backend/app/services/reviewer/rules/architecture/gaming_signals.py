"""
GAMING-DETECT-001: Facade detection — repo optimized for appearance over substance.

Anti-gaming philosophy:
  A repo can game surface hygiene signals easily:
    - add README  (2 minutes)
    - add LICENSE (30 seconds)
    - add .gitignore (1 minute)
  
  A repo cannot easily game:
    - real test files with actual assertions
    - CI that actually runs those tests
    - meaningful commit history depth
    - type checking with real coverage
    - service layer architecture
    - legitimate operational signals

This rule detects the "polished facade" pattern:
  High on easy signals + Low on hard signals = gaming candidate.

Confidence is always low-medium — we cannot be certain.
But the finding warrants a note and lowers the trust signal.
"""
from ..base import Rule
from ...models.finding import Finding
from ...models.evidence import EvidenceItem


EASY_SIGNALS = ["has_readme", "has_license"]
HARD_SIGNALS = ["has_tests", "has_ci", "has_type_checker", "has_linter"]

EASY_THRESHOLD = 2    # must have both easy signals
HARD_THRESHOLD = 1    # has fewer than this many hard signals


class FacadeDetectionRule(Rule):
    rule_id = "GAMING-FACADE-001"
    title = "Surface polish without production discipline detected"
    category = "architecture"
    severity = "medium"
    ecosystems = ["all"]
    tags = ["gaming", "facade", "trust", "hiring"]
    score_domains = ["reliability", "developer_experience"]

    def applies(self, facts) -> bool:
        # Only meaningful when there are enough files to judge
        return facts.metrics.total_file_count >= 5

    def evaluate(self, facts) -> list[Finding]:
        t = facts.tooling

        easy_present = sum([
            1 if t.has_readme else 0,
            1 if t.has_license else 0,
        ])
        hard_present = sum([
            1 if t.has_tests else 0,
            1 if t.has_ci else 0,
            1 if t.has_type_checker else 0,
            1 if t.has_linter else 0,
        ])

        if easy_present < EASY_THRESHOLD:
            return []  # missing even the basics — not a gaming pattern
        if hard_present >= 2:
            return []  # genuinely has hard signals — not a facade

        missing_hard = []
        if not t.has_tests: missing_hard.append("no automated tests")
        if not t.has_ci: missing_hard.append("no CI pipeline")
        if not t.has_type_checker: missing_hard.append("no type checking")
        if not t.has_linter: missing_hard.append("no linter config")

        return [Finding(
            id="finding-gaming-facade",
            rule_id=self.rule_id, title=self.title, category=self.category,
            severity="medium", confidence="low",
            layer="heuristic",
            summary=f"README and LICENSE present, but {len(missing_hard)} production discipline signals absent.",
            why_it_matters="This pattern — surface hygiene without engineering depth — is common in "
                           "repos optimized for appearance rather than production use. "
                           "Easy signals (README, LICENSE) are present; hard signals are not.",
            suggested_fix="Add real tests, CI pipeline, and type checking. "
                          "These signals are harder to fake and reflect genuine engineering discipline.",
            evidence=[
                EvidenceItem(kind="metric", value=f"Easy signals present: README, LICENSE"),
                EvidenceItem(kind="metric", value=f"Missing hard signals: {', '.join(missing_hard)}"),
            ],
            score_impact={"reliability": -5, "developer_experience": -5},
            tags=self.tags,
        )]
