from datetime import datetime

from pydantic import BaseModel


class QueueMetricsResponse(BaseModel):
    queued: int
    running: int
    completed_last_24h: int
    failed_last_24h: int
    average_duration_seconds: int | None = None
    oldest_queued_seconds: int | None = None
    oldest_running_seconds: int | None = None


class RecentFailureResponse(BaseModel):
    kind: str
    repo: str
    error_message: str | None = None
    completed_at: datetime | None = None


class OpsSnapshotResponse(BaseModel):
    status: str
    attention_message: str | None = None
    atlas: QueueMetricsResponse
    review: QueueMetricsResponse
    recent_failures: list[RecentFailureResponse]
    generated_at: datetime
