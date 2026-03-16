# Atlas Reviewer — Integration Checklist

## Phase 1: Drop-in (Days 1-3)
Engine into backend, service boundary, tests passing.

- [ ] Copy `atlas_reviewer/` → `backend/app/services/reviewer/`
- [ ] Fix all imports (relative → `app.services.reviewer.*`)
- [ ] Run `pytest backend/app/services/reviewer/tests/` — all 222 must pass
- [ ] Add `service.py` to `backend/app/services/reviewer/service.py`
- [ ] Write one unit test for `run_review()` with a mock clone
- [ ] **Acceptance: 222 tests green, `run_review()` callable from backend shell**

## Phase 2: Persistence (Day 4)
Model, migration, job wiring.

- [ ] Add `backend/app/models/review.py` (from `integration/backend_model.py`)
- [ ] Generate Alembic migration: `alembic revision --autogenerate -m "add reviews table"`
- [ ] Review generated migration, apply to dev DB: `alembic upgrade head`
- [ ] Add `backend/app/api/routes/review.py` (from `integration/backend_routes.py`)
- [ ] Register router in `backend/app/main.py`: `app.include_router(review_router)`
- [ ] Wire actual Job model and DB session into routes (uncomment the TODO blocks)
- [ ] Wire `_run_review_job()` background task to real `run_review()` call
- [ ] **Acceptance: POST /api/review returns job_id, GET /api/review/{id} returns status**

## Phase 3: Adapters + Docker (Days 5-6)
Toolchain in container, verify depth labels.

- [ ] Add ruff, bandit, pip-audit to Dockerfile (see `Dockerfile_additions.txt`)
- [ ] Deploy to Railway staging
- [ ] Submit one real Python repo, verify adapters ran in the result
- [ ] Verify `depth_level` is "structural_plus" or better for Python repos
- [ ] Verify temp directories are cleaned up after job completes
- [ ] Add explicit timeout to background task (wrap in `asyncio.wait_for`)
- [ ] Add repo size check — reject > 50k files before clone starts
- [ ] **Acceptance: Review job completes in < 3 min, depth_level is correct**

## Phase 4: Frontend (Days 7-10)
New `/review` page, components, wired to API.

- [ ] Create `frontend/app/review/page.tsx` — repo URL form, mirrors analyze page
- [ ] Create `frontend/components/review/ReviewScorecard.tsx` — 6 category bars
- [ ] Create `frontend/components/review/FindingsPanel.tsx` — tabbed, evidence drawer
- [ ] Create `frontend/components/review/ProductionVerdict.tsx` — verdict + why-not + flip
- [ ] Create `frontend/components/review/AntiGamingBlock.tsx` — signal table, hiring toggle
- [ ] Create `frontend/components/review/DepthBadge.tsx` — depth + confidence inline
- [ ] Wire submit → poll → fetch loop in `frontend/lib/reviewClient.ts`
- [ ] Add typed response interfaces to `frontend/lib/types.ts`
- [ ] **Acceptance: Can submit repo from browser, see real result rendered**

## Phase 5: Guardrails + Staging Audit (Days 11-13)
Rate limiting, size limits, 5-repo audit, fix operational breakage.

- [ ] Add per-IP rate limit middleware (3 reviews/day on free tier)
- [ ] Add GitHub URL validation (must match `github.com/{owner}/{repo}`)
- [ ] Add pre-clone size estimate via GitHub API metadata before full clone
- [ ] Run 5-repo staging audit using `runner.py` against staging URL
- [ ] Verify JSON export shape is clean
- [ ] Verify error_code appears correctly for: bad URL, private repo, large repo
- [ ] Add `robots.txt` or `noindex` to review results pages if needed
- [ ] **Acceptance: All 5 audit repos complete cleanly, errors fail gracefully**

## Hard constraints (must be true before going live)

- [ ] Temp directories ALWAYS cleaned up (success, failure, timeout, cancellation)
- [ ] Total review timeout ≤ 300s (enforced in `run_review()`)
- [ ] Clone timeout ≤ 180s (enforced in `_clone()`)
- [ ] Error codes stored in Review row — not just generic job failure
- [ ] Score 90+ at structural-only depth shows depth disclosure prominently in UI
- [ ] No raw stack traces visible in API responses
