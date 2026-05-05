from datetime import datetime

from pydantic import BaseModel, Field


class ExternalServiceStatusResponse(BaseModel):
    mode: str
    status: str
    detail: str = ""


class QueuedJobResponse(BaseModel):
    job_id: str
    repo: str
    age_seconds: int
    created_at: datetime | None = None


class QueueMetricsResponse(BaseModel):
    queued: int
    running: int
    completed_last_24h: int
    failed_last_24h: int
    average_duration_seconds: int | None = None
    oldest_queued_seconds: int | None = None
    oldest_running_seconds: int | None = None
    oldest_queued_jobs: list[QueuedJobResponse] = Field(default_factory=list)


class RecentFailureResponse(BaseModel):
    kind: str
    repo: str
    error_message: str | None = None
    completed_at: datetime | None = None


class QueueGuardResponse(BaseModel):
    guard_after_seconds: int
    cleared_atlas: int = 0
    cleared_review: int = 0
    root_cause: str | None = None
    recommended_action: str | None = None


class OpsSnapshotResponse(BaseModel):
    status: str
    attention_message: str | None = None
    github: ExternalServiceStatusResponse
    atlas: QueueMetricsResponse
    review: QueueMetricsResponse
    queue_guard: QueueGuardResponse
    recent_failures: list[RecentFailureResponse]
    generated_at: datetime
