"""
repo_scout.py — v1 corrected service layer.

Fixes applied (keyed to review items):

[1] GitHub sort: "best-match" omits sort param entirely; uses httpx params={}
[2] has_readme: GitHub README scoring removed from heuristic; marked unverified
[3] Split scores: quality_score (deterministic) + relevance_score (LLM) + blend
[4] LLM output: strict Pydantic parse, one retry, fallback to heuristic-only
[5] URL construction: httpx params= throughout, no f-string query interpolation
[6] Noise suppression: forks, archived, templates, mirrors, empty descriptions
[7] Token handling: token used only for request duration, excluded from logs
[9] Evidence panel: every scoring factor is surfaced explicitly
"""

from __future__ import annotations

import logging
import math
import re
from datetime import UTC

import httpx

from app.llm.scout_prompts import (
    LLMRepoScore,
    LLMScoutOutput,
    build_scoring_prompt,
    safe_parse_llm_output,
)
from app.schemas.scout import (
    EvidencePanel,
    Platform,
    RepoResult,
    RepoSignal,
    ScoreBreakdown,
    ScoutRequest,
    ScoutResponse,
    SignalType,
    SortBy,
    Verdict,
)

logger = logging.getLogger(__name__)

# ── constants ─────────────────────────────────────────────────────────────────

GITHUB_SEARCH_URL = "https://api.github.com/search/repositories"
GITLAB_SEARCH_URL = "https://gitlab.com/api/v4/projects"

# Valid GitHub sort values (best-match = omit param entirely)
_GH_SORT_MAP: dict[SortBy, str | None] = {
    SortBy.STARS:      "stars",
    SortBy.UPDATED:    "updated",
    SortBy.BEST_MATCH: None,   # FIX [1]: omit param, GitHub defaults to best-match
}

# Patterns that suggest a repo is a mirror/clone rather than the original
_MIRROR_PATTERNS = re.compile(
    r"\b(mirror|clone|fork|backup|copy|archived|deprecated)\b", re.I
)


# ── helpers ───────────────────────────────────────────────────────────────────

def _days_since(date_str: str | None) -> int | None:
    if not date_str:
        return None
    from datetime import datetime
    dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    return (datetime.now(UTC) - dt).days


def _fmt_num(n: int) -> str:
    return f"{n / 1000:.1f}k" if n >= 1000 else str(n)


def _find_term_matches(query: str, text: str) -> list[str]:
    """Return query tokens found in text (case-insensitive)."""
    tokens = [t.lower() for t in re.split(r"\W+", query) if len(t) > 2]
    return [t for t in tokens if t in text.lower()]


# ── noise filter ─────────────────────────────────────────────────────────────

def _noise_flags(raw: dict) -> list[str]:
    """
    FIX [6]: identify noise signals so the heuristic can penalise them
    and the UI can display them explicitly.
    """
    flags: list[str] = []

    if raw.get("is_fork"):
        flags.append("fork")
    if raw.get("is_archived"):
        flags.append("archived")
    if raw.get("is_template"):
        flags.append("template")

    desc = raw.get("description") or ""
    if not desc.strip():
        flags.append("no description")
    elif _MIRROR_PATTERNS.search(desc):
        flags.append("possible mirror")

    name = raw.get("full_name", "").lower()
    if _MIRROR_PATTERNS.search(name):
        flags.append("possible mirror")

    if (raw.get("stars", 0) < 5) and (raw.get("forks", 0) < 2):
        flags.append("low traction")

    return list(dict.fromkeys(flags))   # dedupe while preserving order


def _should_exclude(raw: dict, flags: list[str]) -> bool:
    """Hard exclusions — these repos are dropped before scoring."""
    if raw.get("is_archived") and raw.get("stars", 0) < 50:
        return True
    if "fork" in flags and raw.get("stars", 0) < 20:
        return True
    return False


# ── heuristic quality scorer ──────────────────────────────────────────────────

