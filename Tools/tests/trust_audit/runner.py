"""Trust audit runner — category-aware depth scoring."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))
import argparse, tempfile, subprocess
from pathlib import Path
from datetime import datetime
from collections import Counter

from atlas_reviewer.facts.builder import build_facts
from atlas_reviewer.engine.registry import build_default_registry
from atlas_reviewer.engine.executor import execute
from atlas_reviewer.engine.dedupe import deduplicate
from atlas_reviewer.engine.coverage import build_coverage
from atlas_reviewer.engine.confidence import compute_confidence_badge
from atlas_reviewer.engine.depth import compute_depth
from atlas_reviewer.engine.anti_gaming import build_anti_gaming_block
from atlas_reviewer.engine.readiness import why_not_production_suitable, what_would_flip_verdict
from atlas_reviewer.scoring.engine import compute_scorecard, compute_overall
from atlas_reviewer.scoring.interpretation import interpret_report
from atlas_reviewer.llm.contract import build_llm_input
from atlas_reviewer.llm.summaries import _deterministic_fallback
from atlas_reviewer.models.report import ReviewReport, RepoMeta

RESULTS_DIR = Path(__file__).parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)

AUDIT_REPOS = [
    {"repo": "https://github.com/tiangolo/fastapi",                          "archetype": "strong_python",   "note": "Reference baseline"},
    {"repo": "https://github.com/encode/httpx",                              "archetype": "strong_python",   "note": "Well-typed OSS library"},
    {"repo": "https://github.com/nsidnev/fastapi-realworld-example-app",     "archetype": "tutorial_python", "note": "Teaching repo"},
    {"repo": "https://github.com/mjhea0/flaskr-tdd",                         "archetype": "tutorial_python", "note": "Tutorial with TDD framing"},
    {"repo": "https://github.com/realpython/reader",                         "archetype": "weak_python",     "note": "Simple utility"},
    {"repo": "https://github.com/t3-oss/create-t3-app",                      "archetype": "strong_ts",       "note": "Modern TS starter"},
    {"repo": "https://github.com/bradtraversy/vanillawebprojects",           "archetype": "weak_ts",         "note": "JS learning repo"},
    {"repo": "https://github.com/tiangolo/uvicorn-gunicorn-fastapi-docker",  "archetype": "mixed_infra",     "note": "Docker-heavy repo"},
]


def run_repo(repo_url: str) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        r = subprocess.run(["git","clone","--depth","1",repo_url,tmp],
                           capture_output=True, text=True, timeout=180)
        if r.returncode != 0:
            raise RuntimeError(f"Clone failed: {r.stderr[:150]}")
        commit = subprocess.run(["git","rev-parse","--short","HEAD"],
                                cwd=tmp, capture_output=True, text=True).stdout.strip()

        facts, adapter_results = build_facts(repo_url=repo_url, repo_path=tmp, commit=commit)
        registry = build_default_registry()
        applicable = registry.for_facts(facts)
        findings = deduplicate(execute(registry, facts))

        confidence = compute_confidence_badge(facts, adapter_results, len(applicable), len(registry.all()))
        depth_profile = compute_depth(adapter_results, succeeded_tools=confidence.succeeded_tools)

        scorecard = compute_scorecard(findings, depth=depth_profile.level)
        overall = compute_overall(scorecard)

        coverage = build_coverage(facts, adapter_results, tmp)
        interpreted = interpret_report(scorecard, overall, findings)
        anti_gaming = build_anti_gaming_block(findings, scorecard)
        why_not = why_not_production_suitable(scorecard, findings, overall)
        flip = what_would_flip_verdict(scorecard, findings)

        report = ReviewReport(schema_version="1.0", ruleset_version="2026.03",
                              repo=RepoMeta(url=repo_url, commit=commit,
                                            primary_languages=facts.languages.primary),
                              coverage=coverage, scorecard=scorecard)
        report.interpretation.overall_label = interpreted.overall_band.label
        report.interpretation.production_suitable = interpreted.production_suitable

        llm_input = build_llm_input(report, overall, findings,
                                    confidence_label=confidence.label,
                                    adapters_ran=confidence.adapters_ran)
        summary, trace = _deterministic_fallback(llm_input, findings)
        all_text = f"{summary.developer} {summary.manager} {summary.hiring}"
        untraced = trace.untraced_check(all_text)

        adapter_issue_count = sum(
            len(getattr(facts.tool_results, t, []))
            for t in ["ruff","bandit","gitleaks"]
        ) + sum(
            len(r.issues) for r in adapter_results.values()
            if hasattr(r, "issues") and r.status.value == "success"
        )

        return {
            "repo_url": repo_url, "commit": commit,
            "overall": overall, "band": interpreted.overall_band.label,
            "trust": interpreted.trust_recommendation,
            "production_suitable": interpreted.production_suitable,
            "depth_level": depth_profile.level.value,
            "depth_label": depth_profile.label,
            "depth_verdict_note": depth_profile.verdict_note,
            "adapters_ran": confidence.succeeded_tools,
            "adapter_issue_count": adapter_issue_count,
            "scorecard": {
                "security": scorecard.security, "testing": scorecard.testing,
                "maintainability": scorecard.maintainability, "reliability": scorecard.reliability,
                "operational_readiness": scorecard.operational_readiness,
                "developer_experience": scorecard.developer_experience,
            },
            "confidence": {"label": confidence.label, "score": confidence.score,
                           "rationale": confidence.rationale},
            "anti_gaming": {
                "verdict": anti_gaming.overall_verdict,
                "signals": [{"type": s.signal_type, "verdict": s.verdict, "conf": s.confidence}
                             for s in anti_gaming.signals],
                "summary": anti_gaming.summary,
            },
            "summary": {"developer": summary.developer, "manager": summary.manager,
                        "hiring": summary.hiring},
            "untraced_sentences": untraced,
            "why_not_production": why_not, "flip_verdict": flip,
            "top_findings": [
                {"severity": f.severity, "rule_id": f.rule_id, "title": f.title}
                for f in sorted(findings, key=lambda x: ["critical","high","medium","low","info"].index(x.severity))[:8]
            ],
            "coverage_limits": coverage.limits[:5],
        }


def write_audit_report(result: dict, entry: dict, run_ts: str) -> Path:
    repo_name = result["repo_url"].split("/")[-1]
    sc = result["scorecard"]
    ag = result["anti_gaming"]
    conf = result["confidence"]
    lines = [
        f"# Trust Audit: {repo_name}",
        f"Run: {run_ts}  |  Archetype: {entry['archetype']}  |  Commit: {result['commit']}",
        f"Note: *{entry['note']}*", "",
        "## Scores",
        f"Overall: **{result['overall']}** ({result['band']}) — Trust: **{result['trust']}** — Production: **{'Yes' if result['production_suitable'] else 'No'}**", "",
        f"**Analysis depth: {result['depth_label']}**",
        f"*{result['depth_verdict_note']}*", "",
        f"Adapters: {', '.join(result.get('adapters_ran', [])) or 'none'}  |  Issues found: {result.get('adapter_issue_count', 0)}", "",
        "| Category | Score |", "|---|---|",
    ]
    for k, v in sc.items():
        lines.append(f"| {k.replace('_',' ').title()} | {v} |")
    lines += ["", f"## Confidence: **{conf['label']}** ({conf['score']:.2f})"]
    for r in conf["rationale"]:
        lines.append(f"- {r}")
    lines += ["", "## Summaries",
              f"**Developer:** {result['summary']['developer']}",
              f"**Manager:** {result['summary']['manager']}",
              f"**Hiring:** {result['summary']['hiring']}", ""]
    untraced = result.get("untraced_sentences", [])
    lines += ["## ⚠ Untraced sentences"] + [f"- `{s}`" for s in untraced] + [""] if untraced else ["## ✓ All traceable", ""]
    lines += ["## Anti-Gaming", f"Verdict: **{ag['verdict']}**", f"> {ag['summary']}", "",
              "| Signal | Verdict | Conf |", "|---|---|---|"]
    for s in ag["signals"]:
        lines.append(f"| {s['type']} | {s['verdict']} | {s['conf']} |")
    if result.get("flip_verdict"):
        lines += ["", "## What Would Change the Verdict"]
        for i, a in enumerate(result["flip_verdict"]):
            lines.append(f"{i+1}. {a}")
    lines += ["", "## Top Findings"]
    for f in result["top_findings"]:
        lines.append(f"- [{f['severity'].upper()}] `{f['rule_id']}` — {f['title']}")
    lines += ["", "## Coverage Limits"]
    for lim in result["coverage_limits"]:
        lines.append(f"- {lim}")
    lines += ["", "---", "## Human Judgment Checklist",
              "- [ ] Depth label accurately reflects what ran",
              "- [ ] Score feels calibrated for the depth level",
              "- [ ] Anti-gaming verdict is fair",
              "- [ ] No sentence is misleading", "",
              f"*Trust audit — {run_ts}*"]
    out = RESULTS_DIR / f"{repo_name}_audit.md"
    out.write_text("\n".join(lines))
    return out


def write_summary(all_results, all_entries, run_ts):
    valid = [(r, e) for r, e in zip(all_results, all_entries) if "error" not in r]
    lines = ["# Trust Audit Summary", f"Run: {run_ts}  |  Repos: {len(all_results)}", "",
             "| Repo | Archetype | Overall | Band | Depth | Anti-Gaming | Issues | Untraced |",
             "|---|---|---|---|---|---|---|---|"]
    depth_abbr = {"structural_only":"struct","lint_augmented":"lint+","security_augmented":"sec+","full_toolchain":"full"}
    for result, entry in zip(all_results, all_entries):
        if "error" in result:
            lines.append(f"| {result['repo_url'].split('/')[-1]} | {entry['archetype']} | ERROR | — | — | — | — | — |")
            continue
        repo_name = result["repo_url"].split("/")[-1]
        uc = len(result.get("untraced_sentences", []))
        uf = f"⚠ {uc}" if uc else "✓ 0"
        d = depth_abbr.get(result.get("depth_level","?"),"?")
        lines.append(f"| {repo_name} | {entry['archetype']} | {result['overall']} | {result['band']} | {d} | {result['anti_gaming']['verdict']} | {result.get('adapter_issue_count',0)} | {uf} |")
    lines += ["", "## Score Range by Archetype", "", "| Archetype | Min | Max | Mean |", "|---|---|---|---|"]
    arch_scores: dict[str, list[int]] = {}
    for r, e in valid:
        arch_scores.setdefault(e["archetype"], []).append(r["overall"])
    for arch, scores in sorted(arch_scores.items()):
        lines.append(f"| {arch} | {min(scores)} | {max(scores)} | {sum(scores)//len(scores)} |")
    lines += ["", "## Depth Distribution", "", "| Depth Level | Count |", "|---|---|"]
    dc = Counter(r.get("depth_level","?") for r, _ in valid)
    for level, count in dc.most_common():
        lines.append(f"| {level} | {count} |")
    lines += ["", "## Human Review Queue", ""]
    for r, e in valid:
        flags = []
        if r.get("untraced_sentences"): flags.append(f"untraced ({len(r['untraced_sentences'])})")
        if r["anti_gaming"]["verdict"] == "surface_polish" and e["archetype"].startswith("strong"): flags.append("anti-gaming FP risk")
        if r["overall"] > 80 and not r["production_suitable"]: flags.append("high score/not production")
        if r.get("depth_level") in ("structural_only","lint_augmented") and r["overall"] >= 88: flags.append("high at shallow depth")
        if flags: lines.append(f"- **{r['repo_url'].split('/')[-1]}**: {', '.join(flags)}")
    (RESULTS_DIR / "_trust_audit_summary.md").write_text("\n".join(lines))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    repos = AUDIT_REPOS
    if args.repo: repos = [{"repo": args.repo, "archetype": "manual", "note": "Single"}]
    if args.limit: repos = repos[:args.limit]
    run_ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    print(f"\nCODEBASE ATLAS — TRUST AUDIT  (category-aware depth)")
    print(f"Repos: {len(repos)}  |  Run: {run_ts}\n" + "="*70)
    if args.dry_run:
        for e in repos: print(f"  {e['archetype']:<20} {e['repo'].split('/')[-1]}")
        return
    all_results, all_entries = [], []
    for entry in repos:
        repo_name = entry["repo"].split("/")[-1]
        print(f"\n► {repo_name} [{entry['archetype']}]")
        try:
            result = run_repo(entry["repo"])
            all_results.append(result)
            all_entries.append(entry)
            write_audit_report(result, entry, run_ts)
            sc = result["scorecard"]
            print(f"  {result['overall']} ({result['band']}) | depth: {result['depth_label']}")
            print(f"  adapters: {', '.join(result.get('adapters_ran',[]))+' ('+str(result.get('adapter_issue_count',0))+' issues)' or 'none'}")
            print(f"  sec={sc['security']} test={sc['testing']} maint={sc['maintainability']} rel={sc['reliability']}")
            uc = result["untraced_sentences"]
            print(f"  {result['anti_gaming']['verdict']} | untraced: {len(uc)}{'  ⚠' if uc else '  ✓'}")
        except Exception as exc:
            print(f"  ERROR: {exc}")
            all_results.append({"repo_url": entry["repo"], "error": str(exc)})
            all_entries.append(entry)
    print("\n" + "="*70)
    write_summary(all_results, all_entries, run_ts)
    print(f"Summary: {RESULTS_DIR / '_trust_audit_summary.md'}")


if __name__ == "__main__":
    main()
