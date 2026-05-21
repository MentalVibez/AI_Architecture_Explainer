"""app/api/routes_webhook.py

Receives GitHub webhook events and queues Review jobs automatically.

Security: every request must carry a valid X-Hub-Signature-256 header
signed with the GITHUB_WEBHOOK_SECRET. Requests without a configured
secret or with an invalid signature are rejected with 400/403.
"""

from __future__ import annotations

import hashlib
import hmac
import logging

from fastapi import APIRouter, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.review_job import ReviewJob

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])

_HANDLED_ACTIONS = {"opened", "synchronize", "reopened"}


def _verify_signature(body: bytes, signature_header: str | None) -> None:
    """Raise HTTPException if the HMAC-SHA256 signature does not match."""
    if not settings.github_webhook_secret:
        raise HTTPException(status_code=400, detail="Webhook secret not configured")
    if not signature_header or not signature_header.startswith("sha256="):
        raise HTTPException(status_code=403, detail="Missing or malformed signature")
    expected = "sha256=" + hmac.new(
        settings.github_webhook_secret.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected, signature_header):
        raise HTTPException(status_code=403, detail="Invalid signature")


@router.post("/github")
async def github_webhook(
    request: Request,
    x_hub_signature_256: str | None = Header(default=None),
    x_github_event: str | None = Header(default=None),
) -> dict[str, str]:
    body = await request.body()
    _verify_signature(body, x_hub_signature_256)

    if x_github_event != "pull_request":
        return {"status": "ignored", "reason": f"event={x_github_event}"}

    payload = await request.json()
    action = payload.get("action")
    if action not in _HANDLED_ACTIONS:
        return {"status": "ignored", "reason": f"action={action}"}

    pr = payload.get("pull_request", {})
    base_repo = pr.get("base", {}).get("repo", {})
    head = pr.get("head", {})

    repo_url: str | None = base_repo.get("clone_url") or base_repo.get("html_url")
    branch: str = head.get("ref") or "main"
    commit: str | None = head.get("sha") or None
    pr_number: int | None = pr.get("number")
    pr_repo: str | None = base_repo.get("full_name")

    if not repo_url or not pr_number or not pr_repo:
        logger.warning("github_webhook_malformed_payload action=%s", action)
        raise HTTPException(status_code=422, detail="Incomplete pull_request payload")

    async with AsyncSessionLocal() as db:
        job = ReviewJob(
            repo_url=repo_url,
            branch=branch,
            commit=commit,
            pr_number=pr_number,
            pr_repo=pr_repo,
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)

    logger.info(
        "github_webhook_queued action=%s pr=%s#%d job_id=%s",
        action, pr_repo, pr_number, job.id,
    )
    return {"status": "queued", "job_id": str(job.id)}
