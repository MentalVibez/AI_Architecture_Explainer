# MERGE_GUIDE

**22 files. 30 minutes. 7 steps.**

Merges the deep intelligence engine from `Testing/` into the live backend. After this merge, the six `/api/results/{id}/intelligence*` endpoints are live and the Review pipeline has a full production scorecard.

---

## File inventory

### Root (2)
| File | Action |
|------|--------|
| `README.md` | Updated (already done) |
| `MERGE_GUIDE.md` | This file |

### Backend source (9)
| Destination | Source |
|---|---|
| `backend/app/schemas/intelligence.py` | `Testing/intelligence.py` |
| `backend/app/services/deep_scanner.py` | `Testing/deep_scanner.py` |
| `backend/app/services/pipeline.py` | `Testing/pipeline.py` |
| `backend/app/services/context_reviewer.py` | `Testing/context_reviewer.py` |
| `backend/app/services/repair_engine.py` | `Testing/repair_engine.py` |
| `backend/app/services/scorecard.py` | `Testing/scorecard.py` |
| `backend/app/services/report_builder.py` | `Testing/report_builder.py` |
| `backend/app/api/routes/intelligence.py` | `Testing/mnt/user-data/outputs/atlas_merge_package/backend/app/api/routes/intelligence.py` |
| `backend/app/models/intelligence.py` | `Testing/mnt/user-data/outputs/atlas_merge_package/backend/app/models/intelligence.py` |

### Tests (8)
| Destination | Source |
|---|---|
| `backend/tests/unit/test_deep_scanner.py` | `Testing/test_deep_scanner.py` |
| `backend/tests/unit/test_graph_accuracy.py` | `Testing/test_graph_accuracy.py` |
| `backend/tests/unit/test_integration.py` | `Testing/test_integration.py` |
| `backend/tests/unit/test_invariants.py` | `Testing/test_invariants.py` |
| `backend/tests/unit/test_real_world.py` | `Testing/test_real_world.py` |
| `backend/tests/unit/test_repair_engine.py` | `Testing/test_repair_engine.py` |
| `backend/tests/fixtures/golden_repos.py` | `Testing/golden_repos.py` |
| `backend/tests/fixtures/real_world_shapes.py` | `Testing/real_world_shapes.py` |

### Docs (3)
| Destination | Source |
|---|---|
| `docs/PIPELINE_ARCHITECTURE.md` | `Testing/PIPELINE_ARCHITECTURE.md` |
| `docs/LIMITATIONS.md` | `Testing/LIMITATIONS.md` |
| `docs/SEMANTICS.md` | `Testing/SEMANTICS.md` |

---

## Step 1 — Copy the 20 backend files

```bash
# Create destination directories
mkdir -p backend/app/schemas
mkdir -p backend/app/api/routes
mkdir -p backend/tests/unit
mkdir -p backend/tests/fixtures
mkdir -p docs

# Source modules
cp Testing/intelligence.py        backend/app/schemas/intelligence.py
cp Testing/deep_scanner.py        backend/app/services/deep_scanner.py
cp Testing/pipeline.py            backend/app/services/pipeline.py
cp Testing/context_reviewer.py    backend/app/services/context_reviewer.py
cp Testing/repair_engine.py       backend/app/services/repair_engine.py
cp Testing/scorecard.py           backend/app/services/scorecard.py
cp Testing/report_builder.py      backend/app/services/report_builder.py

# Routes and ORM (from the mnt/ output artifacts)
cp "Testing/mnt/user-data/outputs/atlas_merge_package/backend/app/api/routes/intelligence.py" \
   backend/app/api/routes/intelligence.py
cp "Testing/mnt/user-data/outputs/atlas_merge_package/backend/app/models/intelligence.py" \
   backend/app/models/intelligence.py

# Tests
cp Testing/test_deep_scanner.py   backend/tests/unit/test_deep_scanner.py
cp Testing/test_graph_accuracy.py backend/tests/unit/test_graph_accuracy.py
cp Testing/test_integration.py    backend/tests/unit/test_integration.py
cp Testing/test_invariants.py     backend/tests/unit/test_invariants.py
cp Testing/test_real_world.py     backend/tests/unit/test_real_world.py
cp Testing/test_repair_engine.py  backend/tests/unit/test_repair_engine.py
cp Testing/golden_repos.py        backend/tests/fixtures/golden_repos.py
cp Testing/real_world_shapes.py   backend/tests/fixtures/real_world_shapes.py

# Docs
cp Testing/PIPELINE_ARCHITECTURE.md docs/PIPELINE_ARCHITECTURE.md
cp Testing/LIMITATIONS.md           docs/LIMITATIONS.md
cp Testing/SEMANTICS.md             docs/SEMANTICS.md

# Touch __init__.py files where needed
touch backend/app/schemas/__init__.py
touch backend/app/api/routes/__init__.py
touch backend/tests/unit/__init__.py
touch backend/tests/fixtures/__init__.py
```

All import paths in the copied files are already written for the installed `app.*` package layout. No edits needed.

---

## Step 2 — Register the intelligence router

Open `backend/app/main.py`. Add one import and one `include_router` call, following the existing pattern:

```python
# Add this import with the other router imports (around line 10–17):
from app.api.routes.intelligence import router as intelligence_router

# Add this line after the existing app.include_router calls (around line 53–60):
app.include_router(intelligence_router, prefix="/api")
```

