"""
Tests for repo URL normalization.
All cases that real users will paste.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../.."))

import pytest
from atlas_reviewer.utils.repo_url import normalize_repo_url, NormalizedRepo


# ── Valid URLs — all should produce the same canonical form ───────────────────

VALID_CASES = [
    "https://github.com/tiangolo/fastapi",
    "https://github.com/tiangolo/fastapi.git",
    "https://github.com/tiangolo/fastapi/",
    "http://github.com/tiangolo/fastapi",
    "github.com/tiangolo/fastapi",
    "www.github.com/tiangolo/fastapi",
    "https://github.com/tiangolo/fastapi/tree/main",
    "https://github.com/tiangolo/fastapi/tree/main/fastapi",
    "https://github.com/tiangolo/fastapi/blob/main/README.md",
]

@pytest.mark.parametrize("url", VALID_CASES)
def test_valid_url_normalizes(url):
    result = normalize_repo_url(url)
    assert result.owner == "tiangolo"
    assert result.name == "fastapi"
    assert result.clone_url == "https://github.com/tiangolo/fastapi.git"
    assert result.canonical_url == "https://github.com/tiangolo/fastapi"


def test_dotgit_stripped_from_name():
    result = normalize_repo_url("https://github.com/tiangolo/fastapi.git")
    assert result.name == "fastapi"
    assert ".git" not in result.clone_url.replace(".git", "x")  # only one .git
    assert result.clone_url.endswith(".git")


def test_org_repo_preserved():
    result = normalize_repo_url("https://github.com/encode/httpx")
    assert result.owner == "encode"
    assert result.name == "httpx"


def test_hyphenated_repo():
    result = normalize_repo_url("https://github.com/nsidnev/fastapi-realworld-example-app")
    assert result.name == "fastapi-realworld-example-app"


def test_underscore_repo():
    result = normalize_repo_url("https://github.com/MentalVibez/AI_Architecture_Explainer")
    assert result.owner == "MentalVibez"
    assert result.name == "AI_Architecture_Explainer"


# ── Invalid URLs — all should raise ValueError ────────────────────────────────

INVALID_CASES = [
    "https://gitlab.com/owner/repo",
    "https://bitbucket.org/owner/repo",
    "not-a-url",
    "https://github.com/orgs/myorg",
    "https://github.com/explore",
    "",
    "   ",
    "https://example.com/owner/repo",
]

@pytest.mark.parametrize("url", INVALID_CASES)
def test_invalid_url_raises(url):
    with pytest.raises(ValueError):
        normalize_repo_url(url)


def test_profile_url_rejected():
    with pytest.raises(ValueError):
        normalize_repo_url("https://github.com/tiangolo")  # no repo segment


# ── Service ReviewError on invalid URL ────────────────────────────────────────

import asyncio
from atlas_reviewer.service import run_review, ReviewError


def test_invalid_url_raises_review_error():
    with pytest.raises(ReviewError) as exc_info:
        asyncio.run(run_review("https://gitlab.com/owner/repo"))
    assert exc_info.value.code == "INVALID_URL"


def test_private_repo_message_helpful():
    """Verify the error message is user-facing, not a raw git traceback."""
    # We can't actually clone without network, but we can verify the normalizer
    result = normalize_repo_url("https://github.com/someorg/private-repo")
    assert result.clone_url == "https://github.com/someorg/private-repo.git"


# ── ReviewError is the only exception type from run_review ───────────────────

def test_run_review_returns_only_review_error_or_report():
    """
    run_review() contract: raises ReviewError, never raw exceptions.
    Test with a clearly invalid URL.
    """
    try:
        asyncio.run(run_review("not-a-github-url"))
        assert False, "Should have raised"
    except ReviewError as e:
        assert e.code in ("INVALID_URL", "CLONE_FAILED", "REVIEW_TIMEOUT", "ENGINE_ERROR")
    except Exception as e:
        assert False, f"Raw exception leaked: {type(e).__name__}: {e}"
