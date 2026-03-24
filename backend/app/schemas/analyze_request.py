import re

from pydantic import BaseModel, field_validator

_NORMALIZE_RE = re.compile(r"(https://github\.com/[^/?#]+/[^/?#.]+?)(?:\.git)?(?:[/?#].*)?$")


class AnalyzeRequest(BaseModel):
    repo_url: str

    @field_validator("repo_url")
    @classmethod
    def must_be_github_url(cls, v: str) -> str:
        v = v.strip()
        if "github.com" not in v:
            raise ValueError("URL must be a GitHub repository URL")
        m = _NORMALIZE_RE.match(v)
        if m:
            return m.group(1)
        return v
