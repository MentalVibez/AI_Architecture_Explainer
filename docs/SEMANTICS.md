# Codebase Atlas — Frozen Semantics

**Version:** 1.1.0  
**Status:** Locked. Changes require explicit version bump and test suite update.

This document defines the invariants the system must always satisfy.
If a test contradicts this document, the test is wrong.
If the implementation contradicts this document, the implementation is wrong.

---

## 1. Critical Path Depth Rule

**Rule:** A file is on the critical path if and only if it is reachable from an
entrypoint via confirmed dependency edges within **shortest-path depth** 0, 1, or 2.

**Depth definition:**
- Depth 0 — the entrypoint file itself
- Depth 1 — files directly imported by the entrypoint
- Depth 2 — files imported by depth-1 files

**Cap:** Depth > 2 is never marked critical.

**Traversal algorithm: BFS (breadth-first search).**
BFS guarantees that every file's critical-path depth is its shortest-path
distance from any entrypoint. This means:
- A file reachable in 2 hops is always marked critical
- A file reachable in both 2 hops and 4 hops is marked critical (2 wins)
- Traversal order never affects which files are marked critical

This replaced an earlier DFS implementation that had an ordering artifact: if
node B was reachable via A→C→B (depth 2) and also via A→B (depth 1), DFS might
process it at depth 2 first, causing B's children to appear at depth 3 and be
incorrectly blocked. BFS eliminates this class of bug entirely.

**Multiple entrypoints:** Each entrypoint runs its own BFS. A file marked
critical by any entrypoint retains that status. A shared `visited` set is NOT
used across entrypoints — each BFS is independent so every entrypoint
contributes its own reach.

**Invariant tests must verify:**
- depth-0 files: always critical (linear chain)
- depth-1 files: always critical (linear chain)
- depth-2 files: always critical (linear chain, no DFS artifact)
- depth-3 files: never critical (linear chain)
- depth-4+ files: never critical

---

## 2. Lock File Rule

**Decision:** Lock files are handled by `is_generated()`, not `should_skip()`.

**Rationale:** Atlas is a repo intelligence tool. The distinction matters:
- `should_skip()` — binary/compiled assets and vendor directories. Never fetched.
  These contain no text signal at all.
- `is_generated()` — lockfiles, minified output, `.d.ts` declarations, proto
  generated files. These are text but carry no source intelligence. They are
  excluded from deep analysis but ARE visible in the file inventory for repo
  composition stats (e.g. "this repo uses npm" is inferred from the presence
  of `package-lock.json` in the tree, even if it is never parsed).

**`should_skip()` covers:** binary extensions, vendor/dependency directories  
**`is_generated()` covers:** lock files, minified JS/CSS, `.d.ts`, proto output,
build artifacts

**Invariant:** `should_skip("package-lock.json")` must return `False`.
`is_generated("package-lock.json")` must return `True`.

**Scan loop behavior:** The scanner applies BOTH checks:
```python
if should_skip(path) or is_generated(path):
    continue  # skip from deep analysis
```
Lock files are excluded from parsing but counted in `files_skipped` for
honest reporting.

---

## 3. Confirmed vs Unresolved Edge Rule

**Rule:** If a file's path is in `known_paths` (the set of all files in the
scan batch), any import that resolves to that path produces a `confirmed` edge,
regardless of that file's `FileIntelligence.confidence` score.

**Rationale:** Edge confidence and file parse confidence are independent:
- Edge confidence: can we trace which file is being imported? (graph topology)
- File confidence: did we successfully parse that file's internals?

A confirmed edge to a zero-confidence file means: "we know this file is
imported, but we couldn't parse it." This is more informative than an unresolved
edge, which means "we found an import but don't know what it refers to."

**How to detect fetch-failed targets:** Check the target's `FileIntelligence`:
```python
target_fi = file_map.get(edge.target_path)
if target_fi and target_fi.confidence == 0.0:
    # file exists but failed to parse
```

