# Trust Audit: fastapi
Run: 2026-03-15 17:03  |  Archetype: strong_python  |  Commit: eb6851d
Note: *Reference baseline*

## Scores
Overall: **92** (Strong) — Trust: **strong** — Production: **Yes**

**Analysis depth: Full supported toolchain**
*This verdict is backed by full structural, security, and dependency analysis.*

Adapters: ruff, bandit, pip_audit, secret_patterns  |  Issues found: 28

| Category | Score |
|---|---|
| Security | 95 |
| Testing | 100 |
| Maintainability | 80 |
| Reliability | 92 |
| Operational Readiness | 93 |
| Developer Experience | 97 |

## Confidence: **Medium** (0.60)
- 38% of repository files analyzed
- 1 of 1 detected language(s) have rule packs
- 4/4 security/quality scanners ran successfully
- Framework detection not yet run — rule packs applied heuristically

## Summaries
**Developer:** This repository has 1 high-severity finding(s) in dependencies.
**Manager:** This repository is strong with manageable technical debt. No blockers for planned delivery.
**Hiring:** This repository shows signals of solid engineering discipline across security, testing, maintainability.

## ✓ All traceable

## Anti-Gaming
Verdict: **likely_honest**
> No presentation-over-substance patterns detected. Engineering discipline signals appear genuine.

| Signal | Verdict | Conf |
|---|---|---|
| testing_discipline | present | high |
| security_hygiene | present | high |

## What Would Change the Verdict
1. Generate a lockfile: `pip freeze > requirements.txt`, `poetry lock`, or `npm ci`.

## Top Findings
- [HIGH] `DEPS-LOCKFILE-001` — No dependency lockfile found
- [MEDIUM] `OPS-ENV-001` — No .env.example file found
- [MEDIUM] `HYGIENE-LARGE-FILES-001` — Oversized source files detected

## Coverage Limits
- Runtime execution not performed
- No Dockerfile found — container security checks skipped
- Dependency vulnerabilities reflect available lockfiles only
- Generated files and vendor directories excluded from analysis

---
## Human Judgment Checklist
- [ ] Depth label accurately reflects what ran
- [ ] Score feels calibrated for the depth level
- [ ] Anti-gaming verdict is fair
- [ ] No sentence is misleading

*Trust audit — 2026-03-15 17:03*