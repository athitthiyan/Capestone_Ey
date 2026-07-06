# Local Development Guide

**Verified against:** `Backend/docker-compose.yml`, `Backend/Dockerfile`, `requirements.txt`,
`UI/package.json`, `.env.example` files. **Version:** `0.1.0`.

## Prerequisites

- Python 3.11+ (Dockerfile uses `python:3.11-slim`; CI uses 3.11).
- Node.js 22 + pnpm 9.15.9 (via Corepack) for the UI.
- Docker + Docker Compose (for the backing services).
- Optional: `psql`, `redis-cli` for poking at state.

## Option A - Full stack with Docker Compose (recommended)

Brings up 7 services: `postgres`, `redis`, `eventstore`, `api`, `worker`, `beat`, `flower`.

```bash
cd Backend
cp .env.example .env          # add your provider key if USE_REAL_AGENTS=true
docker compose up -d
docker compose ps             # wait for healthy
```

Endpoints:

| Service | URL |
|---------|-----|
| API health | http://localhost:8000/health |
| API docs (Swagger) | http://localhost:8000/docs |
| Prometheus metrics | http://localhost:8000/metrics |
| Flower (Celery) | http://localhost:5555 |
| EventStoreDB UI | http://localhost:2113 |
| pgAdmin (optional) | http://localhost:5050 (`docker compose --profile tools up -d`) |

The compose `api`/`worker`/`beat` services set `USE_CELERY=true`, `USE_REDIS_EVENTS=true`,
and point `EVENTSTORE_URL` at the `eventstore` container, so live updates and async
execution work end to end.

## Option B - API only (minimal, no Redis/Celery/EventStore)

Investigations run in-process; audit goes to Postgres. You only need PostgreSQL.

```bash
cd Backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# ensure DATABASE_URL points at a reachable Postgres; keep USE_CELERY/USE_REDIS_EVENTS/USE_EVENTSTORE=false
alembic upgrade head
uvicorn app.main:app --reload
```

`uvicorn main:app` also works via a compatibility shim, but prefer `app.main:app`.

## Option C - Local production-like

Keep local Postgres, add Redis + EventStoreDB + real agents:

```bash
cd Backend
docker compose -f docker-compose.local-infra.yml up -d
# then set USE_CELERY/USE_REDIS_EVENTS/USE_EVENTSTORE/USE_REAL_AGENTS=true in .env
```

(See `Backend/LOCAL_PRODUCTION.md` for the annotated `.env`.)

## Database migrations

Schema is owned by Alembic (`Backend/migrations/versions/`, 5 revisions as of 0.1.0).

```bash
cd Backend
alembic upgrade head                                   # apply
alembic revision --autogenerate -m "describe change"   # new revision
alembic downgrade -1                                   # roll back one
```

In non-production, the app also runs `init_db()` on startup for convenience; in
production it **only** uses Alembic (no `create_all`) to avoid schema drift.

## Enable pgvector (RAG)

The `vector_embeddings` table uses `pgvector`. On the Postgres instance:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

The knowledge base is indexed on startup (`sync_knowledge_embeddings`) and re-indexable
via `POST /api/v1/knowledge/reindex`.

## Frontend

```bash
cd UI
corepack enable
pnpm install
cp .env.example .env          # set NEXT_PUBLIC_API_BASE_URL (+ token or username/password)
pnpm dev                      # http://localhost:3000
```

Scripts (`UI/package.json`): `dev`, `build`, `start`, `lint`, `typecheck`, `test`
(Vitest), `format`.

## Run a first investigation

```bash
# create
curl -s -X POST http://localhost:8000/api/v1/investigations \
  -H "Content-Type: application/json" \
  -d '{"transactionId":"TXN-1","vendor":"Acme","amount":51000,"category":"Consulting"}'
# execute (use the returned id)
curl -s -X POST http://localhost:8000/api/v1/investigations/{id}/execute
# watch live: ws://localhost:8000/api/v1/ws/investigations/{id}
```

## Tests

```bash
cd Backend && pytest              # sqlite + stub agents, no external services
cd UI && pnpm test                # Vitest
```

## Debugging tips

- 500s: set `DEBUG=true` locally to see the real error + `request_id` in the response.
- No live WS events across processes: ensure `USE_REDIS_EVENTS=true` and Redis reachable.
- Stub output instead of real reasoning: set `USE_REAL_AGENTS=true` + provider key.
- Startup ValueError about `SECRET_KEY`/keys: see the validation rules in
  [Environment Variables](ENVIRONMENT_VARIABLES.md).
