"""
Golden benchmark calibration runner.

Runs the full pipeline against each benchmark repo and produces:
  - Per-repo calibration summary
  - Per-category score breakdown
  - Must-find recall + must-not-find precision
  - Score band interpretation
  - Rank-order assertion across buckets
  - Markdown calibration report to tests/golden/snapshots/

Usage:
    python -m atlas_reviewer.tests.golden.runner
    python -m atlas_reviewer.tests.golden.runner --bucket strong_python
    python -m atlas_reviewer.tests.golden.runner --dry-run
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))

import json
import argparse
import tempfile
import subprocess
import statistics
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime

from atlas_reviewer.facts.builder import build_facts
from atlas_reviewer.engine.registry import build_default_registry
from atlas_reviewer.engine.executor import execute
from atlas_reviewer.engine.dedupe import deduplicate
from atlas_reviewer.engine.coverage import build_coverage
from atlas_reviewer.scoring.engine import compute_scorecard, compute_overall
from atlas_reviewer.scoring.interpretation import interpret_report, interpret_overall
from atlas_reviewer.models.report import ReviewReport, RepoMeta

MANIFESTS_DIR = Path(__file__).parent / "manifests"
SNAPSHOTS_DIR = Path(__file__).parent / "snapshots"
SNAPSHOTS_DIR.mkdir(exist_ok=True)


@dataclass
class BandCheck:
    category: str
    actual: int
    lo: int
    hi: int

    @property
    def passed(self): return self.lo <= self.actual <= self.hi
    def __str__(self):
        return f"  {'✓' if self.passed else '✗'} {self.category}: {self.actual} (expected {self.lo}–{self.hi})"


@dataclass
class CalibrationResult:
    repo_name: str
    bucket: str
    overall_score: int
    band_label: str
    trust: str
    scorecard: dict
    band_checks: list = field(default_factory=list)
    recall_misses: list = field(default_factory=list)
    false_positives: list = field(default_factory=list)
    top_findings: list = field(default_factory=list)
    coverage_limits: list = field(default_factory=list)
    applicable_rules: int = 0
    adapters_run: list = field(default_factory=list)
    error: str | None = None

    @property
    def band_pass_rate(self):
        if not self.band_checks: return 1.0
        return sum(1 for c in self.band_checks if c.passed) / len(self.band_checks)

    @property
    def passed(self):
        return (self.error is None
                and self.band_pass_rate >= 0.8
                and not self.recall_misses
                and not self.false_positives)


def run_engine(repo_url: str) -> tuple:
    with tempfile.TemporaryDirectory() as tmp:
        r = subprocess.run(
            ["git", "clone", "--depth", "1", repo_url, tmp],
            capture_output=True, text=True, timeout=180,
        )
        if r.returncode != 0:
            raise RuntimeError(f"Clone failed: {r.stderr[:200]}")

        commit = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=tmp, capture_output=True, text=True,
        ).stdout.strip()

        facts, adapter_results = build_facts(repo_url=repo_url, repo_path=tmp, commit=commit)
        registry = build_default_registry()
        applicable = registry.for_facts(facts)
        findings = deduplicate(execute(registry, facts))
        scorecard = compute_scorecard(findings)
        overall = compute_overall(scorecard)
        coverage = build_coverage(facts, adapter_results, tmp)
        interpreted = interpret_report(scorecard, overall, findings)

        return scorecard, overall, findings, coverage, interpreted, len(applicable), list(adapter_results.keys())


def check_manifest(manifest: dict, scorecard, overall: int, findings: list,
                   coverage, interpreted, applicable: int, adapters: list) -> CalibrationResult:
    repo_name = manifest["repo"].split("/")[-1]
    expected = manifest.get("expected", {})
    band = interpret_overall(overall)

    result = CalibrationResult(
        repo_name=repo_name,
        bucket=manifest.get("bucket", "unknown"),
        overall_score=overall,
        band_label=band.label,
        trust=band.trust_recommendation,
        scorecard={
            "maintainability": scorecard.maintainability,
            "reliability": scorecard.reliability,
            "security": scorecard.security,
            "testing": scorecard.testing,
            "operational_readiness": scorecard.operational_readiness,
            "developer_experience": scorecard.developer_experience,
        },
        applicable_rules=applicable,
        adapters_run=adapters,
        coverage_limits=coverage.limits[:4],
    )

    sc_map = result.scorecard
    for cat, (lo, hi) in expected.get("score_bands", {}).items():
        result.band_checks.append(BandCheck(cat, sc_map.get(cat, 0), lo, hi))

    all_rule_ids = {f.rule_id for f in findings}
    all_tags = {t for f in findings for t in f.tags}

    for mf in expected.get("must_find", []):
        if mf not in all_rule_ids and mf not in all_tags:
            result.recall_misses.append(mf)

    for mn in expected.get("must_not_find", []):
        if mn in all_rule_ids or mn in all_tags:
            result.false_positives.append(mn)

    result.top_findings = [
        f"{f.severity.upper()}: {f.rule_id}" for f in
        sorted(findings, key=lambda x: ["critical","high","medium","low","info"].index(x.severity))[:5]
    ]

    return result


def write_calibration_snapshot(result: CalibrationResult, manifest: dict, run_ts: str) -> None:
    sc = result.scorecard
    lines = [
        f"# Calibration snapshot: {result.repo_name}",
        f"Run: {run_ts}  |  Bucket: {result.bucket}  |  Overall: {result.overall_score}  |  Band: {result.band_label}",
        f"Trust: **{result.trust}**  |  Rules applicable: {result.applicable_rules}  |  Adapters: {', '.join(result.adapters_run) or 'none'}",
        "",
        "## Scorecard",
        "| Category | Score | Interpretation |",
        "|---|---|---|",
    ]
    from atlas_reviewer.scoring.interpretation import interpret_category
    for cat, score in sc.items():
        interp = interpret_category(cat, score)
        lines.append(f"| {cat.replace('_', ' ').title()} | **{score}** | {interp} |")

    lines += ["", "## Score band checks"]
    for check in result.band_checks:
        lines.append(str(check))

    lines += ["", "## Top findings"]
    for f in result.top_findings:
        lines.append(f"- {f}")

    if result.recall_misses:
        lines += ["", "## ⚠ Must-find misses"]
        for m in result.recall_misses:
            lines.append(f"- {m}")

    if result.false_positives:
        lines += ["", "## ⚠ False positives"]
        for fp in result.false_positives:
            lines.append(f"- {fp}")

    lines += ["", "## Coverage limits"]
    for lim in result.coverage_limits:
        lines.append(f"- {lim}")

    notes = manifest.get("expected", {}).get("notes", "")
    if notes:
        lines += ["", f"*Notes: {notes}*"]

    (SNAPSHOTS_DIR / f"{result.repo_name}.md").write_text("
".join(lines))


def check_rank_order(results: list[CalibrationResult]) -> list[str]:
    BUCKET_RANK = {
        "strong_python": 3, "strong_typescript": 3,
        "mixed_infra": 2,
        "tutorial_python": 1,
        "weak_python": 0, "weak_typescript": 0,
    }
    bucket_scores: dict[int, list[int]] = {}
    for r in results:
        rank = BUCKET_RANK.get(r.bucket, -1)
        if rank >= 0:
            bucket_scores.setdefault(rank, []).append(r.overall_score)

    violations = []
    rank_means = {rank: statistics.mean(scores) for rank, scores in bucket_scores.items() if scores}
    for i, hi_rank in enumerate(sorted(rank_means, reverse=True)):
        for lo_rank in list(sorted(rank_means, reverse=True))[i+1:]:
            if rank_means[hi_rank] <= rank_means[lo_rank]:
                violations.append(
                    f"Bucket rank {hi_rank} (mean={rank_means[hi_rank]:.1f}) "
                    f"≤ bucket rank {lo_rank} (mean={rank_means[lo_rank]:.1f})"
                )
    return violations


def write_master_report(results: list[CalibrationResult], run_ts: str) -> None:
    lines = [
        "# Atlas Reviewer — Calibration Report",
        f"Run: {run_ts}  |  Repos: {len(results)}  |  Ruleset: 2026.03",
        "",
        "## Score summary by repo",
        "",
        "| Repo | Bucket | Overall | Band | Trust | Bands ✓ | Recall | Precision | Status |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in results:
        if r.error:
            lines.append(f"| {r.repo_name} | {r.bucket} | — | — | — | — | — | — | ERROR |")
            continue
        bands_ok = f"{sum(1 for c in r.band_checks if c.passed)}/{len(r.band_checks)}" if r.band_checks else "n/a"
        recall_ok = "✓" if not r.recall_misses else f"✗ {len(r.recall_misses)} miss"
        prec_ok = "✓" if not r.false_positives else f"✗ {len(r.false_positives)} fp"
        status = "✓ PASS" if r.passed else "✗ FAIL"
        lines.append(f"| {r.repo_name} | {r.bucket} | {r.overall_score} | {r.band_label} | {r.trust} | {bands_ok} | {recall_ok} | {prec_ok} | {status} |")

    lines += ["", "## Category heatmap", ""]
    cats = ["security","testing","maintainability","reliability","operational_readiness","developer_experience"]
    header = "| Repo | " + " | ".join(c[:6] for c in cats) + " |"
    sep = "|---|" + "---|" * len(cats)
    lines += [header, sep]
    for r in results:
        if r.error: continue
        scores = " | ".join(str(r.scorecard.get(c, "—")) for c in cats)
        lines.append(f"| {r.repo_name} | {scores} |")

    lines += ["", "## Rank order check", ""]
    violations = check_rank_order([r for r in results if not r.error])
    if violations:
        for v in violations:
            lines.append(f"- ✗ {v}")
    else:
        lines.append("- ✓ Stronger buckets outrank weaker buckets")

    lines += ["", "---", f"*Generated by atlas_reviewer calibration runner*"]
    (SNAPSHOTS_DIR / "_calibration_report.md").write_text("
".join(lines))
    print(f"
  Master report: {SNAPSHOTS_DIR / '_calibration_report.md'}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bucket", default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--repo", default=None)
    args = parser.parse_args()

    manifests_raw = []
    for f in sorted(MANIFESTS_DIR.glob("*.json")):
        with open(f) as fh:
            m = json.load(fh)
        if args.bucket and m.get("bucket") != args.bucket:
            continue
        if args.repo and args.repo not in m["repo"]:
            continue
        manifests_raw.append(m)

    run_ts = datetime.now().strftime("%Y-%m-%d %H:%M")

    print(f"
CODEBASE ATLAS — GOLDEN BENCHMARK CALIBRATION")
    print(f"Ruleset: 2026.03  |  Repos: {len(manifests_raw)}  |  Run: {run_ts}
")
    print("=" * 70)

    if args.dry_run:
        for m in manifests_raw:
            print(f"  {m['bucket']:<28} {m['repo'].split('/')[-1]}")
        print(f"
Dry run: {len(manifests_raw)} manifests loaded. Snapshots would write to {SNAPSHOTS_DIR}")
        return

    results: list[CalibrationResult] = []

    for manifest in manifests_raw:
        repo_name = manifest["repo"].split("/")[-1]
        print(f"
► {repo_name} [{manifest['bucket']}]")
        try:
            scorecard, overall, findings, coverage, interpreted, applicable, adapters = run_engine(manifest["repo"])
            result = check_manifest(manifest, scorecard, overall, findings, coverage, interpreted, applicable, adapters)
            results.append(result)
            write_calibration_snapshot(result, manifest, run_ts)

            band = interpret_overall(overall)
            print(f"  {overall} ({band.label}) — trust: {band.trust_recommendation}")
            sc = result.scorecard
            print(f"  sec={sc['security']} test={sc['testing']} maint={sc['maintainability']} "
                  f"rel={sc['reliability']} ops={sc['operational_readiness']} devex={sc['developer_experience']}")
            print(f"  Bands: {result.band_pass_rate:.0%}  Recall: {'✓' if not result.recall_misses else '✗ '+str(result.recall_misses)}  "
                  f"Precision: {'✓' if not result.false_positives else '✗ '+str(result.false_positives)}  "
                  f"{'PASS' if result.passed else 'FAIL'}")

        except Exception as exc:
            print(f"  ERROR: {exc}")
            results.append(CalibrationResult(
                repo_name=repo_name, bucket=manifest.get("bucket","?"),
                overall_score=0, band_label="—", trust="—", scorecard={}, error=str(exc),
            ))

    print("
" + "=" * 70)
    rank_violations = check_rank_order([r for r in results if not r.error])
    if rank_violations:
        print("RANK ORDER ✗")
        for v in rank_violations: print(f"  {v}")
    else:
        print("RANK ORDER ✓  Stronger buckets outrank weaker buckets")

    passed = sum(1 for r in results if r.passed)
    errors = sum(1 for r in results if r.error)
    print(f"
Passed: {passed}/{len(results)}  Errors: {errors}")

    write_master_report(results, run_ts)

    if any(not r.passed for r in results):
        sys.exit(1)


if __name__ == "__main__":
    main()
