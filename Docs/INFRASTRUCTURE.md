# Infrastructure Guide

**Verified against:** compose files, Dockerfiles, `k8s-deployment.yaml`, `railway.*.json`.
**Version:** `0.1.0`.

## Components

| Component | Image / tech | Ports | Persistence | Required? |
|-----------|--------------|-------|-------------|-----------|
| API | `Backend/Dockerfile` (python:3.11-slim, non-root, `--workers 4`) | 8000 | stateless | Yes |
| UI | `UI/Dockerfile` (node:22-alpine, standalone Next.js) | 3000 | stateless | Yes |
| PostgreSQL | `postgres:16-alpine` | 5432 | `postgres_data` | Yes |
| Redis | `redis:7-alpine` (AOF on) | 6379 | `redis_data` | If `USE_CELERY`/`USE_REDIS_EVENTS` |
| EventStoreDB | `eventstore:23.10.0` | 1113/2113 | `eventstore_data` | Optional (`USE_EVENTSTORE`) |
| Celery worker | backend image | - | stateless | If `USE_CELERY` |
| Celery beat | backend image | - | stateless | If `USE_CELERY` |
| Flower | backend image | 5555 | stateless | Dev/monitoring only |
| pgAdmin | `dpage/pgadmin4:8` | 5050 | `pgadmin_data` | Dev only (`tools` profile) |

## Redis logical databases

| DB | Use |
|----|-----|
| 0 | Cache + real-time pub/sub (`REDIS_URL`) |
| 1 | Celery broker (`CELERY_BROKER_URL`) |
| 2 | Celery result backend (`CELERY_RESULT_BACKEND`) |

## Container images

- **Backend:** multi-stage; deps installed system-wide (so the non-root `appuser` can run
  `uvicorn`/`celery`/`alembic`), runtime has `libpq5` + `curl`, `HEALTHCHECK` on `/health`.
- **UI:** multi-stage `deps -> builder -> runner`, standalone output, non-root `nextjs`
  user, `NEXT_PUBLIC_*` baked at build time.

## Networking

- App tier (UI, API) is the only public surface, behind a TLS reverse proxy / LB.
- Data tier (Postgres, Redis, EventStore) stays on a private network; never exposed.
- API listens on `0.0.0.0:8000`; UI on `0.0.0.0:3000`.

## Scaling

- **API:** horizontal; stateless. Tune uvicorn `--workers` / `WEB_CONCURRENCY` and DB pool
  (`DATABASE_POOL_SIZE`, `DATABASE_MAX_OVERFLOW`).
- **Worker:** horizontal; scale replicas and `--concurrency` (`CELERY_WORKER_CONCURRENCY`)
  for investigation throughput.
- **Beat:** run exactly one instance (scheduler).
- **Postgres:** scale vertically + connection pooling (PgBouncer) as load grows.
- **Redis:** single instance is usually sufficient; use managed HA for production.

See [Scaling and performance notes in MAINTENANCE.md](MAINTENANCE.md).

## Capacity planning inputs

- Per investigation with real agents: ~5 LLM calls x debate rounds; est. cost
  `ESTIMATED_AGENT_RUN_COST_USD` (0.21 default). Cost telemetry: `llm_call_logs` and
  `/api/v1/analytics/llm/*`.
- Investigation timeout: `INVESTIGATION_TIMEOUT_MINUTES` (30).
