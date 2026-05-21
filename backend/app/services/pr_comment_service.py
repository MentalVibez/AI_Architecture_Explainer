"""app/services/pr_comment_service.py

Posts a formatted CodeBaseAtlas review summary as a GitHub PR comment.
Fire-and-forget: never raises — failures are logged and swallowed.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.review import Review
    from app.models.review_job import ReviewJob

logger = logging.getLogger(__name__)

_SEVERITY_ICONS = {
    "critical": "🔴",
    "high": "🔴",
    "medium": "🟡",
    "warning": "🟡",
    "low": "🟢",
    "info": "⚪",
}

_FRONTEND_BASE = "https://codebaseatlas.com"


def _verdict_line(review: "Review") -> str:
    icon = "✅" if review.production_suitable else "⚠️"
    parts = [icon]
    if review.verdict_label:
        parts.append(review.verdict_label)
    if review.overall_score is not None:
        parts.append(f"· Score: {review.overall_score}/100")
    return " ".join(parts) if len(parts) > 1 else f"{icon} Analysis complete"


def _findings_section(findings: list[dict]) -> str:
    if not findings:
        return ""
    lines = ["", "### Findings", "| | Finding |", "|---|---|"]
    for f in findings[:8]:
        severity = (f.get("severity") or "").lower()
        icon = _SEVERITY_ICONS.get(severity, "⚪")
        title = f.get("title") or f.get("rule_id") or "Unnamed finding"
        lines.append(f"| {icon} | {title} |")
    if len(findings) > 8:
        lines.append(f"| | *…and {len(findings) - 8} more* |")
    return "\n".join(lines)


def build_comment(review: "Review", result_url: str) -> str:
    lines = ["## CodeBaseAtlas Review", ""]
    lines.append(f"**Verdict**: {_verdict_line(review)}")

    summary = review.summary_json or {}
    developer_summary = summary.get("developer") if isinstance(summary, dict) else None
    if developer_summary:
        lines.append("")
        lines.append(f"> {developer_summary[:400]}")

    findings = review.findings_json or []
    findings_md = _findings_section(findings)
    if findings_md:
        lines.append(findings_md)

    lines.append("")
    lines.append(f"[View full report →]({result_url})")
    return "\n".join(lines)


def build_error_comment(error_message: str | None) -> str:
    detail = error_message or "An unexpected error occurred during analysis."
    return f"## CodeBaseAtlas Review\n\n⚠️ Analysis could not be completed: {detail[:300]}"


async def post_pr_comment(
    *,
    pr_repo: str,
    pr_number: int,
    review: "Review",
    job: "ReviewJob",
) -> None:
    """Post a review summary comment on the GitHub PR. Never raises."""
    from app.core.config import settings
    from app.services.github_service import create_github_client

    if not settings.github_token:
        logger.debug("pr_comment_skipped reason=no_github_token pr=%s#%d", pr_repo, pr_number)
        return

    result_url = f"{_FRONTEND_BASE}/review/results/{review.id}"

    if review.error_code:
        body = build_error_comment(review.error_message)
    else:
        body = build_comment(review, result_url)

    url = f"/repos/{pr_repo}/issues/{pr_number}/comments"

    try:
        async with create_github_client() as client:
            response = await client.post(url, json={"body": body})
            if response.status_code == 201:
                logger.info(
                    "pr_comment_posted pr=%s#%d result_id=%s",
                    pr_repo, pr_number, review.id,
                )
            else:
                logger.warning(
                    "pr_comment_failed pr=%s#%d status=%d",
                    pr_repo, pr_number, response.status_code,
                )
    except Exception:
        logger.debug(
            "pr_comment_error pr=%s#%d", pr_repo, pr_number, exc_info=True
        )