def _quality_score(raw: dict, flags: list[str]) -> tuple[int, list[RepoSignal]]:
    """
    FIX [3]: this function scores QUALITY only (not relevance).
    FIX [2]: README is no longer assumed for GitHub repos — see comment below.

    Max reachable before noise penalties: ~72 → capped at 70 before LLM sees it.
    """
    score = 0
    signals: list[RepoSignal] = []

    # ── stars ──
    stars = raw.get("stars", 0)
    if stars >= 5000:
        score += 22
        signals.append(RepoSignal(label=f"★ {_fmt_num(stars)} stars", type=SignalType.GOOD))
    elif stars >= 1000:
        score += 18
        signals.append(RepoSignal(label=f"★ {_fmt_num(stars)} stars", type=SignalType.GOOD))
    elif stars >= 100:
        score += 12
        signals.append(RepoSignal(label=f"★ {_fmt_num(stars)} stars", type=SignalType.GOOD))
    elif stars >= 10:
        score += 5
        signals.append(RepoSignal(label=f"★ {_fmt_num(stars)} stars", type=SignalType.WARN))
    else:
        signals.append(RepoSignal(label=f"★ {_fmt_num(stars)} stars", type=SignalType.BAD))

    # ── recency ──
    days = _days_since(raw.get("updated_at"))
    if days is not None:
        if days <= 30:
            score += 15
            signals.append(RepoSignal(label="Active: updated this month", type=SignalType.GOOD))
        elif days <= 90:
            score += 10
            signals.append(RepoSignal(label=f"Updated {days}d ago", type=SignalType.GOOD))
        elif days <= 365:
            score += 4
            signals.append(RepoSignal(label=f"Updated {days}d ago", type=SignalType.WARN))
        else:
            years = math.floor(days / 365)
            signals.append(RepoSignal(label=f"Stale: ~{years}yr ago", type=SignalType.BAD))

    # ── license ──
    license_name = raw.get("license_name")
    if license_name and license_name.upper() not in ("NOASSERTION", "OTHER"):
        score += 7
        signals.append(RepoSignal(label=license_name, type=SignalType.GOOD))
    else:
        signals.append(RepoSignal(label="No license", type=SignalType.WARN))

    # ── README ──
    # FIX [2]: GitHub search API does NOT confirm README presence.
    # readme_verified is only True for GitLab (readme_url field) or when we
    # do an explicit second-pass check. We score it, but mark as unverified.
    if raw.get("platform") == "gitlab":
        if raw.get("readme_verified"):
            score += 7
            signals.append(
                RepoSignal(label="README confirmed", type=SignalType.GOOD, verified=True)
            )
        else:
            signals.append(
                RepoSignal(label="No README found", type=SignalType.WARN, verified=True)
            )
    else:
        # GitHub: treat README as likely-present but do NOT score it
        # Mark verified=False so the UI can display "unverified"
        signals.append(
            RepoSignal(label="README (unverified)", type=SignalType.WARN, verified=False)
        )

    # ── description quality ──
    desc = raw.get("description") or ""
    if len(desc) > 40:
        score += 3

    # ── topics ──
    topics = raw.get("topics") or []
    if len(topics) >= 3:
        score += 3

    # ── forks signal ──
    forks = raw.get("forks", 0)
    if forks >= 500:
        score += 5
        signals.append(RepoSignal(label=f"⑂ {_fmt_num(forks)} forks", type=SignalType.GOOD))
    elif forks >= 50:
        score += 2

    # ── noise penalties FIX [6] ──
    if "fork" in flags:
        score = max(0, score - 15)
        signals.append(RepoSignal(label="Is a fork", type=SignalType.BAD))
    if "possible mirror" in flags:
        score = max(0, score - 10)
        signals.append(RepoSignal(label="Possible mirror/clone", type=SignalType.WARN))
    if "no description" in flags:
        score = max(0, score - 5)
        signals.append(RepoSignal(label="No description", type=SignalType.BAD))
    if "template" in flags:
        signals.append(RepoSignal(label="Template repo", type=SignalType.WARN))

    return min(score, 70), signals


# ── deduplication ─────────────────────────────────────────────────────────────

def _deduplicate(repos: list[dict]) -> list[dict]:
    """
    FIX [6]: remove cross-platform duplicates by normalising repo name.
    Keep the higher-starred version when names collide.
    """
    seen: dict[str, dict] = {}
    for r in repos:
        # Normalise: lowercase, strip owner prefix
        key = r["full_name"].split("/")[-1].lower()
        if key not in seen or r["stars"] > seen[key]["stars"]:
            seen[key] = r
    return list(seen.values())


