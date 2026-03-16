# Trust Audit: fastapi-realworld-example-app
Run: 2026-03-15 17:03  |  Archetype: tutorial_python  |  Commit: 029eb77
Note: *Teaching repo*

## Scores
Overall: **95** (Strong) — Trust: **strong** — Production: **Yes**

**Analysis depth: Full supported toolchain**
*This verdict is backed by full structural, security, and dependency analysis.*

Adapters: ruff, bandit, pip_audit, secret_patterns  |  Issues found: 40

| Category | Score |
|---|---|
| Security | 95 |
| Testing | 100 |
| Maintainability | 83 |
| Reliability | 100 |
| Operational Readiness | 100 |
| Developer Experience | 96 |

## Confidence: **Medium** (0.69)
- 76% of repository files analyzed
- 1 of 1 detected language(s) have rule packs
- 4/4 security/quality scanners ran successfully
- Framework detection not yet run — rule packs applied heuristically

## Summaries
**Developer:** This repository is strong with no critical issues detected.
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

## Top Findings
- [MEDIUM] `HYGIENE-LARGE-FILES-001` — Oversized source files detected
- [MEDIUM] `DX-LINT-001` — No linter configuration found
- [MEDIUM] `DOCKER-SEC-001` — Dockerfile runs as root

## Coverage Limits
- Runtime execution not performed
- Dependency vulnerabilities reflect available lockfiles only
- Generated files and vendor directories excluded from analysis

---
## Human Judgment Checklist
- [ ] Depth label accurately reflects what ran
- [ ] Score feels calibrated for the depth level
- [ ] Anti-gaming verdict is fair
- [ ] No sentence is misleading

*Trust audit — 2026-03-15 17:03*