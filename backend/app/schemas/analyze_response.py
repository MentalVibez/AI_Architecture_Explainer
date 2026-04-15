from datetime import datetime

from pydantic import BaseModel


class AnalyzeResponse(BaseModel):
    job_id: int
    status: str


class JobStatusResponse(BaseModel):
    job_id: int
    status: str
    phase: str = "unknown"
    status_detail: str = ""
    result_id: int | None = None
    error_message: str | None = None
    duration_seconds: int = 0
    next_poll_seconds: int | None = None
    created_at: datetime | None = None
    completed_at: datetime | None = None