# ── GitHub fetcher ────────────────────────────────────────────────────────────

async def _fetch_github(
    query: str,
    sort_by: SortBy,
    token: str | None,
) -> list[dict]:
    headers = {"Accept": "application/vnd.github+json"}
    # FIX [7]: token used only here, never stored, never logged
    if token:
        headers["Authorization"] = f"Bearer {token}"

    # FIX [1] + [5]: use params={}, omit sort for best-match
    params: dict = {"q": query, "per_page": 10}
    sort_value = _GH_SORT_MAP.get(sort_by)
    if sort_value:
        params["sort"] = sort_value
    # If sort_value is None (best-match), omit sort param entirely

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(GITHUB_SEARCH_URL, headers=headers, params=params)
        if resp.status_code == 403:
            raise RuntimeError("github_rate_limit")
        if resp.status_code == 422:
            raise RuntimeError("github_invalid_query")
        resp.raise_for_status()

    items = resp.json().get("items", [])

    return [
        {
            "id":            f"gh_{r['id']}",
            "platform":      "github",
            "full_name":     r["full_name"],
            "owner":         r["owner"]["login"],
            "description":   (r.get("description") or "").strip(),
            "url":           r["html_url"],
            "stars":         r["stargazers_count"],
            "forks":         r["forks_count"],
            "open_issues":   r["open_issues_count"],
            "language":      r.get("language"),
            "license_name":  r["license"]["spdx_id"] if r.get("license") else None,
            "updated_at":    r.get("updated_at"),
            "created_at":    r.get("created_at"),
            # FIX [2]: readme_verified is NOT set here — GitHub search does not confirm it
            "readme_verified": False,
            "topics":        r.get("topics") or [],
            "is_fork":       r.get("fork", False),
            "is_archived":   r.get("archived", False),
            "is_template":   r.get("is_template", False),
        }
        for r in items
    ]


# ── GitLab fetcher ────────────────────────────────────────────────────────────

async def _fetch_gitlab(query: str) -> list[dict]:
    # FIX [5]: use params={} throughout
    params = {
        "search":     query,
        "order_by":   "last_activity_at",
        "per_page":   8,
        "visibility": "public",
    }

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(GITLAB_SEARCH_URL, params=params)
        if resp.status_code == 429:
            raise RuntimeError("gitlab_rate_limit")
        resp.raise_for_status()

    items = resp.json()

    return [
        {
            "id":            f"gl_{r['id']}",
            "platform":      "gitlab",
            "full_name":     r["path_with_namespace"],
            "owner":         r.get("namespace", {}).get("name", ""),
            "description":   (r.get("description") or "").strip(),
            "url":           r["web_url"],
            "stars":         r.get("star_count", 0),
            "forks":         r.get("forks_count", 0),
            "open_issues":   r.get("open_issues_count", 0),
            "language":      None,
            "license_name":  r.get("license", {}).get("name") if r.get("license") else None,
            # Note: GitLab last_activity_at can lag ~1 hour per API docs
            "updated_at":    r.get("last_activity_at"),
            "created_at":    r.get("created_at"),
            # FIX [2]: readme_url IS in GitLab responses — this signal is verified
            "readme_verified": bool(r.get("readme_url")),
            "topics":        r.get("topics") or [],
            "is_fork":       r.get("forked_from_project") is not None,
            "is_archived":   r.get("archived", False),
            "is_template":   False,
        }
        for r in items
    ]


# ── LLM scoring with retry + fallback ────────────────────────────────────────

async def _score_with_llm(
    user_query: str,
    repos: list[dict],
    llm,
) -> LLMScoutOutput:
    """
    FIX [4]: strict Pydantic parse, one retry, graceful fallback.
    The caller never sees raw exception text.
    """
    prompt = build_scoring_prompt(user_query, repos)

    for attempt in range(2):   # try twice before falling back
        try:
            raw_text: str = await llm.generate_text(prompt)
            result = safe_parse_llm_output(raw_text)
            if result is not None:
                return result
            logger.warning("Scout LLM parse failed on attempt %d", attempt + 1)
        except Exception:
            logger.exception("Scout LLM call failed on attempt %d", attempt + 1)

    # Fallback: return empty scores so heuristics carry the weight
    logger.error("Scout LLM scoring unavailable — falling back to heuristic-only mode")
    return LLMScoutOutput(
        scores={},
        tldr=(
            "AI summary unavailable — results are ranked by quality signals only "
            "(stars, recency, license, maintenance). Relevance scores are estimated."
        ),
    )


