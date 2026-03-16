# Trust Audit: create-t3-app
Run: 2026-03-15 17:03  |  Archetype: strong_ts  |  Commit: 4709861
Note: *Modern TS starter*

## Scores
Overall: **89** (Solid) — Trust: **solid** — Production: **Yes**

**Analysis depth: Structural + lint + security**
*This verdict includes security scanning. Dependency vulnerability assessment was not performed.*

Adapters: secret_patterns  |  Issues found: 2

| Category | Score |
|---|---|
| Security | 97 |
| Testing | 80 |
| Maintainability | 83 |
| Reliability | 89 |
| Operational Readiness | 100 |
| Developer Experience | 90 |

## Confidence: **Medium** (0.58)
- 33% of repository files analyzed
- 2 of 2 detected language(s) have rule packs
- 1/1 security/quality scanners ran successfully
- Framework detection not yet run — rule packs applied heuristically

## Summaries
**Developer:** This repository has 1 high-severity finding(s) in testing.
**Manager:** This repository is solid with manageable technical debt. No blockers for planned delivery.
**Hiring:** This repository shows signals of solid engineering discipline across security, testing, maintainability.

## ✓ All traceable

## Anti-Gaming
Verdict: **inconclusive**
> Mixed signals. Some presentation patterns detected alongside real engineering gaps. Not conclusive — recommend probing for depth in interview.

| Signal | Verdict | Conf |
|---|---|---|
| facade_risk | present | low |
| testing_discipline | present | high |
| security_hygiene | present | high |

## What Would Change the Verdict
1. Add a tests/ directory. Start with unit tests on core business logic.

## Top Findings
- [HIGH] `TESTING-001` — No test files detected
- [MEDIUM] `HYGIENE-LARGE-FILES-001` — Oversized source files detected
- [MEDIUM] `DX-LINT-001` — No linter configuration found
- [MEDIUM] `GAMING-FACADE-001` — Surface polish without production discipline detected
- [LOW] `DX-FORMAT-001` — No code formatter configuration found

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