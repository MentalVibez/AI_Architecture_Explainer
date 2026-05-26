from datetime import datetime

from pydantic import BaseModel, model_validator

from app.services.pipeline.claim_enforcer import ClaimEnforcer
from app.services.policy.tier_policy import AnalysisTier

_STATIC_CLAIMS = ClaimEnforcer(AnalysisTier.STATIC).as_response_fields()


class AnalysisResultResponse(BaseModel):
    id: int
    job_id: int
    share_slug: str | None
    repo_snapshot_sha: str | None
    detected_stack: dict
    dependencies: dict
    entry_points: list
    folder_map: list
    diagram_mermaid: str | None
    developer_summary: str | None
    hiring_manager_summary: str | None
    confidence_score: float | None
    caveats: list
    raw_evidence: list
    setup_risk: dict | None = None
    debug_readiness: dict | None = None
    change_risk: dict | None = None
    analysis_tier: str = _STATIC_CLAIMS["analysis_tier"]
    runtime_verified: bool = _STATIC_CLAIMS["runtime_verified"]
    tier_disclosure: str = _STATIC_CLAIMS["tier_disclosure"]
    created_at: datetime

    model_config = {"from_attributes": True}

    @model_validator(mode="after")
    def attach_static_claim_disclosure(self) -> "AnalysisResultResponse":
        self.analysis_tier = _STATIC_CLAIMS["analysis_tier"]
        self.runtime_verified = _STATIC_CLAIMS["runtime_verified"]
        self.tier_disclosure = _STATIC_CLAIMS["tier_disclosure"]
        return self
