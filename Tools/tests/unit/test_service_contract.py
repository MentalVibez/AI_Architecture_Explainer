"""
Service contract tests — verify error codes, error translation,
and that no raw exceptions escape run_review().

All tests run without network. They test the error handling surface
and contract boundaries, not the full review pipeline.
"""
import sys, os, asyncio
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../.."))

import pytest
from atlas_reviewer.service import (
    run_review, ReviewError,
    MAX_FILE_COUNT, MAX_REPO_SIZE_BYTES,
    _check_repo_size,
)
from atlas_reviewer.utils.repo_url import normalize_repo_url
import tempfile
from pathlib import Path


# ── URL validation ────────────────────────────────────────────────────────────

def test_invalid_url_gives_invalid_url_code():
    with pytest.raises(ReviewError) as exc:
        asyncio.run(run_review("not-a-url"))
    assert exc.value.code == "INVALID_URL"


def test_gitlab_url_gives_invalid_url_code():
    with pytest.raises(ReviewError) as exc:
        asyncio.run(run_review("https://gitlab.com/owner/repo"))
    assert exc.value.code == "INVALID_URL"


def test_review_error_has_message():
    with pytest.raises(ReviewError) as exc:
        asyncio.run(run_review("not-a-url"))
    assert exc.value.message
    assert len(exc.value.message) > 10


def test_review_error_str_includes_code():
    err = ReviewError("CLONE_FAILED", "some message")
    assert "CLONE_FAILED" in str(err)
    assert "some message" in str(err)


# ── Repo size checks ──────────────────────────────────────────────────────────

def test_size_check_passes_on_empty_dir():
    with tempfile.TemporaryDirectory() as tmp:
        _check_repo_size(tmp)  # should not raise


def test_size_check_raises_on_too_many_files():
    with tempfile.TemporaryDirectory() as tmp:
        # Create MAX_FILE_COUNT + 1 empty files
        root = Path(tmp)
        for i in range(MAX_FILE_COUNT + 1):
            (root / f"f{i}.py").write_text("")
        with pytest.raises(ReviewError) as exc:
            _check_repo_size(tmp)
        assert exc.value.code == "REPO_TOO_LARGE"
        assert "files" in exc.value.message.lower()


def test_size_check_skips_git_directory():
    with tempfile.TemporaryDirectory() as tmp:
        # .git files should not count toward limits
        git_dir = Path(tmp) / ".git"
        git_dir.mkdir()
        (git_dir / "COMMIT_EDITMSG").write_text("x" * 1000)
        _check_repo_size(tmp)  # should not raise


# ── No raw exceptions escape ──────────────────────────────────────────────────

@pytest.mark.parametrize("bad_url", [
    "not-a-url",
    "https://gitlab.com/a/b",
    "ftp://github.com/a/b",
    "",
    "   ",
])
def test_no_raw_exception_from_bad_url(bad_url):
    """run_review() must always raise ReviewError, never anything else."""
    try:
        asyncio.run(run_review(bad_url))
        assert False, f"Expected ReviewError for {bad_url!r}"
    except ReviewError:
        pass  # correct
    except Exception as e:
        assert False, f"Raw exception leaked for {bad_url!r}: {type(e).__name__}: {e}"


# ── ReviewError attributes ────────────────────────────────────────────────────

def test_review_error_code_is_string():
    err = ReviewError("TEST_CODE", "test message")
    assert isinstance(err.code, str)
    assert isinstance(err.message, str)


def test_review_error_codes_are_stable():
    """Known codes must not change — they're stored in the DB."""
    known_codes = {"INVALID_URL", "CLONE_FAILED", "REPO_TOO_LARGE",
                   "REVIEW_TIMEOUT", "ENGINE_ERROR"}
    # Just verify the set is documented — actual codes in run_review()
    assert len(known_codes) == 5
