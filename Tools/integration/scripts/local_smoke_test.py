#!/usr/bin/env python3
"""
Local smoke test — run inside backend/ before deploying to Railway.

Tests the wiring layer directly (no HTTP server needed):
  1. Imports resolve cleanly
  2. Reviewer service callable
  3. ReviewReport → Review.from_report() mapping complete
  4. Rate limiter logic correct
  5. URL normalizer handles all variants

Usage:
    cd backend
    python ../integration/scripts/local_smoke_test.py

Expected: all checks pass in ~60 seconds (one real repo clone).
"""
import sys
import asyncio
import traceback

PASS = "✓"
FAIL = "✗"
results = []


def check(label: str, fn):
    try:
        fn()
        print(f"  {PASS} {label}")
        results.append(True)
    except Exception as e:
        print(f"  {FAIL} {label}")
        print(f"       {type(e).__name__}: {e}")
        results.append(False)


async def check_async(label: str, fn):
    try:
        await fn()
        print(f"  {PASS} {label}")
        results.append(True)
    except Exception as e:
        print(f"  {FAIL} {label}")
        print(f"       {type(e).__name__}: {e}")
        if "--verbose" in sys.argv:
            traceback.print_exc()
        results.append(False)


# ── 1. Import checks ──────────────────────────────────────────────────────────
print("\n1. Import checks")

def test_service_import():
    from app.services.reviewer.service import run_review, ReviewError
    assert callable(run_review)

def test_model_import():
    from app.models.review import Review
    assert hasattr(Review, "from_report")
    assert hasattr(Review, "from_error")

def test_worker_import():
    from app.services.review_worker import process_review_job
    assert callable(process_review_job)

def test_rate_limit_import():
    from app.middleware.rate_limit import check_review_rate_limit
    assert callable(check_review_rate_limit)

def test_url_normalizer_import():
    from app.services.reviewer.utils.repo_url import normalize_repo_url
    assert callable(normalize_repo_url)

def test_routes_import():
    from app.api.routes.review import router
    assert router is not None

check("service import (run_review, ReviewError)", test_service_import)
check("Review model import (from_report, from_error)", test_model_import)
check("review_worker import (process_review_job)", test_worker_import)
check("rate_limit import (check_review_rate_limit)", test_rate_limit_import)
check("url normalizer import", test_url_normalizer_import)
check("review routes import (router)", test_routes_import)


# ── 2. URL normalizer ─────────────────────────────────────────────────────────
print("\n2. URL normalizer")

def test_url_variants():
    from app.services.reviewer.utils.repo_url import normalize_repo_url
    cases = [
        ("https://github.com/encode/httpx",           "encode", "httpx"),
        ("github.com/encode/httpx",                   "encode", "httpx"),
        ("https://github.com/encode/httpx.git",        "encode", "httpx"),
        ("https://github.com/encode/httpx/tree/main",  "encode", "httpx"),
        ("https://github.com/MentalVibez/AI_Architecture_Explainer",
                                                      "MentalVibez", "AI_Architecture_Explainer"),
    ]
    for url, exp_owner, exp_name in cases:
        r = normalize_repo_url(url)
        assert r.owner == exp_owner, f"{url}: owner={r.owner!r}"
        assert r.name == exp_name, f"{url}: name={r.name!r}"
        assert r.clone_url.endswith(".git")

def test_url_rejection():
    from app.services.reviewer.utils.repo_url import normalize_repo_url
    bad = ["https://gitlab.com/a/b", "not-a-url", "", "https://github.com"]
    for url in bad:
        try:
            normalize_repo_url(url)
            assert False, f"Should have raised for {url!r}"
        except ValueError:
            pass

check("valid URL variants normalize correctly", test_url_variants)
check("invalid URLs raise ValueError", test_url_rejection)


# ── 3. ReviewError contract ───────────────────────────────────────────────────
print("\n3. ReviewError contract")

def test_invalid_url_error():
    from app.services.reviewer.service import run_review, ReviewError
    try:
        asyncio.run(run_review("https://gitlab.com/a/b"))
        assert False, "Should have raised"
    except ReviewError as e:
        assert e.code == "INVALID_URL"
        assert e.message

def test_error_has_stable_attributes():
    from app.services.reviewer.service import ReviewError
    err = ReviewError("CLONE_FAILED", "test message")
    assert isinstance(err.code, str)
    assert isinstance(err.message, str)
    assert "CLONE_FAILED" in str(err)

def test_no_raw_exception_from_bad_url():
    from app.services.reviewer.service import run_review, ReviewError
    try:
        asyncio.run(run_review("not-a-url"))
    except ReviewError:
        pass
    except Exception as e:
        assert False, f"Raw exception leaked: {type(e).__name__}: {e}"

check("INVALID_URL raised for non-GitHub URL", test_invalid_url_error)
check("ReviewError has stable code + message attributes", test_error_has_stable_attributes)
check("No raw exceptions escape run_review()", test_no_raw_exception_from_bad_url)


# ── 4. Rate limiter logic ─────────────────────────────────────────────────────
print("\n4. Rate limiter logic")

