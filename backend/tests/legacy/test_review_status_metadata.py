from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

from app.api.routes_review import _build_review_status_response
from app.models.review_job import ReviewJob


def _utcnow_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def test_review_status_response_for_running_job_includes_progress_hints():
    started = _utcnow_naive() - timedelta(seconds=42)
    job = ReviewJob(
        id=uuid4(),
        status="running",
        repo_url="https://github.com/example/repo",
        branch="main",
        created_at=started,
        started_at=started,
    )

    payload = _build_review_status_response(job, review=None)

    assert payload.phase == "analysis"
    assert payload.duration_seconds >= 42
    assert payload.next_poll_seconds == 5
    assert payload.suggested_action == "Keep polling until the report is ready."


def test_review_status_response_for_failed_job_maps_retry_guidance():
    started = _utcnow_naive() - timedelta(seconds=10)
    completed = _utcnow_naive()
    job = ReviewJob(
        id=uuid4(),
        status="failed",
        repo_url="https://github.com/example/repo",
        branch="main",
        error_code="REVIEW_TIMEOUT",
        error_message="timed out",
        created_at=started,
        started_at=started,
        completed_at=completed,
    )
    review = SimpleNamespace(id=uuid4(), error_code="REVIEW_TIMEOUT", error_message="timed out")

    payload = _build_review_status_response(job, review=review)

    assert payload.phase == "failed"
    assert payload.retryable is True
    assert payload.next_poll_seconds is None
    assert "time budget" in payload.status_detail
    assert payload.suggested_action == (
        "Retry the review in a moment. If it keeps failing, inspect backend logs."
    )
