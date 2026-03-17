"""
Scout schemas — v1 corrected.

Key changes from prototype:
- credibility_score split into quality_score + relevance_score + overall_score
- readme_verified flag distinguishes confirmed vs assumed README
- ScoutError uses a safe message string, never raw exception text
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field, field_validator

# ── enums ─────────────────────────────────────────────────────────────────────

class Platform(StrEnum):
    GITHUB = "github"
    GITLAB = "gitlab"


class SortBy(StrEnum):
    STARS = "stars"
    UPDATED = "updated"
    BEST_MATCH = "best-match"   # GitHub: omit sort param entirely


class Verdict(StrEnum):
    HIGHLY_RECOMMENDED = "HIGHLY_RECOMMENDED"
    RECOMMENDED        = "RECOMMENDED"
    WORTH_CHECKING     = "WORTH_CHECKING"
    AVOID              = "AVOID"


class SignalType(StrEnum):
    GOOD = "good"
    WARN = "warn"
    BAD  = "bad"


# ── request ───────────────────────────────────────────────────────────────────

class ScoutRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=256)
    platforms: list[Platform] = [Platform.GITHUB, Platform.GITLAB]
    sort_by: SortBy = SortBy.STARS
    # Token is optional. If provided it is used only for the duration
    # of this request and never logged or persisted.
    github_token: str | None = Field(default=None, exclude=True)

    @field_validator("platforms")
    @classmethod
    def at_least_one_platform(cls, v: list[Platform]) -> list[Platform]:
        if not v:
            raise ValueError("At least one platform must be selected.")
        return v


# ── sub-models ────────────────────────────────────────────────────────────────

class RepoSignal(BaseModel):
    label: str
    type: SignalType
    verified: bool = True   # False = inferred, not directly confirmed by API


class ScoreBreakdown(BaseModel):
    """
    Three-number model so UI can show what is actually being measured.

    quality_score   — maintenance health: stars, recency, license, docs, activity
    relevance_score — semantic fit to the user's query (LLM-assigned)
    overall_score   — weighted blend: 0.4 * quality + 0.6 * relevance
    """
    quality_score:   int = Field(ge=0, le=100)
    relevance_score: int = Field(ge=0, le=100)
    overall_score:   int = Field(ge=0, le=100)

    @classmethod
    def blend(cls, quality: int, relevance: int) -> ScoreBreakdown:
        overall = round(0.4 * quality + 0.6 * relevance)
        return cls(
            quality_score=quality,
            relevance_score=relevance,
            overall_score=min(overall, 100),
        )


class EvidencePanel(BaseModel):
    """
    Explicit evidence for every factor that contributed to quality_score.
    Makes the AI feel like an evaluator, not a magic box.
    """
    stars:            int
    forks:            int
    days_since_update: int | None
    has_license:      bool
    license_name:     str | None
    readme_verified:  bool          # True only when confirmed via API
    is_fork:          bool
    is_archived:      bool
    is_template:      bool
    open_issues:      int
    topic_matches:    list[str]     # query terms found in repo topics
    matched_terms:    list[str]     # query terms found in name/description
    noise_flags:      list[str]     # e.g. "fork", "archived", "no description"
    repo_age_days:    int | None = None   # days since repo was created
    issue_ratio:      float | None = None # open_issues / max(stars, 1)


# ── repo result ───────────────────────────────────────────────────────────────

class RepoResult(BaseModel):
    id:            str
    platform:      Platform
    full_name:     str
    owner:         str
    description:   str
    url:           str
    language:      str | None
    created_at:    str | None
    updated_at:    str | None

    scores:        ScoreBreakdown
    verdict:       Verdict
    ai_insight:    str
    risks:         list[str]
    signals:       list[RepoSignal]
    evidence:      EvidencePanel


# ── response ──────────────────────────────────────────────────────────────────

class ScoutResponse(BaseModel):
    query:   str
    total:   int
    repos:   list[RepoResult]   # sorted by overall_score desc
    tldr:    str


class ScoutError(BaseModel):
    """Never exposes raw exception text to the client."""
    error:   str        # safe, user-facing message
    code:    str        # machine-readable slug  e.g. "github_rate_limit"
