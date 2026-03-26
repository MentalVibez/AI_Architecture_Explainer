# Codebase Atlas — Intelligence Pipeline Architecture

## Pipeline Sequence (Non-Negotiable)

```
Ingest → Extract → DeepScan → RepoGraph → Review → Explain → Optimize
```

Each stage consumes the output of the previous stage.
No stage skips ahead. No stage inverts this order.

---

## Stage Responsibilities

### Stage 1: Ingest
**Existing service:** `app/services/github_fetcher.py`

What it does:
- Accepts repo URL
- Authenticates with GitHub API
- Fetches the full file tree (all paths + sizes)
- Does NOT fetch file contents here

Output: `List[Dict]` — raw GitHub tree items

---

### Stage 2: Extract (NEW — DeepScanner)
**New service:** `app/services/deep_scanner.py`

What it does:
- Receives the file tree
- Prioritizes files for scanning (entrypoints first, tests last)
- Fetches file contents concurrently (bounded semaphore)
- Runs language detection (deterministic)
- Runs per-language parsers (imports, exports, functions, classes)
- Detects sensitive patterns
- Computes complexity signals
- Builds FileIntelligence per file
- Builds CodeContext graph (who calls whom)
- Produces ScanMetadata (how complete was the scan)

Output: `DeepScanResult` → `List[FileIntelligence]`, `Dict[str, CodeContext]`, `ScanMetadata`

**LLM involvement: ZERO**

---

### Stage 3: RepoGraph (UPDATE existing)
**Existing service:** `app/services/analysis_pipeline.py` (needs update)

What it does now:
- Consumes `DeepScanResult`
- Builds the architecture graph (component nodes, edges)
- Identifies service boundaries
- Determines primary framework
- Traces entrypoint → call chains

Current Atlas does this from manifests only.
After this update: it consumes `FileIntelligence` objects for richer signal.

Output: `RepoGraph` object (architecture component model)

**LLM involvement: ZERO** (graph construction is deterministic)

---

### Stage 4: Review (NEW — ContextReviewer)
**New service:** `app/services/context_reviewer.py`

What it does:
- Phase 1 (deterministic): Runs known-pattern detectors against each file's sensitive operations. Produces `CodeFinding` objects with full evidence. No LLM.
- Phase 2 (conditional LLM): For high-risk / critical-path files, calls Claude with `FileIntelligence + CodeContext + repo_summary` as structured input. LLM returns `List[CodeFinding]` — validated against schema before acceptance.

LLM invocation criteria (targeted, not exhaustive):
- File is on critical path, OR
- File has LOC ≥ 50 AND has sensitive operations, OR
- File has cyclomatic complexity ≥ 15, OR
- File has 3+ callers (high blast radius)

LLM is NOT invoked for: tests, configs, migrations, infra files

Output: `List[CodeFinding]`

**LLM involvement: CONDITIONAL** — advisory only, evidence-mandatory

---

### Stage 5: Explain (UPDATE existing)
**Existing service:** `app/services/summary_service.py` (update prompt)

What it does:
- Consumes `RepoGraph` + `List[CodeFinding]` + `ScanMetadata`
- Generates developer summary (technical)
- Generates non-technical summary
- Generates architecture explanation that references actual findings
- Generates Mermaid diagram (color-coded by finding severity)

The summary now reflects what the code *actually does* (from DeepScan evidence),
not just what the README says.

Output: Structured summaries + Mermaid diagram

**LLM involvement: YES** — summaries are the appropriate LLM task

---

### Stage 6: Scorecard (NEW — Scorecard Engine)
**New service:** `app/services/scorecard.py`

What it does:
- Consumes `List[CodeFinding]` + `List[FileIntelligence]` + `ScanMetadata`
- Scores: security, performance, reliability, maintainability, test_coverage, documentation
- Applies confidence weighting (partial scans = honest scores)
- Produces `ProductionScore` with per-dimension breakdown

Output: `ProductionScore`

**LLM involvement: ZERO**

---

### Stage 7: Optimize (NEW)
**New service:** `app/services/optimizer.py` (not yet built)

What it does:
- Consumes `List[CodeFinding]`
- Groups findings by type
- Presents candidates to user for approval (UI gate)
- For approved candidates: calls LLM with narrow patch prompt
- Produces `List[OptimizationCandidate]` with unified diffs

Rules:
- No full-file rewrites
- No repo-wide refactors
- Targeted patches only
- Every patch tied to a specific CodeFinding

Output: `List[OptimizationCandidate]` — all require `is_approved = True` before being applied

**LLM involvement: YES** — patch generation, constrained to specific finding scope

---

## Schema Data Flow

```
GitHubTree
    ↓
FileIntelligence (one per file)
    ↓
CodeContext (relationship graph, one per file)
    ↓
RepoGraph (architecture view)
    ↓
CodeFinding (one per issue, evidence-mandatory)
    ↓
ProductionScore (per-dimension, confidence-weighted)
    ↓
OptimizationCandidate (user-approved patches)
```

---

## Integration Into Existing Codebase

### Where to add DeepScanner

In `app/api/routes/analyze.py` (or wherever the analysis job is dispatched):

```python
# Existing flow:
tree = await github_fetcher.get_tree(owner, repo)
analysis = await analysis_pipeline.run(tree)

# Updated flow:
tree = await github_fetcher.get_tree(owner, repo)
scan_result = await deep_scanner.scan(owner, repo, tree)   # NEW
analysis = await analysis_pipeline.run(tree, scan_result)  # pass scan_result in
findings = await context_reviewer.review_repo(...)         # NEW
score = build_scorecard(findings, scan_result.files, scan_result.scan_metadata)  # NEW
```

### Database changes needed (Alembic migration)

New tables:
- `file_intelligence` — stores FileIntelligence per file per job
- `code_findings` — stores CodeFinding per finding per job
- `optimization_candidates` — stores candidates + approval state
- `production_scores` — stores ProductionScore per job

Existing tables remain unchanged. This is purely additive.

---

## Confidence System

Every score has an associated confidence value:

```
confidence = f(scan_coverage, parse_success_rate, test_presence, entrypoint_coverage)
```

When confidence < 0.65:
- Scores are blended toward neutral (50)
- UI displays: "⚠️ Partial scan — results are directional"
- User can request a deeper scan

When confidence ≥ 0.85:
- Scores are shown as-is
- UI displays: "✓ High confidence"

---

## LLM Boundary Summary

| Stage | LLM Used? | Role |
|-------|-----------|------|
| Ingest | No | — |
| DeepScan | No | — |
| RepoGraph | No | — |
| Review (Phase 1) | No | Deterministic patterns |
| Review (Phase 2) | Conditional | Evidence-mandatory findings |
| Explain | Yes | Summaries from structured evidence |
| Scorecard | No | — |
| Optimize | Yes | Targeted patches, user-approved |

**The LLM never produces scores, never constructs graphs, and never invents findings without evidence.**

---

## Next Build Steps

1. ✅ Schemas locked (`schemas/intelligence.py`)
2. ✅ DeepScanner implemented (`services/deep_scanner.py`)
3. ✅ ContextReviewer implemented (`services/context_reviewer.py`)
4. ✅ Scorecard engine implemented (`services/scorecard.py`)
5. ✅ Test suite written (`tests/test_deep_scanner.py`)
6. ⬜ Wire DeepScanner output into existing `analysis_pipeline.py`
7. ⬜ Alembic migration for new tables
8. ⬜ API routes for findings + scorecard
9. ⬜ Optimizer service (`services/optimizer.py`)
10. ⬜ Frontend: findings panel, scorecard UI, before/after diff view
