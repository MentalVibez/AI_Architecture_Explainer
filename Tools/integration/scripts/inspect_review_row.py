#!/usr/bin/env python3
"""
Inspect a stored Review row to verify DB mapping is correct.

Run after a successful staging review:
    python integration/scripts/inspect_review_row.py --result-id <uuid>

Or to inspect the most recent review:
    python integration/scripts/inspect_review_row.py --latest

Prints a clear table of all scalar fields and a summary of JSONB payloads.
This is the "manually inspect one stored row" step before calling backend done.
"""
import argparse
import asyncio
import json
import sys


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--result-id", default=None)
    parser.add_argument("--latest",    action="store_true")
    args = parser.parse_args()

    if not args.result_id and not args.latest:
        print("Usage: --result-id <uuid>  OR  --latest")
        sys.exit(1)

    # Import after arg parse so --help works without DB
    try:
        from app.core.database import async_session_factory
        from app.models.review import Review
        from sqlalchemy import select
    except ImportError as e:
        print(f"Import error: {e}")
        print("Run from inside the backend/ directory with the app installed.")
        sys.exit(1)

    async with async_session_factory() as db:
        if args.latest:
            result = await db.scalar(
                select(Review).order_by(Review.created_at.desc()).limit(1)
            )
        else:
            import uuid
            result = await db.get(Review, uuid.UUID(args.result_id))

        if not result:
            print("No review found.")
            sys.exit(1)

        print(f"\nReview row: {result.id}")
        print(f"Job:        {result.job_id}")
        print(f"Repo:       {result.repo_url}")
        print(f"Commit:     {result.commit}  Branch: {result.branch}")
        print(f"Created:    {result.created_at}")
        print(f"Completed:  {result.completed_at}")

        print(f"\n── Engine metadata ──────────────────────────────────")
        print(f"Ruleset:    {result.ruleset_version or '(null)'}")
        print(f"Depth:      {result.depth_level or '(null) ← FAIL if null'}")
        print(f"Confidence: {result.confidence_label or '(null) ← FAIL if null'}")

        print(f"\n── Scalar scores ────────────────────────────────────")
        score_fields = [
            ("overall_score",              result.overall_score),
            ("security_score",             result.security_score),
            ("testing_score",              result.testing_score),
            ("maintainability_score",      result.maintainability_score),
            ("reliability_score",          result.reliability_score),
            ("operations_score",           result.operations_score),
            ("developer_experience_score", result.developer_experience_score),
        ]
        for name, value in score_fields:
            status = "" if value is not None else "  ← FAIL: null"
            print(f"  {name:<32} {value}{status}")

        print(f"\n── Verdict scalars ──────────────────────────────────")
        print(f"  verdict_label:        {result.verdict_label or '(null) ← FAIL'}")
        print(f"  trust_recommendation: {result.trust_recommendation or '(null)'}")
        print(f"  production_suitable:  {result.production_suitable}")
        print(f"  anti_gaming_verdict:  {result.anti_gaming_verdict or '(null) ← FAIL'}")

        print(f"\n── JSONB payloads ────────────────────────────────────")
        jsonb_fields = [
            ("scorecard_json",   result.scorecard_json),
            ("findings_json",    result.findings_json),
            ("coverage_json",    result.coverage_json),
            ("depth_json",       result.depth_json),
            ("anti_gaming_json", result.anti_gaming_json),
            ("summary_json",     result.summary_json),
            ("meta_json",        result.meta_json),
        ]
        for name, value in jsonb_fields:
            if value is None:
                print(f"  {name:<20} NULL  ← FAIL")
            elif isinstance(value, list):
                print(f"  {name:<20} list  ({len(value)} items)")
            elif isinstance(value, dict):
                keys = list(value.keys())[:5]
                print(f"  {name:<20} dict  (keys: {keys})")
            else:
                print(f"  {name:<20} {type(value).__name__}")

        if result.error_code:
            print(f"\n── Error (this is a failed review) ──────────────")
            print(f"  error_code:    {result.error_code}")
            print(f"  error_message: {result.error_message}")

        # Check for nulls in required fields
        required_nulls = [
            name for name, value in score_fields if value is None
        ] + [
            name for name, value in jsonb_fields if value is None
        ]
        required_nulls += [
            f for f, v in [
                ("verdict_label", result.verdict_label),
                ("depth_level", result.depth_level),
                ("anti_gaming_verdict", result.anti_gaming_verdict),
            ] if not v
        ]

        print(f"\n── Assessment ────────────────────────────────────────")
        if not required_nulls:
            print(f"  ✓ All required fields populated — DB mapping is correct.")
        else:
            print(f"  ✗ Null fields detected: {required_nulls}")
            print(f"    Fix Review.from_report() mapping.")


asyncio.run(main())
