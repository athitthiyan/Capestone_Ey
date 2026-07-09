# GL Guardian Load Tests

This folder contains a standard-library Python load runner for the backend API
and agent workflow.

## What It Covers

`comprehensive_api_agents_load_test.py` exercises:

- Health: `/health`, `/health/detailed`, `/metrics`
- Auth: `/auth/register`, `/auth/token`, `/auth/me` when a token is available
- Settings: `/settings`, `/settings/llm`, `/settings/llm/providers`
- Knowledge/RAG: `/knowledge/sources`, `/knowledge/chunks`, `/knowledge/search`, `/knowledge/reindex`
- Investigations: create, list, stats, workspace, debate, evidence, verification, audit, replay
- Agents: `/investigations/{id}/execute`, `/agents/health`, `/agents/workflow/{id}`
- Claims: preview, third-party verification, latest verification
- Reviews: queue, escalate, request evidence, approve
- Reports, audit, evaluation, analytics, LLM analytics
- Employee transactions: create, list, get, update, archive when a load-test user can be created or resolved

Bulk destructive endpoints such as `/investigations/all` are intentionally not
called by this runner.

## Run

Start the backend first. For local deterministic agent load testing, keep
`USE_REAL_AGENTS=false` so the agent crew runs without external LLM calls.

```powershell
cd "C:\Users\athit\GL Guardian"
python load-tests/comprehensive_api_agents_load_test.py `
  --base-url http://localhost:8000/api/v1 `
  --users 4 `
  --iterations 8 `
  --agent-cases 2
