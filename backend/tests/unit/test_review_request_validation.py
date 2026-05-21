import pytest
from pydantic import ValidationError

from app.api.routes_review import ReviewRequest


def test_review_request_accepts_hex_commit():
    req = ReviewRequest(
        repo_url="https://github.com/owner/repo",
        branch="main",
        commit="ABCDEF1234567",
    )

    assert req.commit == "abcdef1234567"


def test_review_request_rejects_non_hex_commit():
    with pytest.raises(ValidationError):
        ReviewRequest(
            repo_url="https://github.com/owner/repo",
            branch="main",
            commit="not-a-sha",
        )


def test_review_request_rejects_dangerous_branch_shape():
    with pytest.raises(ValidationError):
        ReviewRequest(
            repo_url="https://github.com/owner/repo",
            branch="-upload-pack=whoops",
        )
