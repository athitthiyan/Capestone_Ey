# Skeptic Engine Load Tests

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
cd "C:\Users\athit\Skeptic Engine"
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
  - `skeptic_investigations_total`
  - `skeptic_debate_rounds_total`
  - `skeptic_verification_results_total`
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
