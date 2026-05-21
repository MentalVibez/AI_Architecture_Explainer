from pydantic import BaseModel, Field


class WeekPlanItem(BaseModel):
    phase: str
    title: str
    goal: str
    actions: list[str] = Field(default_factory=list)


class ReadingPathItem(BaseModel):
    path: str
    reason: str
    confidence: float


class StarterTask(BaseModel):
    title: str
    why_safe: str
    suggested_checks: list[str] = Field(default_factory=list)
    related_paths: list[str] = Field(default_factory=list)


class RiskNote(BaseModel):
    title: str
    guidance: str
    related_paths: list[str] = Field(default_factory=list)


class ConceptNote(BaseModel):
    name: str
    explanation: str
    evidence: list[str] = Field(default_factory=list)


class SetupBlocker(BaseModel):
    title: str
    severity: str
    guidance: str


class CodebaseGuideResponse(BaseModel):
    result_id: int
    repo_label: str | None
    overview: str
    week_plan: list[WeekPlanItem]
    reading_path: list[ReadingPathItem]
    concepts: list[ConceptNote]
    starter_tasks: list[StarterTask]
    risk_notes: list[RiskNote]
    mentor_questions: list[str]
    team_questions: list[str]
    setup_blockers: list[SetupBlocker]
    evidence_summary: dict


# Compatibility alias for the original endpoint name.
OnboardingPlanResponse = CodebaseGuideResponse
