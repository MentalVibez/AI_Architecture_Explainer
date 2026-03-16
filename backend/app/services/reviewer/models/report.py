from pydantic import BaseModel, Field
from .finding import Finding


class RepoMeta(BaseModel):
    url: str
    commit: str
    primary_languages: list[str] = Field(default_factory=list)


class AdapterCoverage(BaseModel):
    tool: str
    status: str
    issues_found: int = 0
    duration_seconds: float = 0.0
    error_summary: str | None = None


class ReviewCoverage(BaseModel):
    repo_files_scanned_pct: float = 0.0
    language_support_pct: float = 0.0
    adapters: list[AdapterCoverage] = Field(default_factory=list)
    limits: list[str] = Field(default_factory=list)


class Scorecard(BaseModel):
    maintainability: int = 100
    reliability: int = 100
    security: int = 100
    testing: int = 100
    operational_readiness: int = 100
    developer_experience: int = 100


class AnalysisDepthInfo(BaseModel):
    """First-class depth field — displayed in UI and API responses."""
    level: str = "structural_only"       # AnalysisDepth enum value
    label: str = "Structural only"       # human-readable
    description: str = ""
    verdict_note: str = ""               # appended to production verdict
    adapters_succeeded: int = 0
    allowed_strong_claims: bool = False


class ScoreInterpretation(BaseModel):
    overall_label: str = ""
    trust_recommendation: str = ""
    color_hint: str = ""
    production_suitable: bool = False
    top_concern: str | None = None
    developer_meaning: str = ""
    manager_meaning: str = ""
    hiring_meaning: str = ""
    category_interpretations: dict[str, str] = Field(default_factory=dict)


class ReviewMeta(BaseModel):
    ruleset_version: str = ""
    schema_version: str = "1.0"
    applicable_rule_count: int = 0
    executed_rule_count: int = 0
    adapters_run: list[str] = Field(default_factory=list)
    overall_score: int = 0
    confidence_label: str = ""
    confidence_score: float = 0.0
    confidence_rationale: list[str] = Field(default_factory=list)


class GamingSignal(BaseModel):
    signal_type: str
    label: str
    verdict: str
    confidence: str
    evidence: str


class AntiGamingBlock(BaseModel):
    overall_verdict: str = "inconclusive"
    signals: list[GamingSignal] = Field(default_factory=list)
    summary: str = ""


class ReviewSummary(BaseModel):
    developer: str = ""
    manager: str = ""
    hiring: str = ""
    trace: dict = Field(default_factory=dict)


class ReviewReport(BaseModel):
    schema_version: str = "1.0"
    ruleset_version: str = ""
    repo: RepoMeta
    coverage: ReviewCoverage = Field(default_factory=ReviewCoverage)
    depth: AnalysisDepthInfo = Field(default_factory=AnalysisDepthInfo)
    scorecard: Scorecard = Field(default_factory=Scorecard)
    interpretation: ScoreInterpretation = Field(default_factory=ScoreInterpretation)
    meta: ReviewMeta = Field(default_factory=ReviewMeta)
    findings: list[Finding] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    priority_actions: list[str] = Field(default_factory=list)
    anti_gaming: AntiGamingBlock = Field(default_factory=AntiGamingBlock)
    review_summary: ReviewSummary = Field(default_factory=ReviewSummary)
