from pydantic import BaseModel


class AnalyzeResponse(BaseModel):
    job_id: int
    status: str


class JobStatusResponse(BaseModel):
    job_id: int
    status: str
    result_id: int | None = None
    error_message: str | None = None
