# Production Rollout

This is the exact launch sequence for Codebase Atlas with the current
Railway `web + worker` backend topology.

Use this during the first production rollout and for later high-risk deploys.

---

## Preflight

Before touching production:

1. Confirm backend CI is green.
2. Confirm frontend CI is green.
3. Confirm the repo includes:
   - `backend/Procfile` with both `web` and `worker`
   - `backend/alembic/versions/0013_add_review_job_commit.py`
4. Confirm Supabase/Postgres credentials are ready.
5. Confirm Anthropic and GitHub tokens are ready.
6. Confirm the frontend production URL is known for `CORS_ORIGINS`.

---

## Railway Setup

Create or verify these two Railway backend services from the same repo:

### Web service

- Root directory: `backend`
- Start command: `sh ./docker-entrypoint.sh`

### Worker service

- Root directory: `backend`
- Start command: `sh ./docker-entrypoint.sh python -m app.worker`

### Shared env vars

Apply the same backend env vars to both services:

- `ANTHROPIC_API_KEY`
- `GITHUB_TOKEN`
- `DATABASE_URL`
- `ENVIRONMENT=production`
- `CORS_ORIGINS=https://your-frontend-domain`
- `WORKER_POLL_INTERVAL_SECONDS=2.0`
- `WORKER_STALE_JOB_SECONDS=1800`
- `WORKER_QUEUE_ORDER=atlas,review`
- `OPS_WORKER_QUEUE_ALERT_SECONDS=120`

---

## Deploy Sequence

1. Deploy the backend web service.
2. Deploy the backend worker service.
3. Watch both logs until startup completes.
4. Verify both services ran `alembic upgrade head`.
5. Deploy or confirm the frontend in Vercel.
6. Update `NEXT_PUBLIC_API_URL` and `API_URL` in Vercel if the backend URL changed.

Do not start smoke tests until both backend services are healthy.

---

## Smoke Test

Set these locally first:

```powershell
$BASE_URL = "https://your-railway-web.up.railway.app"
$REPO_URL = "https://github.com/vercel/next.js"
```

### 1. Health check

```powershell
Invoke-RestMethod "$BASE_URL/health"
```

Expected:

- `status = ok`
- `database = ok`
- `jobs.execution_mode = database_worker_queue`
- `jobs.topology = separate_web_and_worker_processes`

### 2. Ops snapshot before traffic

```powershell
Invoke-RestMethod "$BASE_URL/api/ops/summary"
```

Expected:

- `status = steady` or `active`
- `attention_message = null`

### 3. Submit Atlas job

```powershell
$atlas = Invoke-RestMethod `
  -Method Post `
  -Uri "$BASE_URL/api/analyze" `
  -ContentType "application/json" `
  -Body (@{ repo_url = $REPO_URL } | ConvertTo-Json)

$atlas
```

Expected:

- returns `job_id`
- returns `status = queued`

### 4. Poll Atlas job

```powershell
do {
  Start-Sleep -Seconds 3
  $atlasStatus = Invoke-RestMethod "$BASE_URL/api/analyze/$($atlas.job_id)"
  $atlasStatus
} while ($atlasStatus.status -in @("queued", "running"))
```

Expected:

- transitions `queued -> running -> completed`
- returns `result_id` when completed

### 5. Fetch Atlas result

```powershell
Invoke-RestMethod "$BASE_URL/api/results/$($atlasStatus.result_id)"
```

Expected:

- non-empty result payload
- includes summaries and analysis data

### 6. Submit Review job

```powershell
$review = Invoke-RestMethod `
  -Method Post `
  -Uri "$BASE_URL/api/review/" `
  -ContentType "application/json" `
  -Body (@{ repo_url = $REPO_URL } | ConvertTo-Json)

$review
```

Expected:

- returns `job_id`
- returns `status = queued`

### 7. Poll Review job

```powershell
do {
  Start-Sleep -Seconds 5
  $reviewStatus = Invoke-RestMethod "$BASE_URL/api/review/$($review.job_id)"
  $reviewStatus
} while ($reviewStatus.status -in @("queued", "running"))
```

Expected:

- transitions `queued -> running -> completed`
- returns `result_id` when completed

### 8. Fetch Review result

```powershell
Invoke-RestMethod "$BASE_URL/api/review/results/$($reviewStatus.result_id)"
```

Expected:

- non-empty scorecard/findings payload

### 9. Ops snapshot during or after jobs

```powershell
Invoke-RestMethod "$BASE_URL/api/ops/summary"
```

Expected:

- `status = active` while jobs are moving
- `attention_message = null` during normal flow

---

## Worker Failure Check

This verifies that the backlog alerting path works.

1. Stop or scale down the worker service temporarily.
2. Submit an Atlas job.
3. Wait at least `OPS_WORKER_QUEUE_ALERT_SECONDS` seconds.
4. Call:

```powershell
Invoke-RestMethod "$BASE_URL/api/ops/summary"
```

Expected:

- `status = watch`
- `attention_message` mentions queued jobs without an active worker

Then:

1. Start the worker again.
2. Poll `/api/ops/summary`.
3. Confirm the queue drains and the attention message clears.

---

## Rollback Triggers

Rollback or pause the rollout if any of these happen:

- `/health` is not `ok`
- migrations fail on startup
- worker fails to boot repeatedly
- Atlas jobs stay queued with no worker activity
- Review jobs fail broadly with infrastructure errors
- `/api/ops/summary` stays at `watch` after worker recovery

---

## Post-Deploy Checks

After the smoke test passes:

1. Open the production frontend.
2. Run one Atlas flow through the UI.
3. Run one Review flow through the UI.
4. Confirm homepage ops panel shows healthy state.
5. Check Railway logs for repeated worker restarts.
6. Check Supabase for connection or migration errors.

---

## Notes

- The backend worker is now the source of truth for job execution.
- `/health` reports local service readiness, not third-party vendor reachability.
- `/api/ops/summary` is the operational signal for queue health and worker backlog.
