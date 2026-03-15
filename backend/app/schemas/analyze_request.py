from pydantic import BaseModel, field_validator


class AnalyzeRequest(BaseModel):
    repo_url: str

    @field_validator("repo_url")
    @classmethod
    def must_be_github_url(cls, v: str) -> str:
        if "github.com" not in v:
            raise ValueError("URL must be a GitHub repository URL")
        return v.rstrip("/")
