# Codebase Atlas — Review Compatibility Shell

> Tool 03 in the RepoScout → Atlas → Review → Map pipeline.

Thin standalone shell for the canonical backend reviewer.

The real reviewer implementation now lives in:
`backend/app/services/reviewer/`

## Design law

**Facts are centralized. Rules are tiny. Findings are normalized.**

## Quick start

```bash
pip install -e ".[dev]"
uvicorn Tools.main:app --reload
# POST /review/ with { "repo_url": "https://github.com/org/repo" }
```

## Architecture note

`Tools/` exists for compatibility and local experimentation.
Reviewer logic should be added in the backend package, not duplicated here.

## Ruleset versioning

Every report includes `ruleset_version`. Score changes between versions are attributable.
If a user asks "why did this score change?", you have an answer.
