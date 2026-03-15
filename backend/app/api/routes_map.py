"""
GET /api/map/{owner}/{repo} — API Endpoint Mapper

How it works:
  1. Run deterministic stack analysis (no LLM) to detect framework
  2. Map framework name to targeted parse strategy
  3. Extract routes using framework-specific regex patterns
  4. Enrich with LLM using stack context (grouping + descriptions)
  5. Return grouped, annotated endpoint map

The framework detection is reused from the Atlas pipeline — no separate
service call required.
"""
import logging
import time
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.services.analysis_pipeline import run_analysis
from app.services.endpoint_enricher import enrich_endpoint_map
from app.services.route_extractor import extract_endpoints

logger = logging.getLogger(__name__)
limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/api/map", tags=["map"])

# Maps framework_detector output strings → FRAMEWORK_PATTERNS keys
_FRAMEWORK_MAP: dict[str, str] = {
    "fastapi": "fastapi",
    "flask": "flask",
    "django": "django",
    "express": "express",
    "next.js": "nextjs",
}


class ProfileUsed(BaseModel):
    framework: str
    framework_confidence: str
    from_profile: bool
    detected_backend: list[str]
    detected_frontend: list[str]


class MapResponse(BaseModel):
    repo: str
    profile_used: ProfileUsed
    groups: list[dict]
    summary: str
    api_style: str
    auth_pattern: str
    files_scanned: list[str]
    raw_endpoint_count: int
    warnings: list[str]
    duration_ms: int


def _build_profile(detected_stack: dict) -> tuple[str, str]:
    """
    Derive (framework_key, confidence) from detect_stack() output.

    Returns the first recognized backend framework (high confidence),
    or falls back to nextjs if present in frontend,
    or "unknown" (generic scan).
    """
    backend: list[str] = detected_stack.get("backend", [])
    frontend: list[str] = detected_stack.get("frontend", [])

    for fw in backend:
        key = _FRAMEWORK_MAP.get(fw.lower())
        if key:
            return key, "high"

    for fw in frontend:
        key = _FRAMEWORK_MAP.get(fw.lower())
        if key:
            return key, "high"

    return "unknown", "speculative"


@router.get("/{owner}/{repo}", response_model=MapResponse)
@limiter.limit("20/minute")
async def map_endpoints(
    request: Request,
    owner: str,
    repo: str,
    force_framework: Optional[str] = None,
) -> MapResponse:
    """
    Map API endpoints for a public GitHub repository.

    Pass `force_framework` to override detection (useful for testing).
    Example: GET /api/map/tiangolo/fastapi?force_framework=fastapi
    """
    start = time.monotonic()

    # Step 1: deterministic stack analysis (reuse Atlas pipeline, no LLM)
    try:
        evidence = await run_analysis(owner, repo)
    except Exception as exc:
        logger.exception("Stack analysis failed for %s/%s", owner, repo)
        raise HTTPException(status_code=502, detail="Could not fetch repository data.")

    detected_stack: dict = evidence.get("detected_stack", {})

    # Step 2: determine framework
    if force_framework:
        framework = force_framework.lower()
        confidence = "high"
        from_profile = False
    else:
        framework, confidence = _build_profile(detected_stack)
        from_profile = True

    profile_used = ProfileUsed(
        framework=framework,
        framework_confidence=confidence,
        from_profile=from_profile,
        detected_backend=detected_stack.get("backend", []),
        detected_frontend=detected_stack.get("frontend", []),
    )

    # Step 3: extract routes with targeted patterns
    try:
        endpoint_map = await extract_endpoints(
            owner=owner,
            repo=repo,
            framework=framework,
            framework_confidence=confidence,
            from_profile=from_profile,
        )
    except Exception as exc:
        logger.exception("Route extraction failed for %s/%s", owner, repo)
        raise HTTPException(status_code=502, detail="Route extraction failed.")

    # Step 4: LLM enrichment (grouping + descriptions)
    try:
        enriched = await enrich_endpoint_map(endpoint_map=endpoint_map)
    except Exception as exc:
        logger.exception("Endpoint enrichment failed for %s/%s", owner, repo)
        raise HTTPException(status_code=502, detail="Endpoint enrichment failed.")

    return MapResponse(
        repo=f"{owner}/{repo}",
        profile_used=profile_used,
        groups=enriched.get("groups", []),
        summary=enriched.get("summary", ""),
        api_style=enriched.get("api_style", "Unknown"),
        auth_pattern=enriched.get("auth_pattern", "Unknown"),
        files_scanned=endpoint_map.files_scanned,
        raw_endpoint_count=len(endpoint_map.endpoints),
        warnings=enriched.get("warnings", []),
        duration_ms=int((time.monotonic() - start) * 1000),
    )
