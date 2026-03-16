# Trust Audit: vanillawebprojects
Run: 2026-03-15 17:03  |  Archetype: weak_ts  |  Commit: adc66a1
Note: *JS learning repo*

## Scores
Overall: **85** (Solid) — Trust: **solid** — Production: **Yes**

**Analysis depth: Structural + lint + security**
*This verdict includes security scanning. Dependency vulnerability assessment was not performed.*

Adapters: secret_patterns  |  Issues found: 0

| Category | Score |
|---|---|
| Security | 97 |
| Testing | 80 |
| Maintainability | 77 |
| Reliability | 80 |
| Operational Readiness | 90 |
| Developer Experience | 89 |

## Confidence: **Medium** (0.54)
- 16% of repository files analyzed
- 1 of 1 detected language(s) have rule packs
- 1/1 security/quality scanners ran successfully
- Framework detection not yet run — rule packs applied heuristically

## Summaries
**Developer:** This repository has 2 high-severity finding(s) in testing, hygiene.
**Manager:** This repository is solid with manageable technical debt. No blockers for planned delivery.
**Hiring:** This repository shows signals of solid engineering discipline across security, testing, maintainability.

## ✓ All traceable

## Anti-Gaming
Verdict: **inconclusive**
> Mixed signals. Some presentation patterns detected alongside real engineering gaps. Not conclusive — recommend probing for depth in interview.

| Signal | Verdict | Conf |
|---|---|---|
| readme_theater | present | low |
| testing_discipline | present | high |
| security_hygiene | present | high |

## What Would Change the Verdict
1. Add a GitHub Actions workflow with at minimum: lint, test, and type-check steps.
2. Add a tests/ directory. Start with unit tests on core business logic.

## Top Findings
- [HIGH] `HYGIENE-CI-001` — No CI pipeline detected
- [HIGH] `TESTING-001` — No test files detected
- [MEDIUM] `HYGIENE-LICENSE-001` — Repository is missing a LICENSE file
- [MEDIUM] `HYGIENE-LARGE-FILES-001` — Oversized source files detected
- [MEDIUM] `DX-LINT-001` — No linter configuration found
- [LOW] `DX-FORMAT-001` — No code formatter configuration found
- [LOW] `GAMING-README-001` — README present but engineering substance is missing

## Coverage Limits
- Runtime execution not performed
- No Dockerfile found — container security checks skipped
- No GitHub Actions workflows found — CI hygiene checks limited
- Dependency vulnerabilities reflect available lockfiles only
- Generated files and vendor directories excluded from analysis

---
## Human Judgment Checklist
- [ ] Depth label accurately reflects what ran
- [ ] Score feels calibrated for the depth level
- [ ] Anti-gaming verdict is fair
- [ ] No sentence is misleading

*Trust audit — 2026-03-15 17:03*