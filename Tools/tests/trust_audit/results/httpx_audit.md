# Trust Audit: httpx
Run: 2026-03-15 17:03  |  Archetype: strong_python  |  Commit: b5addb6
Note: *Well-typed OSS library*

## Scores
Overall: **94** (Strong) — Trust: **strong** — Production: **Yes**

**Analysis depth: Full supported toolchain**
*This verdict is backed by full structural, security, and dependency analysis.*

Adapters: ruff, bandit, pip_audit, secret_patterns  |  Issues found: 2

| Category | Score |
|---|---|
| Security | 100 |
| Testing | 100 |
| Maintainability | 75 |
| Reliability | 98 |
| Operational Readiness | 100 |
| Developer Experience | 98 |

## Confidence: **Medium** (0.62)
- 48% of repository files analyzed
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
- [MEDIUM] `ARCH-BOUNDARY-001` — Route handlers importing database session directly
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