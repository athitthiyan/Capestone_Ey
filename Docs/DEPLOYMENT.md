# Deployment Guide

**Verified against:** `docker-compose.production.yml`, `Backend/Dockerfile`, `UI/Dockerfile`,
`Backend/railway.*.json`, `Backend/k8s-deployment.yaml`, `.github/workflows/ci-cd.yml`,
`production.env.example`. **Version:** `0.1.0`.

This guide covers Docker Compose (self-hosted), Railway (managed), Kubernetes, and generic
cloud. For a zero-cost demo, see the root `DEPLOYMENT_GUIDE.md` (free-tier). For CI-driven
deploys, see [CICD.md](CICD.md).

## 0. Prerequisites and topology

- A host or cluster with Docker Engine + Compose plugin (or a K8s cluster / Railway account).
- PostgreSQL 16 (managed or containerized). Enable `pgvector` for RAG.
- A domain + TLS-terminating reverse proxy / load balancer in front of the API and UI.
- Secrets: `SECRET_KEY` (>=32), `POSTGRES_PASSWORD`, LLM provider key(s).

Topology diagram: see [Architecture - Deployment topology](ARCHITECTURE.md#7-deployment-topology-production).

## 1. Docker Compose (self-hosted) - reference path used by CI

The production stack (`docker-compose.production.yml`) defines: `postgres`, `redis`,
`eventstore`, a one-shot `migrate` job, `api`, `worker`, `beat`, and `ui`. It pins
`ENV=production`, `AUTH_REQUIRED=true`, `DEBUG=false`, `USE_CELERY=true`,
`USE_REDIS_EVENTS=true`, `USE_EVENTSTORE=true` (override-able), and uses required-variable
guards (`${VAR:?...}`) that fail fast if a secret is missing.

### Steps

```bash
# On the production host
mkdir -p ~/gl-guardian && cd ~/gl-guardian
cp /path/to/production.env.example .env.production   # then fill real values
# Provide the image tags built by CI:
#   BACKEND_IMAGE=ghcr.io/<owner>/<repo>-backend:<sha>
#   UI_IMAGE=ghcr.io/<owner>/<repo>-ui:<sha>

docker login ghcr.io                                  # if images are private
docker compose --env-file .env.production -f docker-compose.production.yml pull
docker compose --env-file .env.production -f docker-compose.production.yml run --rm migrate
docker compose --env-file .env.production -f docker-compose.production.yml up -d --remove-orphans
docker compose -f docker-compose.production.yml ps
```

Required `.env.production` values (from `production.env.example` + prod safety checks):
`BACKEND_IMAGE`, `UI_IMAGE`, `POSTGRES_PASSWORD`, `SECRET_KEY` (>=32),
`DEFAULT_LLM_PROVIDER` + its API key, `NEXT_PUBLIC_API_BASE_URL`, `CORS_ORIGINS` (explicit
JSON list), `ALLOWED_HOSTS` (explicit JSON list). Optional: `USE_EVENTSTORE`,
`USE_REAL_AGENTS`, `LLM_FALLBACK_ORDER`, `CELERY_WORKER_CONCURRENCY`.

### Volumes / persistence
`postgres_data`, `redis_data`, `eventstore_data` (named volumes). Back these up
(see [Backup and Restore](BACKUP_RESTORE.md)).

### Health checks
`postgres` (`pg_isready`), `redis` (`redis-cli ping`), `eventstore` (`/health/live`),
`api` (`curl /health`). `migrate` runs `alembic upgrade head` once and exits.

### Networking
Put a reverse proxy (nginx/Caddy/Traefik) in front: route `app.example.com` -> `ui:3000`
and `api.example.com` -> `api:8000`, terminating TLS. Do not expose Postgres/Redis/
EventStore publicly.

## 2. Railway (managed) - three services from one image

`Backend/railway.*.json` define three services built from `Backend/Dockerfile`:

| File | Service | Start command | Notes |
|------|---------|---------------|-------|
| `railway.api.json` | API | `uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --workers ${WEB_CONCURRENCY:-1}` | `preDeployCommand: alembic upgrade head`; healthcheck `/health` |
| `railway.worker.json` | Worker | `celery -A app.tasks.celery_app worker --concurrency=4` | restart on failure |
| `railway.beat.json` | Beat | `celery -A app.tasks.celery_app beat` | restart on failure |

Provision Railway Postgres + Redis, set the env vars from
[Environment Variables](ENVIRONMENT_VARIABLES.md) on each service (share via a variable
group), and deploy the UI separately (e.g. Vercel) pointing `NEXT_PUBLIC_API_BASE_URL` at
the API service URL. The API's `preDeployCommand` runs migrations automatically.

> Known gotcha (see project memory / KNOWN_ISSUES): Railway shared-variable references
> must be resolved correctly across the api/worker/beat services or the worker/beat will
> boot with a different DB/Redis than the API.

## 3. Kubernetes

`Backend/k8s-deployment.yaml` provides manifests for the backend. General flow:

```bash
kubectl create namespace gl-guardian
kubectl -n gl-guardian create secret generic gl-guardian-secrets \
  --from-literal=SECRET_KEY=... --from-literal=POSTGRES_PASSWORD=... \
  --from-literal=ANTHROPIC_API_KEY=...
kubectl -n gl-guardian apply -f Backend/k8s-deployment.yaml
kubectl -n gl-guardian rollout status deploy/gl-guardian-api
```

Run migrations as a `Job` (or init container) executing `alembic upgrade head` before the
API rollout. Front with an Ingress + cert-manager for TLS. Set liveness/readiness probes
to `/health` and `/health/detailed`. Review the manifest for the exact resource names,
probes, and replica counts before applying to a real cluster.

## 4. Generic cloud (VM + managed DB)

1. Managed Postgres (Neon/RDS/Cloud SQL); enable `pgvector`.
2. VM/container host for API + worker + beat (Compose path above) or a container service.
3. Managed Redis if using Celery/Redis events; otherwise omit and keep the flags off.
4. TLS at a load balancer / managed proxy; secrets in the platform secret manager.
5. UI on a static/host platform (Vercel/Cloud Run) with `NEXT_PUBLIC_API_BASE_URL` set.

## 5. Post-deployment validation

Run the smoke checks in [RUNBOOK - Health Checks](RUNBOOK.md#health-checks):

```bash
curl -fsS https://api.example.com/health
curl -fsS https://api.example.com/health/detailed
curl -fsS https://api.example.com/metrics | head
# auth
curl -fsS -X POST https://api.example.com/api/v1/auth/token -d 'username=...&password=...'
```

Verify: DB reachable (detailed health), migrations at head (`alembic current`), Redis
reachable if enabled, LLM connectivity (`GET /api/v1/analytics/llm/providers`), a test
investigation runs end to end, background jobs consumed (Flower/worker logs), audit log
writing, and metrics scraping.

## 6. Rollback

Re-deploy the previous image SHA tag (Compose: set `BACKEND_IMAGE`/`UI_IMAGE` to the prior
SHA and `up -d`; Railway: redeploy previous deployment; K8s: `kubectl rollout undo`). Only
run backward-compatible migrations forward; see
[Runbook - Rollback](RUNBOOK.md#rollback-process) and
[Disaster Recovery](DISASTER_RECOVERY.md).
