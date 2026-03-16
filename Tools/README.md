# Codebase Atlas — Review Engine

> Tool 03 in the RepoScout → Atlas → Review → Map pipeline.

Evidence-backed repository review: deterministic rules, tool adapters, architecture heuristics.

## Design law

**Facts are centralized. Rules are tiny. Findings are normalized.**

## Quick start

```bash
pip install -e ".[dev]"
uvicorn atlas_reviewer.main:app --reload
# POST /review/ with { "repo_url": "https://github.com/org/repo" }
```

## Adding a rule

1. Create `rules/<ecosystem>/your_rule.py` extending `Rule`
2. Implement `applies(facts)` — return False to skip for irrelevant repos
3. Implement `evaluate(facts)` — return `[]` or `[Finding(...)]`
4. Register in `engine/registry.py` → `build_default_registry()`
5. Write a unit test in `tests/unit/`

A new rule is 30–60 lines. It does not touch the filesystem.

## Architecture

```
facts/          Central fact store — populated once, read-only during evaluation
  collectors/   repo_structure, manifests, tooling, metrics
rules/          Rule classes — common, python, typescript, docker, frameworks/
engine/         registry, executor, dedupe
scoring/        Weighted category scores with diminishing returns
adapters/       Ruff, Bandit, ESLint, Gitleaks — normalized to ToolIssue (TODO)
exports/        JSON + Markdown report generation
llm/            Summary + remediation (calls Anthropic API post-scoring only)
```

## Ruleset versioning

Every report includes `ruleset_version`. Score changes between versions are attributable.
If a user asks "why did this score change?", you have an answer.
