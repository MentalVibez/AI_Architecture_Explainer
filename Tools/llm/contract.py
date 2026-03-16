"""
LLM input/output contracts.

Design law:
  - LLM receives: structured findings + scorecard + coverage limits + confidence
  - LLM returns: structured JSON
  - LLM never sees: raw code, repo tree, file contents
  - LLM never decides: verdict, scores, production_suitable, findings
"""
from pydantic import BaseModel, Field
from typing import Literal


class LLMFindingInput(BaseModel):
    rule_id: str
    severity: Literal["critical", "high", "medium", "low", "info"]
    confidence: Literal["high", "medium", "low"]
    category: str
    title: str
    why_it_matters: str
    suggested_fix: str
    evidence_strings: list[str] = Field(default_factory=list)


class LLMReportInput(BaseModel):
    """Everything the LLM is allowed to see. Never raw code."""
    repo_url: str
    primary_languages: list[str]
    overall_score: int
    verdict_label: str
    production_suitable: bool
    scorecard_summary: dict[str, int]
    findings: list[LLMFindingInput]
    coverage_pct: float
    coverage_limits: list[str]
    ruleset_version: str
    confidence_label: str = "Low"    # "High" | "Medium" | "Low"
    adapters_ran: bool = False        # True when at least one adapter succeeded


class LLMSummaryOutput(BaseModel):
    developer_summary: str
    manager_summary: str
    hiring_summary: str
    top_risks: list[str]
    strengths: list[str]


def build_llm_input(
    report,
    overall_score: int,
    findings,
    confidence_label: str = "Low",
    adapters_ran: bool = False,
) -> LLMReportInput:
    sc = report.scorecard
    llm_findings = []
    for f in findings:
        if f.severity in ("critical", "high", "medium"):
            llm_findings.append(LLMFindingInput(
                rule_id=f.rule_id,
                severity=f.severity,
                confidence=f.confidence,
                category=f.category,
                title=f.title,
                why_it_matters=f.why_it_matters,
                suggested_fix=f.suggested_fix,
                evidence_strings=[ev.value for ev in f.evidence[:3]],
            ))

    return LLMReportInput(
        repo_url=report.repo.url,
        primary_languages=report.repo.primary_languages,
        overall_score=overall_score,
        verdict_label=report.interpretation.overall_label,
        production_suitable=report.interpretation.production_suitable,
        scorecard_summary={
            "security": sc.security,
            "testing": sc.testing,
            "maintainability": sc.maintainability,
            "reliability": sc.reliability,
            "operational_readiness": sc.operational_readiness,
            "developer_experience": sc.developer_experience,
        },
        findings=llm_findings,
        coverage_pct=report.coverage.repo_files_scanned_pct,
        coverage_limits=report.coverage.limits[:4],
        ruleset_version=report.ruleset_version,
        confidence_label=confidence_label,
        adapters_ran=adapters_ran,
    )
