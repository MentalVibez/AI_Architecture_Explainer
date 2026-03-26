# Codebase Atlas — Import Resolution Limitations

**Version:** 1.1.0  
**Last updated:** 2026-03  
**Status:** Living document. Add entries when new gaps are discovered.
**Rule:** Every entry here has a corresponding test that proves the limitation
exists, and an unresolved edge reason code that appears in the graph output.

---

## How to read this document

Each limitation has:

- **What fails** — the exact pattern that doesn't resolve
- **Why** — the root cause at the parser or resolver level
- **Confidence impact** — how this affects `graph_confidence`
- **Unresolved reason code** — the `UnresolvedReason` value emitted in the edge
- **Test coverage** — which test(s) prove this behavior
- **Workaround / upgrade path** — what would fix it

---

## L-001: `from package import module` — package-directory ambiguity

**Status: PARTIALLY FIXED in v1.1.0**

**What now works:**
```python
# If the package path ends with a known directory signal word
# (routes, services, models, handlers, etc.), the resolver now
# also tries 'package.name' for each imported lowercase name:
from app.api.routes import analyze, health
# → emits 'app.api.routes.analyze' AND 'app.api.routes.health' as candidates
# → both resolve to routes/analyze.py and routes/health.py
# → confirmed edges produced ✓
```

**What still fails:**
```python
# If the package path does NOT end with a signal word:
from app.utils import helpers    # 'utils' IS a signal word → works
from app.core import database    # 'core' is NOT a signal word → still fails
from myapp import main           # 'myapp' is NOT a signal word → still fails
```

**Why partially fixed:** The fix relies on a heuristic — the last component of
the module path matching a set of known package-directory names. This covers
the majority of real-world cases (routes, services, models, handlers) but
misses arbitrary package names.

**Residual confidence impact:** The base module path (`app.api.routes`) still
emits an unresolved edge alongside the resolved submodule edges. This produces
one unresolved edge per `from pkg import ...` statement even when all imported
names resolve. gc is therefore slightly below 1.0 for repos that use this pattern.

**Upgrade path to full fix:** Change `ParseResult.imports` from `List[str]` to
`List[ImportStatement(module, names)]`. The resolver then always has the full
information without needing heuristics. Tracked for v1.2.0.

**Unresolved reason code:** `ambiguous_package_import` (for the base path edge)

---

## L-002: `import module as alias` — aliased module imports

**What fails:**
```python
import numpy as np          # np is used, but numpy is external — fine (excluded)
import app.utils as utils   # utils is used — fails if utils.py exists
```

**What resolves:**
```python
import app.utils            # resolves to app/utils.py
from app import utils       # resolves to app/utils.py
```

**Why:** The parser regex `r'^import\s+([\w., ]+)'` captures the module name
before any `as` clause. For `import app.utils as utils`, the captured string is
`app.utils` (correct). For `import numpy as np`, it's `numpy` (correct, excluded
as external). This case is actually handled — **L-002 is lower priority** than
L-001 and may not manifest in most repos.

**Confidence impact:** Minimal in practice. Most `import X as alias` patterns
use external packages or the standard library, both of which are excluded from
confidence calculation.

**Unresolved reason code:** `parse_ambiguity` (if it does fail)

**Test coverage:** `test_deep_scanner.py::TestLanguageDetection` — no specific
regression test yet. Add if a real-world repo exposes this.

**Upgrade path:** Extend the import regex to capture the pre-`as` token only.
Current regex already does this for most cases; verify edge cases.

---

## L-003: Dynamic imports — runtime path construction

**What fails:**
```python
# Python
module = importlib.import_module(f"app.plugins.{plugin_name}")
module = __import__(f"handlers.{handler_type}")

# TypeScript
const mod = await import(`./handlers/${handlerType}`);
const { default: Component } = await import(`@/components/${name}`);
```

**Why:** Dynamic import paths contain runtime variables. Static analysis cannot
determine the value of `plugin_name`, `handlerType`, or `name` at parse time.
There is no static resolution possible.

**Confidence impact:** These appear as `dynamic_import` unresolved edges. They
do NOT count against `graph_confidence` — the system recognizes them as
structurally unresolvable, not as resolution failures.

**Unresolved reason code:** `dynamic_import`

**Test coverage:** No specific test yet. Dynamic imports produce unresolved edges
with `dynamic_import` reason — verify this in invariants.

**Upgrade path:** None for full resolution. Partial: detect common patterns like
`import_module("app.plugins." + X)` and emit a heuristic edge to the directory.
Mark heuristic edges with `confidence="inferred"` rather than `"confirmed"`.

---

## L-004: TypeScript path aliases not in tsconfig

**What fails:**
```typescript
// tsconfig.json has: "@app/*": ["./src/app/*"]
// But Atlas only knows about Next.js defaults: "@/": "src/"
import { thing } from "@app/utils";  // ← alias not in default set, unresolved
```

**Why:** `_extract_ts_aliases()` returns hardcoded Next.js-convention defaults.
Non-standard aliases that are declared in `tsconfig.json` but not in the default
set are not applied.

**Confidence impact:** Each non-default alias import counts against
`graph_confidence` as unresolved.