# ── main service entry point ──────────────────────────────────────────────────

async def run_scout(req: ScoutRequest, llm) -> ScoutResponse:
    # 1. Fetch from selected platforms
    raw: list[dict] = []
    if Platform.GITHUB in req.platforms:
        raw.extend(await _fetch_github(req.query, req.sort_by, req.github_token))
    if Platform.GITLAB in req.platforms:
        raw.extend(await _fetch_gitlab(req.query))

    if not raw:
        return ScoutResponse(
            query=req.query,
            total=0,
            repos=[],
            tldr="No repositories matched your query.",
        )

    # 2. Noise flags + hard exclusions FIX [6]
    flagged = [(r, _noise_flags(r)) for r in raw]
    flagged = [(r, f) for r, f in flagged if not _should_exclude(r, f)]

    # 3. Deduplicate FIX [6]
    unique = _deduplicate([r for r, _ in flagged])
    flag_map = {r["id"]: f for r, f in flagged}

    # 4. Deterministic quality scoring FIX [3]
    pre: list[dict] = []
    for r in unique:
        flags = flag_map.get(r["id"], [])
        q_score, signals = _quality_score(r, flags)
        topic_hits = _find_term_matches(req.query, " ".join(r.get("topics") or []))
        name_desc_hits = _find_term_matches(
            req.query, r["full_name"] + " " + r["description"]
        )
        pre.append({
            **r,
            "quality_score": q_score,
            "signals": signals,
            "noise_flags": flags,
            "topic_matches": topic_hits,
            "matched_terms": name_desc_hits,
        })

    # 5. LLM relevance scoring FIX [4]
    llm_output = await _score_with_llm(req.query, pre, llm)

    # 6. Merge and build results FIX [3]
    results: list[RepoResult] = []
    for r in pre:
        repo_id = r["id"]
        ai: LLMRepoScore = llm_output.scores.get(repo_id)  # type: ignore[assignment]

        if ai is not None:
            relevance = ai.relevance_score
            verdict   = Verdict(ai.verdict)
            insight   = ai.insight
            risks     = ai.risks
        else:
            # Fallback: estimate relevance from term matches
            topic_boost = len(r["topic_matches"]) * 8
            term_boost  = len(r["matched_terms"]) * 5
            relevance   = min(r["quality_score"] + topic_boost + term_boost, 100)
            verdict     = Verdict.WORTH_CHECKING
            insight     = "AI scoring unavailable. Ranked by quality signals only."
            risks       = []

        scores = ScoreBreakdown.blend(
            quality=r["quality_score"],
            relevance=relevance,
        )

        evidence = EvidencePanel(
            stars=r["stars"],
            forks=r["forks"],
            days_since_update=_days_since(r.get("updated_at")),
            has_license=bool(r.get("license_name")),
            license_name=r.get("license_name"),
            readme_verified=r.get("readme_verified", False),
            is_fork=r.get("is_fork", False),
            is_archived=r.get("is_archived", False),
            is_template=r.get("is_template", False),
            open_issues=r.get("open_issues", 0),
            topic_matches=r["topic_matches"],
            matched_terms=r["matched_terms"],
            noise_flags=r["noise_flags"],
        )

        results.append(RepoResult(
            id=repo_id,
            platform=Platform(r["platform"]),
            full_name=r["full_name"],
            owner=r["owner"],
            description=r["description"],
            url=r["url"],
            language=r.get("language"),
            created_at=r.get("created_at"),
            updated_at=r.get("updated_at"),
            scores=scores,
            verdict=verdict,
            ai_insight=insight,
            risks=risks,
            signals=r["signals"],
            evidence=evidence,
        ))

    results.sort(key=lambda x: x.scores.overall_score, reverse=True)

    return ScoutResponse(
        query=req.query,
        total=len(results),
        repos=results,
        tldr=llm_output.tldr,
    )
