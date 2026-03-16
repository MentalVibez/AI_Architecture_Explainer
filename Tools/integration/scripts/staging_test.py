#!/usr/bin/env python3
"""
3-case backend staging test.

Run this after Phase 2 is wired and deployed to Railway staging.
Tests the full job lifecycle through the real HTTP API.

Usage:
    python scripts/staging_test.py --base-url https://your-app.railway.app

Verifies:
    Case 1: Known good repo — full happy path
    Case 2: Invalid URL — clean 400/queued-then-failed response
    Case 3: Old-branch repo (master) — fallback clone works
"""
import argparse
import time
import sys
import json
import urllib.request
import urllib.error

MAX_POLL_SECONDS = 360   # allow up to 6 min for staging (slower than local)
POLL_INTERVAL    = 5


def api(base_url: str, method: str, path: str, body: dict | None = None) -> dict:
    url = base_url.rstrip("/") + path
    data = json.dumps(body).encode() if body else None
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = json.loads(e.read())
        return {"__status": e.code, "__error": body}


def poll_until_done(base_url: str, job_id: str, label: str) -> dict:
    deadline = time.time() + MAX_POLL_SECONDS
    while time.time() < deadline:
        status = api(base_url, "GET", f"/api/review/{job_id}")
        s = status.get("status", "?")
        print(f"  [{label}] {s}...", end="", flush=True)
        if s in ("completed", "failed"):
            print(f"  [{label}] {s}          ")
            return status
        time.sleep(POLL_INTERVAL)
    print(f"  [{label}] TIMEOUT after {MAX_POLL_SECONDS}s")
    return {"status": "timeout"}


def run_case(base_url: str, case_num: int, label: str,
             repo_url: str, branch: str | None,
             expect_success: bool, expect_error_code: str | None = None) -> bool:

    print(f"
Case {case_num}: {label}")
    print(f"  repo_url: {repo_url}")
    print(f"  branch:   {branch or 'auto'}")
    print(f"  expect:   {'success' if expect_success else f'fail ({expect_error_code})'}")

    # Submit
    body = {"repo_url": repo_url}
    if branch:
        body["branch"] = branch
    resp = api(base_url, "POST", "/api/review", body)

    if "__status" in resp:
        if not expect_success and resp["__status"] == 400:
            err = resp.get("__error", {}).get("error", "?")
            if expect_error_code and err != expect_error_code:
                print(f"  FAIL: expected error_code={expect_error_code!r}, got {err!r}")
                return False
            print(f"  ✓ Got 400 with error={err}")
            return True
        print(f"  FAIL: unexpected HTTP {resp['__status']}: {resp.get('__error')}")
        return False

    job_id = resp.get("job_id")
    if not job_id:
        print(f"  FAIL: no job_id in response: {resp}")
        return False
    print(f"  job_id: {job_id}")

    # Poll
    status = poll_until_done(base_url, job_id, label)
    final_status = status.get("status")

    if expect_success:
        if final_status != "completed":
            print(f"  FAIL: expected completed, got {final_status}")
            print(f"  error_code: {status.get('error_code')}")
            print(f"  error_message: {status.get('error_message')}")
            return False

        result_id = status.get("result_id")
        if not result_id:
            print(f"  FAIL: no result_id on completed job")
            return False

        # Fetch result
        result = api(base_url, "GET", f"/api/results/review/{result_id}")
        if "__status" in result:
            print(f"  FAIL: fetch result returned HTTP {result['__status']}")
            return False

        # Verify key fields
        checks = {
            "overall_score":    result.get("overall_score"),
            "verdict_label":    result.get("verdict_label"),
            "depth_level":      result.get("depth_level"),
            "confidence_label": result.get("confidence_label"),
            "production_suitable": result.get("production_suitable") is not None,
            "scorecard present": bool(result.get("scorecard")),
            "findings present":  result.get("findings") is not None,
            "summary present":   bool(result.get("summary")),
        }
        failed_checks = [k for k, v in checks.items() if not v]
        if failed_checks:
            print(f"  FAIL: missing fields: {failed_checks}")
            return False

        print(f"  ✓ result_id: {result_id}")
        print(f"  ✓ score={result['overall_score']} verdict={result['verdict_label']}")
        print(f"  ✓ depth={result['depth_level']} conf={result['confidence_label']}")
        print(f"  ✓ findings={len(result.get('findings', []))}")
        print(f"  ✓ anti_gaming={result.get('anti_gaming_verdict')}")
        print(f"  ✓ all scalar fields populated")
        return True

    else:
        if final_status != "failed":
            print(f"  FAIL: expected failed, got {final_status}")
            return False
        error_code = status.get("error_code")
        if expect_error_code and error_code != expect_error_code:
            print(f"  FAIL: expected error_code={expect_error_code!r}, got {error_code!r}")
            return False
        print(f"  ✓ failed with error_code={error_code}")
        return True


def main():
    parser = argparse.ArgumentParser(description="Atlas Reviewer staging test")
    parser.add_argument("--base-url", required=True, help="Railway staging base URL")
    args = parser.parse_args()

    base = args.base_url
    print(f"Atlas Reviewer — 3-case staging test")
    print(f"Base URL: {base}")

    # Health check first
    health = api(base, "GET", "/health")
    if "__status" in health:
        print(f"FAIL: health check returned HTTP {health['__status']}")
        sys.exit(1)
    print(f"Health: {health}")

    results = []

    # Case 1: Known good repo (httpx — strong Python, main branch)
    results.append(run_case(
        base, 1, "Known good (httpx, main branch)",
        repo_url="https://github.com/encode/httpx",
        branch="main",
        expect_success=True,
    ))

    # Case 2: Invalid URL — should fail fast with INVALID_URL
    results.append(run_case(
        base, 2, "Invalid URL (GitLab)",
        repo_url="https://gitlab.com/owner/repo",
        branch=None,
        expect_success=False,
        expect_error_code="INVALID_URL",
    ))

    # Case 3: Old-branch repo (reader uses master) — branch fallback must work
    results.append(run_case(
        base, 3, "Old-branch repo (reader, master branch)",
        repo_url="https://github.com/realpython/reader",
        branch=None,   # should auto-detect
        expect_success=True,
    ))

    print(f"
{'='*60}")
    passed = sum(results)
    total  = len(results)
    print(f"Results: {passed}/{total} passed")

    if passed == total:
        print("✓ STAGING TEST PASSED — backend is ready for frontend wiring")
        sys.exit(0)
    else:
        print("✗ STAGING TEST FAILED — fix issues before frontend work")
        sys.exit(1)


if __name__ == "__main__":
    main()