**Invariant:** `edge.confidence == "confirmed"` requires only that
`edge.target_path in known_paths`. It does not require `target.confidence > 0`.

**Unresolved edge:** Produced when an import string cannot be resolved to any
path in `known_paths` AND is not recognized as an external package.

**External package:** Recognized by root prefix matching against `EXTERNAL_PREFIXES`.
External packages produce no edge at all — they are silently dropped.
They never count against `graph_confidence`.

---

## 4. Confidence Ceiling Rule

**Rule:** `ConfidenceBreakdown.score_confidence` is capped at `0.97`.

**Rationale:** Static analysis of a codebase can never be certain. Files may
be generated, conditionally executed, dynamically imported, or use patterns
the parser does not recognize. A score of `1.0` would imply complete knowledge,
which is never warranted.

**Formula:**
```
score_confidence = min(0.97, 
    extraction_confidence × 0.40 +
    graph_confidence      × 0.35 +
    finding_confidence    × 0.25
)
```

**Labels:**
- `>= 0.85` → HIGH
- `>= 0.65` → MODERATE  
- `< 0.65`  → LOW

**Invariant:** `score_confidence` never exceeds `0.97` for any input.

---

## 5. Graph Confidence Rule

**Rule:** `graph_confidence` is the fraction of internal (non-external) imports
that resolved to confirmed edges.

```
graph_confidence = confirmed_internal_imports / total_internal_imports
```

**External imports are excluded from the denominator.** An import of `fastapi`,
`react`, or `urllib.parse` that goes unresolved does not count against
graph confidence. Only imports that appear to reference internal repo files
but couldn't be resolved count against it.

**If total_internal_imports == 0:** graph_confidence = 0.5 (neutral — no signal
either way).

**Invariant:** A repo with only external imports and no internal cross-file
dependencies produces `graph_confidence == 0.5`, not `0.0`.

---

## 6. Schema Version Rule

**Rule:** `RepoIntelligence.schema_version` is set to `SCHEMA_VERSION` from
`schemas/intelligence.py`. Current value: `1.1.0`.

**Bump required when:**
- Any field is added, removed, or renamed in `FileIntelligence`, `CodeContext`,
  `DependencyEdge`, `CodeFinding`, `OptimizationCandidate`, or `RepoIntelligence`
- Any Literal type is extended or narrowed
- Any validator behavior changes

**Bump not required for:**
- Adding items to `EXTERNAL_PREFIXES`
- Adding new language parsers
- Adjusting score weights within declared bounds
- Bug fixes that don't change the schema contract

---

## 7. LLM Boundary Rule

**Rule:** The LLM is never invoked inside DeepScanner. It may only be invoked
in ContextReviewer (conditional, evidence-gated) and ExplainService (summaries).

**LLM may NOT:**
- Produce `FileIntelligence` objects
- Produce `DependencyEdge` objects
- Set `is_on_critical_path`
- Assign `graph_confidence` or `score_confidence`
- Produce findings without `line_start`, `line_end`, and `evidence_snippet`

**LLM MAY:**
- Produce `CodeFinding` objects with full evidence (ContextReviewer)
- Produce natural language summaries from structured evidence (ExplainService)
- Produce `OptimizationCandidate` patches for user-approved findings (Optimizer)

**Invariant:** Every `CodeFinding` must have non-empty `evidence_snippet`,
valid `line_start >= 1`, and `line_end >= line_start`. The schema validator
enforces this — it cannot be bypassed.

---

## 8. Scoring Rule

**Rule:** Score deductions come only from:
1. Proven `CodeFinding` objects (each finding's `score_impact` field)
2. Explicit missing-artifact penalties (no test files detected, no README)
3. Confidence adjustment blending toward neutral (50)

**Score deductions may NOT come from:**
- LLM opinion without evidence
- Absence of features not in scope
- Comparison to external benchmarks
- Any inference not traceable to a file or finding

**Invariant:** `sum(f.score_impact for f in findings)` accounts for all
deductions from the BASE_SCORE (100). No other deduction path exists.
