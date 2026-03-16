# Calibration Notes — Trust Audit 2026-03-15

## Run conditions
- Environment: no static analysis tools installed (ruff, bandit, gitleaks unavailable)
- Analysis mode: rule-only
- Confidence badge: Low for all repos (expected)

## Key findings

### Score compression in rule-only mode
Without adapter tools, most repos with basic hygiene score 88-95/Strong.
The engine correctly identifies *absence* of basics (no tests, no CI) but cannot 
differentiate *depth* of engineering (test coverage, security scan clean, lint density).

This is honest — the confidence badge Low correctly signals limited signal.
When adapters are available, the scoring model will have more differentiation capacity.

### Tutorial repos scoring same as strong repos
fastapi-realworld-example-app: 95/Strong
flaskr-tdd: 94/Strong

Expected — both have basic hygiene signals that satisfy binary rules.
The distinction will appear when ruff reveals lint density and bandit finds security gaps.

### Anti-gaming working correctly
create-t3-app (strong_ts): inconclusive — no tests despite strong structure. Correct.
vanillawebprojects (weak_ts): inconclusive — readme theater without engineering depth. Correct.
Strong Python repos: likely_honest. Correct.

### Hiring summary calibrated correctly
Low confidence now produces: "Structural signals suggest basic engineering hygiene in place."
High/Medium confidence produces: "demonstrates solid engineering discipline..."
This prevents the system from overclaiming when adapter data is absent.

### All 8 repos: 0 untraced sentences after trace alignment fix.

## Next calibration actions
1. Run full audit with ruff + bandit installed — expect tutorial/weak repos to drop 10-20 points
2. Add tests for confidence-calibrated hiring summary language
3. Monitor hollow test detection threshold adjustment on real repos
4. Consider template/starter repo detection for anti-gaming block context