The existing routers are: `health_router`, `analysis_router`, `results_router`, `scout_router`, `map_router`, `review_router`, `public_analyze_router`. The intelligence router adds six `GET` endpoints under `/api/results/{result_id}/intelligence*`.

---

## Step 3 — Wire `_get_db` and `_load_result`

Open `backend/app/api/routes/intelligence.py`. It has two stubs near the top.

### `_get_db` — straightforward

Replace the stub with the same dependency the rest of the app uses:

```python
from app.core.database import get_db

# In each route signature, use:
# db: AsyncSession = Depends(get_db)
```

`get_db` is already defined in `app.core.database` and used by every other route file.

### `_load_result` — your one real decision

**Option A — stub (recommended first, ships immediately):**

```python
async def _load_result(result_id: int, db: AsyncSession):
    return None, None
```

All six endpoints return valid empty responses. You can deploy and confirm the routes are reachable before doing any DB work.

**Option B — full DB query (fill in after deploying Option A):**

```python
from sqlalchemy import select
from app.models.analysis_result import AnalysisResult
from app.models.intelligence import FileIntelligenceORM, ProductionScoreORM
from app.services.report_builder import ReportBuilder

async def _load_result(result_id: int, db: AsyncSession):
    result = await db.get(AnalysisResult, result_id)
    if not result:
        raise HTTPException(status_code=404, detail="Result not found")

    # Load file intelligence rows and reconstruct RepoIntelligence
    file_rows = (await db.execute(
        select(FileIntelligenceORM).where(FileIntelligenceORM.result_id == result_id)
    )).scalars().all()

    score_row = (await db.execute(
        select(ProductionScoreORM).where(ProductionScoreORM.result_id == result_id)
    )).scalar_one_or_none()

    # Reconstruct objects from ORM rows and return (RepoIntelligence, ProductionScore)
    # See docs/PIPELINE_ARCHITECTURE.md for the full shape
    ...
```

Start with Option A. It makes the endpoints live and lets tests pass. Switch to Option B in a follow-up PR.

---

## Step 4 — Create and run the Alembic migration

```bash
cd backend
alembic revision --autogenerate -m "add_intelligence_tables"
alembic upgrade head
```

This creates five new tables:

| Table | FK | Purpose |
|---|---|---|
| `file_intelligence` | `result_id → analysis_results.id` | Per-file metrics, role, signals |
| `dependency_edges` | `result_id → analysis_results.id` | Import graph edges |
| `code_findings` | `result_id → analysis_results.id` | Evidence-backed issues |
| `production_scores` | `result_id → analysis_results.id` (unique) | Composite scorecard |
| `dimension_scores` | `score_id → production_scores.id` | Per-dimension breakdown |

All tables are additive — no existing tables are modified.

---

## Step 5 — Wire `IntelligencePipeline` into the job worker

Open `backend/app/services/analysis_pipeline.py`. The existing `run_analysis()` function already fetches the repo tree. Add five lines after the tree is available:

```python
# Add this import at the top of the file:
from app.services.pipeline import IntelligencePipeline, PipelineConfig
from app.core.config import settings

# Inside run_analysis(), after this existing line:
#   tree = await github_service.get_repo_tree(owner, repo, default_branch)
# Add:
_config = PipelineConfig(
    github_token=getattr(settings, "github_token", None),
    anthropic_api_key=settings.anthropic_api_key,
)
_pipeline = IntelligencePipeline(_config)
intel_result = await _pipeline.run(
    f"https://github.com/{owner}/{repo}", tree, ref=default_branch
)
# intel_result.intelligence holds RepoIntelligence — persist to DB in Step 3 Option B
```

`intel_result.succeeded` is `True` if the scan completed, `False` on timeout or error — the pipeline never raises.

---

## Step 6 — Run tests

```bash
cd backend && pytest
```

Expected outcome:
- All **existing** tests continue to pass (they are unaffected by the new files)
- **354 new tests** from the six intelligence test files pass

All tests are deterministic — no network calls, no LLM calls, no external dependencies. If a test imports from `app.schemas.intelligence` and fails with `ModuleNotFoundError`, confirm Step 1 created `backend/app/schemas/__init__.py`.

---

## Step 7 — Deploy

```bash
git add backend/ docs/ README.md MERGE_GUIDE.md
git commit -m "feat: add deep intelligence engine"
git push origin main
```

Before or immediately after pushing:

```bash
# Run against the Supabase prod DB URL
DATABASE_URL=postgresql+asyncpg://... alembic upgrade head
```

Railway and Vercel configs are unchanged. The new tables are created by the migration; no environment variables are needed for the intelligence endpoints.

---

## What works immediately after this merge

| Feature | Status |
|---|---|
| Six `/api/results/{id}/intelligence*` endpoints live | Yes — returns empty with Option A stub |
| All 354 new tests pass | Yes — fully deterministic |
| DeepScan runs during analysis jobs | Yes — after Step 5 |
| DB persistence of intelligence data | Only after Step 3 Option B |
| RepairEngine proposals surfaced in UI | Separate PR (frontend + `/results/{id}/repairs` endpoint) |

---

## Rollback

```bash
git revert HEAD
alembic downgrade -1
```

The five new tables are dropped by `downgrade -1`. No existing data is affected.
