from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Repo(Base):
    __tablename__ = "repos"

    id: Mapped[int] = mapped_column(primary_key=True)
    github_owner: Mapped[str] = mapped_column(String(255))
    github_repo: Mapped[str] = mapped_column(String(255))
    github_url: Mapped[str] = mapped_column(String(512), unique=True)
    default_branch: Mapped[str] = mapped_column(String(255), default="main")
    last_analyzed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