```

For an authenticated environment:

```powershell
$env:LOADTEST_API_USERNAME = "admin"
$env:LOADTEST_API_PASSWORD = "your-password"
python load-tests/comprehensive_api_agents_load_test.py --base-url https://api.example.com/api/v1
```

Useful knobs:

- `--users`: concurrent worker threads.
- `--iterations`: total scenario iterations.
- `--agent-cases`: how many investigations are actually executed through the agent crew.
- `--skip-agent-execution`: cover read/write APIs without running the crew.
- `--allow-missing-agent-prometheus`: pass the run when terminal agent cases have API/DB artifacts but the process-local agent counters do not move. The report still records a warning.
- `--poll-timeout`: how long to wait for executed investigations to finish.
- `--max-error-rate`: validation threshold for failed API calls.

Reports are written to `load-tests/reports/comprehensive-api-agents-<run_id>.json`.
When employee transaction create is unavailable, the report includes
`employee_transaction_skips` with the status and response reason for each
skipped CRUD sequence.

## How Metrics Are Checked

The runner snapshots `/metrics` and analytics before and after the workload.
For executed agent cases, it also stores `case_observability` by reading the
case, workspace, and workflow APIs after execution. That gives the report two
checks: did the agent persist case artifacts, and did Prometheus expose matching
counters?

It marks the run failed when:

- Any required endpoint family was not exercised.
- API error rate is above `--max-error-rate`.
- `/metrics` is unavailable or unparsable.
- Prometheus output has no HTTP metrics.
- For terminal agent cases, these app counters do not increase enough:
  - `gl_guardian_investigations_total`
  - `gl_guardian_debate_rounds_total`
  - `gl_guardian_verification_results_total`
- Any Prometheus metric value is negative.
- `/analytics/requests` is missing key fields or reports an error rate above the threshold.
- LLM analytics token accounting is inconsistent:
  - `total_tokens != prompt_tokens + completion_tokens`
  - grouped `calls != successful_calls + failed_calls`
  - negative cost, latency, cache, fallback, or call counts

Interpreting results:

- A passed run means the API surface responded within the configured error-rate threshold and the metrics are internally consistent with the load test.
- A failed run means either the API had request failures, the agent workflow did not emit expected counters, or analytics/Prometheus values are malformed or inconsistent.
- If terminal cases have debate/evidence/verification artifacts but the agent Prometheus deltas remain zero, the agent workflow likely ran but `/metrics` is not exporting the worker/process that increments those counters. In production this commonly happens when `USE_CELERY=true` or Uvicorn runs multiple workers without Prometheus multiprocess aggregation.
- Use `--allow-missing-agent-prometheus` only to continue latency/throughput testing while that export gap is being fixed.
- If `employee_transactions` is `0`, inspect `employee_transaction_skips` to see whether production is missing the route, rejecting the role, or failing to resolve the authenticated user as an employee.
- With `USE_REAL_AGENTS=false`, LLM metrics may remain zero. That is expected. With `USE_REAL_AGENTS=true`, LLM call, token, latency, and cost metrics should increase.

# GL Guardian Load-Test Runbook

This runbook is designed for a presentation rehearsal. It proves the API can
handle concurrent dashboard and investigation traffic without triggering costly
LLM/agent execution by default.

## 1. What to Test

Use three layers:

| Layer | Purpose | Safe for demo? |
|---|---|---|
| Smoke | Confirms the app is reachable and the script is valid. | Yes |
| Baseline | Shows normal concurrent API usage. | Yes |
| Presentation | Shows a controlled burst for stakeholder demo. | Yes |
| Stress | Finds the point where latency/errors degrade. | Run after rehearsal |

The default script is read-only. It hits:

- `GET /health`
- `GET /api/v1/investigations?limit=25`
- `GET /api/v1/analytics/kpis`
- `GET /api/v1/analytics/trend?limit=500`

Set `WRITE_CASES=true` only when you deliberately want to create synthetic
load-test investigations.

## 2. Install k6 on Windows

Recommended:

```powershell
winget install k6 --source winget
```

Alternative:

```powershell
choco install k6
```

Verify:

```powershell
k6 version
```

Official docs: https://grafana.com/docs/k6/latest/set-up/install-k6/

## 3. Start GL Guardian

Terminal 1:

```powershell
cd "C:\Users\athit\GL Guardian\Backend"
docker-compose up -d
```

Verify the API:

```powershell
curl.exe http://localhost:8000/health
curl.exe http://localhost:8000/metrics
```

Optional UI for the presentation:

```powershell
cd "C:\Users\athit\GL Guardian\UI"
npm.cmd run dev
```

Open:

- API docs: http://localhost:8000/docs
- Metrics: http://localhost:8000/metrics
- UI: http://localhost:3000
- Flower: http://localhost:5555

## 4. Run the Load Tests

From the repository root:

```powershell
cd "C:\Users\athit\GL Guardian"
New-Item -ItemType Directory -Force load-tests\reports
```

Smoke test:

```powershell
k6 run -e PROFILE=smoke -e BASE_URL=http://localhost:8000 load-tests/k6/gl-guardian-api.js
```

Baseline test:

```powershell
k6 run -e PROFILE=baseline -e BASE_URL=http://localhost:8000 load-tests/k6/gl-guardian-api.js
```

Presentation burst:

```powershell
k6 run -e PROFILE=presentation -e BASE_URL=http://localhost:8000 load-tests/k6/gl-guardian-api.js
```

Stress test:

```powershell
k6 run -e PROFILE=stress -e BASE_URL=http://localhost:8000 load-tests/k6/gl-guardian-api.js
```

Optional synthetic write test:

```powershell
k6 run -e PROFILE=smoke -e WRITE_CASES=true -e BASE_URL=http://localhost:8000 load-tests/k6/gl-guardian-api.js
```

If auth is enabled, pass a bearer token:

```powershell
k6 run -e PROFILE=baseline -e BASE_URL=http://localhost:8000 -e TOKEN="YOUR_TOKEN" load-tests/k6/gl-guardian-api.js
```

Export a shareable HTML report:

```powershell
New-Item -ItemType Directory -Force load-tests\reports
$env:K6_WEB_DASHBOARD="true"
$env:K6_WEB_DASHBOARD_EXPORT="load-tests/reports/gl-guardian-load-report.html"
k6 run -e PROFILE=presentation -e BASE_URL=http://localhost:8000 load-tests/k6/gl-guardian-api.js
```

## 5. What to Capture for Slides

Capture these four proof points:

1. k6 summary screen:
   - `http_req_duration` p95
   - `http_req_failed`
   - total requests
   - checks passed

2. `/metrics` before and after:
   - HTTP request count
   - request latency histogram
   - investigation and LLM metrics if enabled

3. Docker stats during the run:

```powershell
docker stats
```

4. One UI screenshot:
   - Dashboard or investigations page still responding while the load test runs.

## 6. Presentation Talk Track

Use this concise version:

> We ran controlled API load tests against GL Guardian using k6. The test
> exercised health, investigation listing, KPI analytics, and trend analytics.
> We intentionally kept LLM execution out of the benchmark so the result shows
> platform responsiveness rather than provider latency or token spend. Under the
> presentation profile, the API sustained concurrent dashboard-style traffic
> while staying under the configured p95 latency threshold and maintaining a low
> error rate.

## 7. Guardrails

- Do not run stress tests against production without approval.
- Do not enable `WRITE_CASES=true` on a real customer database.
- Do not load-test `/execute` unless you have budgeted LLM/provider costs and
  Celery worker capacity.
- Always run smoke first, then baseline, then presentation, then stress.
