# Phase 2 Wiring Checklist
## From engine drop-in to backend-only staging pass

Each item has one acceptance criterion. Check the box only when verified.

---

### Step 1: Copy reviewer into backend (Day 1)

```bash
cp -r atlas_reviewer/ backend/app/services/reviewer/
find backend/app/services/reviewer -name "*.py" \
  -exec sed -i 's/from atlas_reviewer\./from app.services.reviewer./g' {} \;
find backend/app/services/reviewer -name "*.py" \
  -exec sed -i 's/import atlas_reviewer/import app.services.reviewer/g' {} \;
```

- [ ] `pytest backend/app/services/reviewer/tests/unit/ -q` → all pass
- [ ] `python -c "from app.services.reviewer.service import run_review"` → no import error

---

### Step 2: Review model + migration (Day 1)

```bash
cp integration/backend/app/models/review.py backend/app/models/review.py
# Edit: uncomment the Base import (replace the placeholder)
alembic revision --autogenerate -m "add reviews table"
# Review generated migration, then:
alembic upgrade head
```

- [ ] Migration runs without error on dev DB
- [ ] `reviews` table exists with all columns
- [ ] `Review.from_report()` callable: `from app.models.review import Review`

---

### Step 3: Wire routes (Day 2)

```bash
cp integration/backend/app/api/routes/review.py backend/app/api/routes/review.py
```

Edit `review.py`:
- [ ] Uncomment `from app.core.database import get_db`
- [ ] Uncomment `from app.models.job import Job`
- [ ] Uncomment `from app.models.review import Review`
- [ ] Uncomment `from app.middleware.rate_limit import check_review_rate_limit`
- [ ] Uncomment `from app.services.review_worker import process_review_job`

Register in `backend/app/main.py`:
```python
from app.api.routes.review import router as review_router
app.include_router(review_router)
```

- [ ] `POST /api/review` returns `{"job_id": "...", "status": "queued"}`
- [ ] `GET /api/review/{job_id}` returns status (even if 501 for now)

---

### Step 4: Wire worker (Day 2)

```bash
cp integration/backend/app/services/review_worker.py backend/app/services/review_worker.py
```

In `review.py`, uncomment `_run_background_review` body:
- [ ] Remove the `pass` placeholder
- [ ] Uncomment `async with async_session_factory() as db`
- [ ] Uncomment `process_review_job(...)` call

- [ ] Submit a real repo → job transitions `queued → running → completed`
- [ ] Review row exists in DB after completion
- [ ] `review.overall_score` is not null
- [ ] `review.depth_level` is not null

---

### Step 5: Docker + Railway deploy (Day 3)

```bash
cp integration/Dockerfile.backend backend/Dockerfile
# Or add just the RUN lines to existing Dockerfile
```

- [ ] `docker build` succeeds locally
- [ ] `ruff --version` works inside container
- [ ] `bandit --version` works inside container
- [ ] `git --version` works inside container
- [ ] Deploy to Railway staging succeeds

---

### Step 6: Rate limiter (Day 3)

```bash
cp integration/backend/app/middleware/rate_limit.py backend/app/middleware/rate_limit.py
```

In `review.py`, uncomment `await check_review_rate_limit(request)`

- [ ] 4th submission from same IP returns HTTP 429
- [ ] Response includes `Retry-After` header
- [ ] First 3 submissions work normally

---

### Step 7: 3-case staging test (Day 3)

```bash
python integration/scripts/staging_test.py --base-url https://your-app.railway.app
```

- [ ] Case 1 (httpx): completed, result fetchable, scalar fields populated
- [ ] Case 2 (GitLab): INVALID_URL returned cleanly
- [ ] Case 3 (reader/master): branch fallback works, completed successfully

---

### Go/no-go for frontend (all must be checked)

- [ ] One real completed review in staging DB
- [ ] `GET /api/results/review/{id}` returns full payload with no null surprises
- [ ] One clean failure job stored with error_code
- [ ] Branch fallback verified in staging container
- [ ] Temp dirs cleaned up (check Railway disk usage after 3 reviews)
- [ ] No raw stack traces in API responses
- [ ] Rate limiting working

When all checked: **start Phase 4 (frontend).**
