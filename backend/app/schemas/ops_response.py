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


class WorkerHeartbeatResponse(BaseModel):
    worker_id: str
    hostname: str
    process_id: int
    queues: list[str]
    status: str
    started_at: datetime
    last_seen_at: datetime
    age_seconds: int
    fresh: bool


class WorkerStatusResponse(BaseModel):
    status: str
    fresh_count: int
    stale_count: int
    stale_after_seconds: int
    active_queues: list[str] = Field(default_factory=list)
    workers: list[WorkerHeartbeatResponse] = Field(default_factory=list)


class LLMStageMetrics(BaseModel):
    stage: str
    calls: int
    input_tokens: int
    output_tokens: int
    avg_duration_ms: int


class LLMUsageStats(BaseModel):
    window_hours: int
    total_calls: int
    total_input_tokens: int
    total_output_tokens: int
    estimated_cost_usd: float
    avg_duration_ms: int | None = None
    by_stage: list[LLMStageMetrics] = Field(default_factory=list)


class OpsSnapshotResponse(BaseModel):
    status: str
    attention_message: str | None = None
    github: ExternalServiceStatusResponse
    atlas: QueueMetricsResponse
    review: QueueMetricsResponse
    workers: WorkerStatusResponse
    queue_guard: QueueGuardResponse
    recent_failures: list[RecentFailureResponse]
    llm_usage: LLMUsageStats | None = None
    generated_at: datetime
