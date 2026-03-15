"""
scout.py — FastAPI router, v1 corrected.

FIX [4]: catches all service exceptions and returns safe ScoutError responses.
         Raw exception text never reaches the client.
FIX [7]: github_token excluded from response serialisation (see schema exclude=True).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from app.llm.provider import get_llm_provider  # reuse Atlas's existing DI
from app.schemas.scout import ScoutError, ScoutRequest, ScoutResponse
from app.services.repo_scout import run_scout

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/scout", tags=["scout"])

# Safe error messages keyed to runtime error slugs.
# Raw exception text is logged server-side only, never sent to client.
_ERROR_MESSAGES: dict[str, tuple[int, str]] = {
    "github_rate_limit": (
        429, "GitHub rate limit reached. Add a GitHub token to raise it to 5000 req/hr."
    ),
    "github_invalid_query": (400, "GitHub rejected the query. Try simpler search terms."),
    "gitlab_rate_limit":    (429, "GitLab rate limit reached. Try again in a moment."),
}


@router.post(
    "/search",
    response_model=ScoutResponse,
    responses={
        400: {"model": ScoutError},
        429: {"model": ScoutError},
        502: {"model": ScoutError},
    },
)
async def scout_search(
    req: ScoutRequest,
    llm=Depends(get_llm_provider),
):
    try:
        return await run_scout(req, llm)
    except RuntimeError as e:
        # Known error slugs from platform fetchers
        slug = str(e)
        logger.warning("Scout known error: %s", slug)
        status_code, message = _ERROR_MESSAGES.get(slug, (502, "An upstream error occurred."))
        raise HTTPException(status_code=status_code, detail=message)
    except Exception:
        # Unknown errors: log full traceback, return safe message
        logger.exception("Scout unexpected error for query %r", req.query)
        raise HTTPException(
            status_code=502,
            detail="An unexpected error occurred. Please try again.",
        )
