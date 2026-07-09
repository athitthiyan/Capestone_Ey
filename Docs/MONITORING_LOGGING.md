# Monitoring and Logging Guide

**Verified against:** `app/main.py` (Instrumentator), `config.py`, `app/core/request_logging.py`,
`celery_app.py`. **Version:** `0.1.0`.

## Metrics

- Exposed at `GET /metrics` when `METRICS_ENABLED=true` (default), via
  `prometheus-fastapi-instrumentator`. Excluded from OpenAPI.
- Includes HTTP request metrics plus application LLM cost/latency/token and pipeline
  metrics.

### Prometheus scrape example

```yaml
scrape_configs:
  - job_name: gl-guardian-api
    metrics_path: /metrics
    static_configs:
      - targets: ["api.internal:8000"]
```

### Suggested alert rules

| Alert | Condition | Severity |
|-------|-----------|----------|
| API down | `/health` non-200 or scrape failing > 2m | SEV1 |
| DB unreachable | `/health/detailed` returns 503 | SEV1 |
| Elevated 5xx | HTTP 5xx rate > 2% over 5m | SEV2 |
| Latency | p95 request latency > target over 10m | SEV2 |
| LLM spend spike | LLM cost/hour > budget | SEV2 |
| Worker backlog | Celery queue depth rising > 15m | SEV2 |

## Tracing

Optional LangSmith tracing for every LangGraph/LLM call: set `LANGSMITH_TRACING=true` and
`LANGSMITH_API_KEY` (project `gl-guardian`). Mirrored into `LANGCHAIN_*` env at startup.

## Application logs

- Format: `%(asctime)s - %(name)s - %(levelname)s - %(message)s`, level `LOG_LEVEL`.
- Access via `docker compose logs -f <service>` (or platform log stream).
- Unhandled exceptions are logged with stack trace server-side; the client only sees a
  generic message + `request_id` unless `DEBUG=true`.

## Structured audit trails (in the database)

| Table | What | Endpoint |
|-------|------|----------|
| `request_logs` | Every HTTP request (excl. health/docs) | `GET /api/v1/audit/requests` |
| `audit_log` | Immutable hash-chained business events | `GET /api/v1/audit`, `/audit/recent` |
| `llm_call_logs` | Per-call cost/latency/tokens/provider | `GET /api/v1/analytics/llm/*` |
| `ragas_evaluation_results` | Real-time quality scores | `GET /api/v1/evaluation/*` |

`REQUEST_LOG_EXCLUDED_PATHS` controls what the request logger skips; disable entirely with
`REQUEST_LOGGING_ENABLED=false`.

## What to watch

- 5xx rate and p95 latency (Prometheus).
- LLM cost trend and provider fallbacks (`/api/v1/analytics/llm/cost-trends`, `by-provider`).
- Verifier rejections / escalations (quality regressions).
- Worker queue depth and task retries (Flower).
- Audit-chain continuity (integrity of `audit_log`).


## Live measurements (2026-07-08)

Measured against the production deployment (single external client; smoke-level, not a
load test). Source and method: `Docs/LIVE_DATA_VALIDATION.md` §5.

| Metric | Value |
|--------|-------|
| API `/health` availability | 100% over 80 requests (0 errors) |
| API latency median / avg | 220 ms / 334 ms |
| API latency p95 / p99 | 1.25 s / 1.26 s |
| UI `/dashboard` TTFB avg / p95 | 188 ms / 247 ms (10 requests) |
| `/metrics` exposition | live, 31 metric families |
| Auth enforcement | `/api/v1/*` returns 401 without JWT |
| Cloud stress/soak, CPU/RAM, real-agent E2E latency | **Not measured** |
