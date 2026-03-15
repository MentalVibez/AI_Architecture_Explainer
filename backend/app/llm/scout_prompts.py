"""
Scout LLM prompts — v1 corrected.

Key changes:
- LLM output is validated against a strict Pydantic model before use
- quality_score excluded from LLM prompt (that is deterministic pre-score)
- LLM is only asked for: relevance_score, verdict, insight, risks, tldr
- Retry-on-parse-failure logic lives in the caller (repo_scout.py)
"""

from __future__ import annotations

import json

from pydantic import BaseModel, Field, field_validator

# ── strict output schema (what we demand from the LLM) ────────────────────────

class LLMRepoScore(BaseModel):
    """Strict model for one repo's LLM output."""
    relevance_score: int = Field(ge=0, le=100)
    verdict: str
    insight: str = Field(min_length=20)
    risks: list[str] = []

    @field_validator("verdict")
    @classmethod
    def valid_verdict(cls, v: str) -> str:
        allowed = {"HIGHLY_RECOMMENDED", "RECOMMENDED", "WORTH_CHECKING", "AVOID"}
        if v not in allowed:
            raise ValueError(f"verdict must be one of {allowed}, got {v!r}")
        return v


class LLMScoutOutput(BaseModel):
    """Top-level model for the full LLM response."""
    scores: dict[str, LLMRepoScore]   # key = repo id
    tldr:   str = Field(min_length=20)


# ── safe parse with fallback ──────────────────────────────────────────────────

def safe_parse_llm_output(raw_text: str) -> LLMScoutOutput | None:
    """
    Strip markdown fences, parse JSON, validate with Pydantic.
    Returns None on any failure so the caller can retry or fall back.
    """
    try:
        clean = raw_text.strip()
        # strip ```json ... ``` or ``` ... ``` fences (with optional trailing text)
        if clean.startswith("```"):
            # Extract only the content between the opening and closing fence
            lines = clean.splitlines()
            inner: list[str] = []
            in_fence = False
            for line in lines:
                if line.strip().startswith("```") and not in_fence:
                    in_fence = True
                    continue
                if line.strip().startswith("```") and in_fence:
                    break  # stop at closing fence; discard trailing text
                if in_fence:
                    inner.append(line)
            clean = "\n".join(inner).strip()
        data = json.loads(clean)
        return LLMScoutOutput.model_validate(data)
    except Exception:
        return None


# ── prompt builder ────────────────────────────────────────────────────────────

def build_scoring_prompt(user_query: str, repos: list[dict]) -> str:
    """
    Evidence-first: LLM receives structured facts only.
    It is NOT asked to re-evaluate quality signals (stars, recency, license) —
    those are already computed deterministically. It is ONLY asked for
    semantic relevance and insight specific to this user's query.
    """
    summaries = [
        {
            "id":               r["id"],
            "name":             r["full_name"],
            "description":      r["description"],
            "language":         r.get("language"),
            "license":          r.get("license_name"),
            "topics":           r.get("topics", []),
            "platform":         r["platform"],
            "quality_score":    r["quality_score"],   # context only — do not re-score
            "noise_flags":      r.get("noise_flags", []),
        }
        for r in repos
    ]

    header = (
        f"You are a senior developer helping a user find the best"
        f" repositories for: \"{user_query}\""
    )
    tldr_hint = (
        "<3-5 sentences: which repos stand out, the overall landscape,"
        " any clear winner, key caveats>"
    )
    return f"""{header}

A deterministic quality_score (0-100) has already been computed for each repo
from stars, recency, license, README, and maintenance signals.
Do NOT re-evaluate those signals. Your job is semantic relevance only.

For each repo, return:
  relevance_score: 0-100 — how well this repo matches what the user actually needs
  verdict: one of HIGHLY_RECOMMENDED | RECOMMENDED | WORTH_CHECKING | AVOID
  insight: 2 sentences — be specific to this user's query, not generic praise
  risks: list of concrete risks (e.g. "Python 2 only", "last commit 2 years ago", "no tests found")

Return ONLY valid JSON with no markdown fences, no preamble, no explanation:

{{
  "scores": {{
    "<repo_id>": {{
      "relevance_score": <0-100>,
      "verdict": "<HIGHLY_RECOMMENDED|RECOMMENDED|WORTH_CHECKING|AVOID>",
      "insight": "<2 sentences specific to the user query>",
      "risks": ["<risk1>", "<risk2>"]
    }}
  }},
  "tldr": "{tldr_hint}"
}}

Repositories:
{json.dumps(summaries, indent=2)}"""