**Unresolved reason code:** `alias_unknown`

**Test coverage:** Not currently covered. Add a fixture for non-standard aliases.

**Upgrade path (near-term):** During the DeepScan phase, detect `tsconfig.json`
in the file tree and parse its `compilerOptions.paths` to extract actual aliases.
This would be done by `GitHubContentFetcher` fetching `tsconfig.json` early
(it's in the entrypoint priority tier).

**Upgrade path (implemented in):** `deep_scanner.py::_extract_ts_aliases()` is
already a stub designed to be replaced. The function signature takes
`List[FileIntelligence]` — when tsconfig content is stored in `DeepScanResult`,
the full alias map can be passed through.

---

## L-005: Namespace packages (PEP 420) — no `__init__.py`

**What fails:**
```
# Modern Python namespace packages (no __init__.py):
myorg/
    shared/         ← no __init__.py
        models.py
        auth.py

# Import in app/main.py:
from myorg.shared import models  # ← L-001 + no __init__.py
from myorg.shared.models import User  # ← resolves correctly
```

**Why:** Traditional Python packages have `__init__.py`. The resolver handles
this via the `__init__.py` fallback in `_resolve_python_import`. Namespace
packages (PEP 420, common in monorepos) omit `__init__.py` entirely — the
directory IS the package.

The resolver already handles this partially (it tries paths without `__init__.py`
for absolute imports), but the combination with L-001 means
`from myorg.shared import models` still fails.

**Confidence impact:** Same as L-001. Counts against graph_confidence.

**Unresolved reason code:** `ambiguous_package_import`

**Test coverage:** `test_graph_accuracy.py::TestMonorepoPackages` covers the
resolved case. The unresolved case (package-level imports in a namespace package)
is not yet tested.

**Upgrade path:** Same as L-001. Requires import statement → imported names
decomposition in the parser.

---

## L-006: `__init__.py` barrel imports (Python)

**What fails:**
```python
# In app/services/__init__.py:
from app.services.analyzer import AnalysisService
from app.services.fetcher import GitHubFetcher

# In app/main.py:
from app.services import AnalysisService  # ← resolves to app/services, not analyzer.py
```

**Why:** `app.services` resolves to `app/services/__init__.py` (the package
entry), not to `app/services/analyzer.py`. The graph shows the correct
dependency chain through `__init__.py`, but consumers wanting to see
`main.py → analyzer.py` directly may not find that edge.

**Confidence impact:** None — the edge to `__init__.py` IS confirmed.
The transitive graph through `__init__.py` → `analyzer.py` is also correct.

**Unresolved reason code:** N/A — this is correct behavior, not a failure.

**Test coverage:** Not specifically tested. Would require a fixture with
`__init__.py` that re-exports submodule members.

**Note:** This is a semantics question, not a resolution bug. The edge
`main.py → __init__.py → analyzer.py` is accurate. If callers want
direct `main.py → analyzer.py` edges, that requires transitive edge flattening,
which is a separate feature.

---

## L-007: Circular imports

**What fails or degrades:**
```python
# app/a.py imports app/b.py
# app/b.py imports app/a.py  ← circular dependency
```

**Why:** BFS with a `visited` set handles this correctly — it will not infinite
loop. However, the BFS depth measurement for files in a cycle depends on which
node the BFS processes first.

**Confidence impact:** None — circular imports are detected and handled.
The graph will contain edges `a → b` and `b → a`, both confirmed. BFS
will mark whichever is reachable first at the shorter depth.

**Unresolved reason code:** N/A — edges resolve correctly.

**Test coverage:** Not specifically tested. The `visited` set in BFS prevents
infinite loops. A circular import regression test would be a good addition.

**Note:** Circular imports in Python are often a code smell. The `CodeFinding`
system can detect and flag them as a `maintainability` finding. This is separate
from resolution behavior.

---

## Summary table

| ID | Pattern | Resolves? | Reason code | Impact |
|---|---|---|---|---|
| L-001 | `from pkg import mod` | ✗ | `ambiguous_package_import` | Medium — common pattern |
| L-002 | `import mod as alias` | ✓ mostly | `parse_ambiguity` | Low |
| L-003 | Dynamic imports | ✗ | `dynamic_import` | Low — not counted against confidence |
| L-004 | Non-default TS aliases | ✗ | `alias_unknown` | High in non-Next.js TS repos |
| L-005 | Namespace packages | ✗ | `ambiguous_package_import` | Medium in modern monorepos |
| L-006 | `__init__.py` re-exports | ✓ (indirect) | N/A | Low — semantics only |
| L-007 | Circular imports | ✓ | N/A | None |

---

## What these limitations mean for scores

When `graph_confidence` is LOW or MODERATE and the scan report shows many
`ambiguous_package_import` unresolved edges, the most likely cause is L-001.
The dependency graph is incomplete — missing edges between files that do
import each other — and `graph_confidence` correctly reflects this.

The fix for users: switch to explicit `from module.submodule import Name`
imports. This is also better Python practice for large codebases.

The fix for Atlas: implement L-001's upgrade path in v1.2.0.