def test_rate_limiter_counts():
    import time
    from app.middleware.rate_limit import _review_log, MAX_REVIEWS_PER_DAY

    # Clear state
    _review_log.clear()
    test_ip = "test.smoke.test.ip"

    # Simulate N-1 submissions
    now = time.time()
    for _ in range(MAX_REVIEWS_PER_DAY - 1):
        _review_log[test_ip].append((now, "review"))

    assert len(_review_log[test_ip]) == MAX_REVIEWS_PER_DAY - 1
    _review_log.clear()

check("Rate limiter in-memory store works", test_rate_limiter_counts)


# ── 5. Review model mapping ───────────────────────────────────────────────────
print("\n5. Review model mapping (ReviewReport → Review row)")

async def test_from_report_mapping():
    from app.services.reviewer.service import run_review
    from app.models.review import Review
    import uuid

    # Run a real review
    report = await run_review("https://github.com/encode/httpx")

    # Map to Review row (without DB)
    fake_job_id = uuid.uuid4()
    review = Review.from_report(job_id=fake_job_id, report=report, branch="main")

    # Verify all scalar fields are populated
    assert review.overall_score is not None, "overall_score is None"
    assert review.security_score is not None, "security_score is None"
    assert review.testing_score is not None, "testing_score is None"
    assert review.maintainability_score is not None, "maintainability_score is None"
    assert review.reliability_score is not None, "reliability_score is None"
    assert review.operations_score is not None, "operations_score is None"
    assert review.developer_experience_score is not None, "developer_experience_score is None"
    assert review.verdict_label, "verdict_label is empty"
    assert review.depth_level, "depth_level is empty"
    assert review.confidence_label, "confidence_label is empty"
    assert review.anti_gaming_verdict, "anti_gaming_verdict is empty"
    assert review.production_suitable is not None, "production_suitable is None"

    # Verify JSONB fields are dicts/lists (serializable)
    assert isinstance(review.scorecard_json, dict), "scorecard_json not dict"
    assert isinstance(review.findings_json, list), "findings_json not list"
    assert isinstance(review.coverage_json, dict), "coverage_json not dict"
    assert isinstance(review.depth_json, dict), "depth_json not dict"
    assert isinstance(review.anti_gaming_json, dict), "anti_gaming_json not dict"
    assert isinstance(review.summary_json, dict), "summary_json not dict"
    assert isinstance(review.meta_json, dict), "meta_json not dict"

    # Verify JSONB fields are JSON-serializable (no Pydantic objects buried)
    import json
    json.dumps(review.scorecard_json)
    json.dumps(review.findings_json)
    json.dumps(review.summary_json)

    # Print what will be in the DB
    print(f"       score={review.overall_score} verdict={review.verdict_label}")
    print(f"       depth={review.depth_level} conf={review.confidence_label}")
    print(f"       sec={review.security_score} test={review.testing_score}")
    print(f"       findings={len(review.findings_json)} in JSONB")
    print(f"       anti_gaming={review.anti_gaming_verdict}")
    print(f"       summary keys={list(review.summary_json.keys())}")


async def test_from_error_mapping():
    from app.models.review import Review
    import uuid

    review = Review.from_error(
        job_id=uuid.uuid4(),
        repo_url="https://github.com/test/repo",
        error_code="CLONE_FAILED",
        error_message="git clone returned 128",
    )
    assert review.error_code == "CLONE_FAILED"
    assert review.error_message
    assert review.completed_at is not None
    # All score fields should be None for failed reviews
    assert review.overall_score is None


# Run async checks
asyncio.run(check_async(
    "ReviewReport → Review.from_report() all fields populated (real review of httpx)",
    test_from_report_mapping,
))
check("Review.from_error() populates error fields, score fields null", lambda: asyncio.run(test_from_error_mapping()))


# ── 6. Branch fallback ────────────────────────────────────────────────────────
print("\n6. Branch fallback (reader uses master, not main)")

async def test_branch_fallback():
    from app.services.reviewer.service import run_review
    # reader uses master — this verifies the fallback clone logic works
    report = await run_review("https://github.com/realpython/reader")
    assert report.repo.commit
    assert report.meta.overall_score is not None
    print(f"       commit={report.repo.commit} score={report.meta.overall_score}")

asyncio.run(check_async(
    "Branch fallback: reader (master branch) reviewed successfully",
    test_branch_fallback,
))


# ── Summary ───────────────────────────────────────────────────────────────────
total  = len(results)
passed = sum(results)
failed = total - passed

print(f"\n{'='*60}")
print(f"Smoke test: {passed}/{total} passed")

if failed == 0:
    print("\n✓ ALL CHECKS PASSED")
    print("  The backend wiring is ready for Railway staging deploy.")
    print("  Next: run the alembic migration, then deploy and run staging_test.py")
    sys.exit(0)
else:
    print(f"\n✗ {failed} CHECK(S) FAILED")
    print("  Fix the failing checks before deploying.")
    print("  Run with --verbose for full tracebacks.")
    sys.exit(1)
