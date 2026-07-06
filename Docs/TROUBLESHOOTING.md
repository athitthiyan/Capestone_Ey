# Troubleshooting Guide

**Version:** `0.1.0`. Symptom -> likely cause -> fix, grounded in the code.

## Startup fails immediately

| Error | Cause | Fix |
|-------|-------|-----|
| `SECRET_KEY is required when AUTH_REQUIRED=true` | Auth on, no key | Set `SECRET_KEY` (>=32 in prod) |
| `AUTH_REQUIRED must be true when ENV=production` | Prod safety check | Set `AUTH_REQUIRED=true` |
| `SECRET_KEY must be at least 32 characters when ENV=production` | Weak key | Use a 32+ char random key |
| `CORS_ORIGINS must be explicit when ENV=production` | `*` in prod | Set an explicit JSON list |
| `<PROVIDER>_API_KEY is required when USE_REAL_AGENTS=true` | Real agents, no key | Set the key for `DEFAULT_LLM_PROVIDER` |
| `LANGSMITH_API_KEY is required when LANGSMITH_TRACING=true` | Tracing on, no key | Set the key or disable tracing |
| `DEFAULT_ADMIN_PASSWORD ... at least 12 characters` | Seeding in prod | Set a strong password or `SEED_DEFAULT_USER=false` |

## API returns 500 with no detail

By design in production the client sees `{"detail":"Internal server error","request_id":...}`.
Find the real error in the server logs by `request_id`, or set `DEBUG=true` locally.

## Live WebSocket events never arrive (across processes)

The worker and API are separate processes. Set `USE_REDIS_EVENTS=true` and ensure Redis is
reachable from both. With it off, only same-process clients get events.

## Agents produce generic/stub output

`USE_REAL_AGENTS=false` streams deterministic stubs. Set `USE_REAL_AGENTS=true` and provide
the provider key to get real reasoning (higher cost/latency).

## Investigations never start / stay queued

- `USE_CELERY=true` but no worker running -> start `worker`.
- Redis unreachable -> broker down; check `redis` health and `CELERY_BROKER_URL`.
- With `USE_CELERY=false`, execution is synchronous in the API request instead.

## Database / migration issues

| Symptom | Fix |
|---------|-----|
| Tables missing in prod | Run the `migrate` job / `alembic upgrade head` (prod never auto-creates) |
| `alembic current` behind head | Apply migrations before starting the API |
| pgvector errors on `vector_embeddings` | `CREATE EXTENSION IF NOT EXISTS vector;` on the DB |
| Pool timeout under load | Raise `DATABASE_POOL_SIZE`/`MAX_OVERFLOW`; add PgBouncer |

## LLM failures / high cost

- Transient provider error -> `ENABLE_LLM_FALLBACK` tries `LLM_FALLBACK_ORDER`.
- Cost spike -> inspect `/api/v1/analytics/llm/cost-trends`; lower usage, switch provider,
  or set `LLM_CACHE_ENABLED=true` (default).
- Model not found -> update the `*_MODEL_*` setting to a currently-available model.

## CORS / blocked browser requests

Add the UI origin to `CORS_ORIGINS` (explicit JSON list in prod). Confirm the UI's
`NEXT_PUBLIC_API_BASE_URL` matches the API URL.

## UI shows old API URL

`NEXT_PUBLIC_*` are baked at build time. Rebuild the UI image with the correct build args
(see [CICD.md](CICD.md)).

## EventStore down

If `USE_EVENTSTORE=true` and EventStoreDB is unreachable, the app logs a warning and falls
back to the Postgres hash-chain audit (`AUDIT_FALLBACK_TO_POSTGRES=true`). No outage, but
fix EventStore to restore the dedicated audit store.

## Health check flapping in containers

`/health` must return 200 within the healthcheck window. Cold starts on sleepy free tiers
can trip this; raise `healthcheckTimeout` (Railway) / start-period (Docker) if needed.
