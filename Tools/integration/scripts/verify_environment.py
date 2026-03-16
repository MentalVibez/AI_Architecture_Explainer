#!/usr/bin/env python3
"""
Verify Railway container has all required tools and correct configuration.

Run this as a Railway "pre-deploy" check or via Railway shell after deploy:
    python integration/scripts/verify_environment.py

Checks:
  - git is installed and functional
  - ruff is installed
  - bandit is installed
  - pip-audit is installed
  - gitleaks installed (optional — noted if missing)
  - /tmp is writable with enough space
  - ANTHROPIC_API_KEY is set
  - DATABASE_URL is set
  - reviewer module is importable
"""
import os
import sys
import shutil
import subprocess
import tempfile

PASS = "✓"
FAIL = "✗"
WARN = "⚠"
results = []


def run(cmd: list[str]) -> tuple[int, str]:
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    return r.returncode, (r.stdout + r.stderr).strip()


def check(label: str, ok: bool, detail: str = "", warn_only: bool = False):
    symbol = PASS if ok else (WARN if warn_only else FAIL)
    print(f"  {symbol} {label}" + (f" ({detail})" if detail else ""))
    if not warn_only:
        results.append(ok)


print("\nAtlas Reviewer — Environment Verification")
print("=" * 50)

# ── Required binaries ─────────────────────────────────────────────────────────
print("\nRequired binaries:")

rc, out = run(["git", "--version"])
check("git", rc == 0, out.split("\n")[0] if rc == 0 else out[:80])

rc, out = run(["ruff", "--version"])
check("ruff", rc == 0, out.split("\n")[0] if rc == 0 else out[:80])

rc, out = run(["bandit", "--version"])
check("bandit", rc == 0, out.split("\n")[0] if rc == 0 else "not found")

rc, out = run(["pip-audit", "--version"])
check("pip-audit", rc == 0, out.split("\n")[0] if rc == 0 else "not found")

# Optional
rc, out = run(["gitleaks", "version"])
check("gitleaks", rc == 0, out.strip() if rc == 0 else "not installed — secrets depth limited",
      warn_only=(rc != 0))

# ── Filesystem ────────────────────────────────────────────────────────────────
print("\nFilesystem:")

# /tmp writable
try:
    with tempfile.TemporaryDirectory() as tmp:
        test_file = os.path.join(tmp, "test.txt")
        with open(test_file, "w") as f:
            f.write("test")
    check("/tmp writable", True)
except Exception as e:
    check("/tmp writable", False, str(e))

# /tmp space — need at least 1GB for large repos
tmp_stat = shutil.disk_usage("/tmp")
tmp_gb = tmp_stat.free / (1024**3)
check("/tmp free space", tmp_gb >= 1.0, f"{tmp_gb:.1f} GB free")

# ── Environment variables ─────────────────────────────────────────────────────
print("\nEnvironment variables:")

anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
check("ANTHROPIC_API_KEY", bool(anthropic_key),
      "set" if anthropic_key else "NOT SET — LLM summaries will use deterministic fallback",
      warn_only=not bool(anthropic_key))

db_url = os.environ.get("DATABASE_URL", "")
check("DATABASE_URL", bool(db_url), "set" if db_url else "NOT SET — DB writes will fail")

# ── Python imports ────────────────────────────────────────────────────────────
print("\nPython imports:")

try:
    from app.services.reviewer.service import run_review, ReviewError
    check("reviewer.service", True)
except ImportError as e:
    check("reviewer.service", False, str(e))

try:
    from app.models.review import Review
    check("models.review", True)
except ImportError as e:
    check("models.review", False, str(e))

try:
    from app.services.review_worker import process_review_job
    check("review_worker", True)
except ImportError as e:
    check("review_worker", False, str(e))

# ── Quick clone test ──────────────────────────────────────────────────────────
print("\nClone test (small public repo):")
try:
    with tempfile.TemporaryDirectory() as tmp:
        rc, out = run(["git", "clone", "--depth", "1",
                       "https://github.com/encode/httpx", tmp])
        check("git clone succeeds", rc == 0, out[:80] if rc != 0 else "")
        if rc == 0:
            rc2, sha = run(["git", "rev-parse", "--short", "HEAD"])
            # Use subprocess with cwd
            r2 = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd=tmp, capture_output=True, text=True
            )
            check("commit SHA readable", r2.returncode == 0, r2.stdout.strip())
except Exception as e:
    check("git clone test", False, str(e))

# ── Summary ───────────────────────────────────────────────────────────────────
total  = len(results)
passed = sum(results)
failed = total - passed

print(f"\n{'='*50}")
print(f"Environment check: {passed}/{total} required checks passed")

if failed == 0:
    print("\n✓ Container is ready for review jobs.")
    sys.exit(0)
else:
    print(f"\n✗ {failed} required check(s) failed — fix before running staging test.")
    sys.exit(1)
