"""
Runs applicable rules against facts. One failing rule does not abort the run.
"""
import logging

from ..facts.models import RepoFacts
from ..models.finding import Finding
from .registry import RuleRegistry

logger = logging.getLogger(__name__)


def execute(registry: RuleRegistry, facts: RepoFacts) -> list[Finding]:
    applicable = registry.for_facts(facts)
    findings: list[Finding] = []

    for rule in applicable:
        try:
            results = rule.evaluate(facts)
            findings.extend(results)
        except Exception as exc:
            logger.warning("Rule %s failed: %s", rule.rule_id, exc)

    return findings
