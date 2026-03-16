# Trust Audit: flaskr-tdd
Run: 2026-03-15 17:03  |  Archetype: tutorial_python  |  Commit: 305122f
Note: *Tutorial with TDD framing*

## Scores
Overall: **92** (Strong) — Trust: **strong** — Production: **Yes**

**Analysis depth: Full supported toolchain**
*This verdict is backed by full structural, security, and dependency analysis.*

Adapters: ruff, bandit, pip_audit, secret_patterns  |  Issues found: 36

| Category | Score |
|---|---|
| Security | 93 |
| Testing | 100 |
| Maintainability | 77 |
| Reliability | 97 |
| Operational Readiness | 100 |
| Developer Experience | 94 |

## Confidence: **Medium** (0.58)
- 30% of repository files analyzed
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
- [MEDIUM] `PY-TYPING-001` — Type checking not enforced
- [MEDIUM] `SEC-BANDIT-GROUPED-001` — Security hygiene issues detected
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