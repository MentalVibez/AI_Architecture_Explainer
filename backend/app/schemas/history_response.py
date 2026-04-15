from datetime import datetime

from pydantic import BaseModel


class RecentRunItemResponse(BaseModel):
    id: str
    kind: str
    repo: str
    href: str
    title: str
    completed_at: datetime


class RecentRunsResponse(BaseModel):
    items: list[RecentRunItemResponse]
