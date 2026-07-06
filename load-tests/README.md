# Skeptic Engine Load-Test Runbook

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

## 3. Start Skeptic Engine

Terminal 1:

```powershell
cd "C:\Users\athit\Skeptic Engine\Backend"
docker-compose up -d
```

Verify the API:

```powershell
curl.exe http://localhost:8000/health
curl.exe http://localhost:8000/metrics
```

Optional UI for the presentation:

```powershell
cd "C:\Users\athit\Skeptic Engine\UI"
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
cd "C:\Users\athit\Skeptic Engine"
New-Item -ItemType Directory -Force load-tests\reports
```

Smoke test:

```powershell
k6 run -e PROFILE=smoke -e BASE_URL=http://localhost:8000 load-tests/k6/skeptic-engine-api.js
```

Baseline test:

```powershell
k6 run -e PROFILE=baseline -e BASE_URL=http://localhost:8000 load-tests/k6/skeptic-engine-api.js
```

Presentation burst:

```powershell
k6 run -e PROFILE=presentation -e BASE_URL=http://localhost:8000 load-tests/k6/skeptic-engine-api.js
```

Stress test:

```powershell
k6 run -e PROFILE=stress -e BASE_URL=http://localhost:8000 load-tests/k6/skeptic-engine-api.js
```

Optional synthetic write test:

```powershell
k6 run -e PROFILE=smoke -e WRITE_CASES=true -e BASE_URL=http://localhost:8000 load-tests/k6/skeptic-engine-api.js
```

If auth is enabled, pass a bearer token:

```powershell
k6 run -e PROFILE=baseline -e BASE_URL=http://localhost:8000 -e TOKEN="YOUR_TOKEN" load-tests/k6/skeptic-engine-api.js
```

Export a shareable HTML report:

```powershell
New-Item -ItemType Directory -Force load-tests\reports
$env:K6_WEB_DASHBOARD="true"
$env:K6_WEB_DASHBOARD_EXPORT="load-tests/reports/skeptic-engine-load-report.html"
k6 run -e PROFILE=presentation -e BASE_URL=http://localhost:8000 load-tests/k6/skeptic-engine-api.js
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

> We ran controlled API load tests against Skeptic Engine using k6. The test
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
