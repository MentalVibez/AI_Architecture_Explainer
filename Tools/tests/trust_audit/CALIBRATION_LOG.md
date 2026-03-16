# Calibration Log — First Trust Audit

Run: 2026-03-15 | Environment: rule-only (no adapter tools installed)

## Results

| Repo | Archetype | Score | Band | Anti-Gaming | Confidence |
|---|---|---|---|---|---|
| fastapi | strong_python | 92 | Strong | likely_honest | Low |
| httpx | strong_python | 94 | Strong | likely_honest | Low |
| fastapi-realworld-example-app | tutorial_python | 95 | Strong | likely_honest | Medium |
| flaskr-tdd | tutorial_python | 94 | Strong | likely_honest | Low |
| reader | weak_python* | 93 | Strong | likely_honest | Low |
| create-t3-app | strong_ts | 90 | Strong | inconclusive | Low |
| vanillawebprojects | weak_ts | 85 | Solid | inconclusive | Low |
| uvicorn-gunicorn-fastapi-docker | mixed_infra | 94 | Strong | likely_honest | Low |

*reader archetype label was wrong — it has tests, CI, and type checking. Engine correctly assessed it Strong.

## Human Judgment Checklist Results

### Q1: Did the anti-gaming verdict feel fair?
- **fastapi / httpx / uvicorn**: `likely_honest` ✓ — These are genuine production repos with real engineering
- **tutorial repos**: `likely_honest` — These repos actually have tests and some CI, so verdict is defensible
- **vanillawebprojects**: `inconclusive` ✓ — Correct. Has README but no CI/tests/linter. Presentation signals present.
- **create-t3-app**: `inconclusive` — Borderline. It's a strong repo but GAMING-README-001 fired. **False positive risk.**

### Q2: Did any sentence appear technically true but rhetorically misleading?
- **reader hiring summary**: "This repository demonstrates solid engineering discipline" — TRUE and accurate
- **tutorial repos**: "This repository is strong with manageable technical debt" — MISLEADING for tutorial repos scoring 95. The word "strong" is technically derived from the score band but reads as an unqualified endorsement.
- **vanillawebprojects manager**: "No blockers for planned delivery" — POTENTIALLY MISLEADING. It has no CI, no tests.

### Q3: Can every important sentence be traced?
- ✓ 0 untraced sentences across all 8 repos after fix

### Q4: Would a hiring manager overread the anti-gaming block?
- **create-t3-app `inconclusive`**: YES — this is a well-maintained starter template being flagged. A hiring manager might dock points unfairly.
- **vanillawebprojects `inconclusive`**: NO — this is appropriate. It genuinely lacks engineering substance.

## Calibration Findings

### FINDING 1: Score compression without adapter tools (Expected)
**Severity: Expected limitation, not a bug**

All repos cluster 85-95 in rule-only mode. Without ruff/bandit/gitleaks:
- Cannot detect actual code quality issues
- Cannot detect security vulnerabilities
- Cannot detect type safety gaps

The engine is HONEST about this — confidence badge shows Low with explicit "No static analysis tools installed" note.

**Action**: Document that adapter tools (ruff, bandit, gitleaks) are required for meaningful score separation in the middle tier. Rule-only mode is only reliable for clear structural signals.

### FINDING 2: Tutorial repos score the same as strong repos (Bug in middle tier)
**Severity: Medium — affects product credibility**

`fastapi-realworld-example-app` (tutorial) and `fastapi` (production OSS) both score 94-95. A hiring manager would not see a meaningful difference.

Root cause: tutorial repos often have enough structural hygiene (README, LICENSE, some tests, some CI) that rule-only analysis can't distinguish them from production repos.

**Action**: Two options:
1. Install adapter tools in the review environment (ruff, bandit — these are the real differentiator)
2. Add a "complexity signal" rule that rewards repos with meaningful test coverage *relative to source size*, not just test file presence

### FINDING 3: "reader" archetype label was wrong (Test fixture bug)
**Severity: Low — engine behavior is correct**

reader has tests, CI, README, license, type checker. It's not a "weak" repo.
The engine correctly scored it Strong.

**Action**: Update audit repo list with correct archetype. Add to `notes` field. Good example of engine catching a human assumption error.

### FINDING 4: create-t3-app anti-gaming false positive (Calibration needed)
**Severity: Medium — affects hiring manager trust**

create-t3-app is a well-maintained TS starter template. It got `inconclusive` because GAMING-README-001 fired.

Root cause: GAMING-README-001 fires when README is present but hard signals are below threshold. create-t3-app has tests and CI but GAMING-README-001 may be evaluating the wrong combination.

**Action**: Tighten GAMING-README-001 applicability. Should require at least 2 of 4 hard signals absent before firing. Currently fires with just linter missing.

### FINDING 5: "No blockers for planned delivery" on untested repos (Rhetoric gap)
**Severity: Medium — affects manager trust**

When `production_suitable=True`, the manager summary says "No blockers for planned delivery."
vanillawebprojects has no CI and no tests but still scores above the production gate (85).

Root cause: production_suitable gate checks `security >= 65` and `testing >= 50`. vanillawebprojects hits both (testing=80 because no test files means the test rules fire but don't tank the score enough with only rule-only signal).

**Action**: Tighten production_suitable gate: require `has_ci=True` as a third condition, or raise testing threshold to 65.

## Required Actions Before Next Audit Run

Priority 1 (blocks credibility):
- [ ] Install adapter tools: `pip install ruff bandit` in review environment
- [ ] Tighten GAMING-README-001 applicability threshold
- [ ] Tighten production_suitable gate — add CI check

Priority 2 (improves accuracy):
- [ ] Update reader archetype to `strong_python` in audit repos
- [ ] Add hollow-test-suite rule sensitivity for repos with tests/ but low LOC

Priority 3 (improves confidence badge):
- [x] Fix framework_confidence default from 0.0 to 0.5 when Atlas not integrated
