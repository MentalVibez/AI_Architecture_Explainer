from datetime import datetime

from pydantic import BaseModel


class AnalysisResultResponse(BaseModel):
    id: int
    job_id: int
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
    created_at: datetime

    model_config = {"from_attributes": True}
