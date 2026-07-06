# Operations Runbook

**Audience:** SRE / production support. **Verified against:** compose files, `config.py`,
`celery_app.py`, health routes. **Version:** `0.1.0`.

Commands below assume the self-hosted Compose deployment
(`docker compose --env-file .env.production -f docker-compose.production.yml ...`). On
Railway/K8s use the equivalent platform command; the logic is identical.

## System overview

Services: `ui`, `api`, `worker`, `beat`, `postgres`, `redis`, `eventstore` (+ one-shot
`migrate`). See [Infrastructure](INFRASTRUCTURE.md) and [Architecture](ARCHITECTURE.md).

## Startup procedure

```bash
cd ~/skeptic-engine
docker compose --env-file .env.production -f docker-compose.production.yml pull
docker compose --env-file .env.production -f docker-compose.production.yml run --rm migrate
docker compose --env-file .env.production -f docker-compose.production.yml up -d
docker compose -f docker-compose.production.yml ps        # all healthy
curl -fsS http://localhost:8000/health
```

Order matters: datastores healthy -> `migrate` -> `api`/`worker`/`beat`/`ui`. Compose
`depends_on: condition: service_healthy` enforces this.

## Shutdown procedure

```bash
# graceful (keep data)
docker compose -f docker-compose.production.yml stop
# full teardown (keep volumes)
docker compose -f docker-compose.production.yml down
# NEVER use `down -v` in production - it deletes postgres/redis/eventstore volumes
```

## Restart procedure

```bash
docker compose -f docker-compose.production.yml restart api        # single service
docker compose -f docker-compose.production.yml up -d --force-recreate worker beat
```

## Daily operations

- Confirm `/health` and `/health/detailed` are green.
- Check worker/beat are consuming (Flower or `logs worker`); no growing backlog.
- Scan error logs for repeated 5xx or LLM fallback storms.
- Review LLM spend: `GET /api/v1/analytics/llm/summary`.
- Confirm nightly backup succeeded (see [Backup and Restore](BACKUP_RESTORE.md)).

## Weekly maintenance

- Review `request_logs` growth; apply retention/pruning if needed.
- Verify the scheduled `tasks.cleanup_old_states` and `tasks.sync_vector_embeddings`
  beat jobs are running.
- Check disk usage on `postgres_data` / `eventstore_data` volumes.
- Review open items in [Known Issues](KNOWN_ISSUES.md).

## Monthly maintenance

- Apply dependency/security updates (see [Maintenance](MAINTENANCE.md)); redeploy via CI.
- Test restore from backup into a scratch environment (DR drill).
- Rotate credentials per policy (see Secret rotation below).
- Reconcile LLM model IDs in settings vs provider availability.

## Health checks

| Check | Command |
|-------|---------|
| Liveness | `curl -fsS http://localhost:8000/health` |
| Readiness (DB, WS) | `curl -fsS http://localhost:8000/health/detailed` |
| Metrics | `curl -fsS http://localhost:8000/metrics | head` |
| Migrations at head | `docker compose ... run --rm migrate alembic current` |
| LLM providers | `curl -fsS http://localhost:8000/api/v1/analytics/llm/providers` |
| Worker | Flower http://localhost:5555 or `logs worker` |

## Monitoring dashboards

Prometheus scrapes `/metrics` (HTTP + LLM cost/latency/token + pipeline metrics).
Optional LangSmith tracing (`LANGSMITH_TRACING=true`). See
[Monitoring and Logging](MONITORING_LOGGING.md) for the metric list and alert rules.

## Log locations

- Container logs: `docker compose -f docker-compose.production.yml logs -f <service>`.
- In-app HTTP audit: `request_logs` table. Business audit: `audit_log` table (+ EventStore).
- LLM telemetry: `llm_call_logs` table.

## Alerts and escalation matrix

| Severity | Example | First responder | Escalate to |
|----------|---------|-----------------|-------------|
| SEV1 | API down / DB unreachable / data loss | On-call SRE | Eng lead + product owner |
| SEV2 | Worker backlog, LLM provider outage, elevated 5xx | On-call SRE | Backend owner |
| SEV3 | Single non-critical feature degraded | On-call SRE | Backlog |

Full flow: [Incident Response](INCIDENT_RESPONSE.md).

## Incident response (summary)

Detect -> declare severity -> stabilize (restart/scale/rollback) -> communicate -> root
cause -> post-incident review. Detail: [Incident Response](INCIDENT_RESPONSE.md).

## Disaster recovery / backup

See [Disaster Recovery](DISASTER_RECOVERY.md) and [Backup and Restore](BACKUP_RESTORE.md).

## Secret rotation

1. Generate the new secret in the secret store / `.env.production`.
2. `SECRET_KEY` rotation invalidates all issued JWTs - expect users to re-login.
3. `docker compose ... up -d --force-recreate api worker beat` to pick up new env.
4. Rotate provider keys one at a time; verify `GET /api/v1/analytics/llm/providers`.
5. Record the rotation in the change log.

## Certificate renewal

TLS terminates at the reverse proxy / LB, not the app. Renew there (e.g. cert-manager or
certbot). No app restart is required for cert renewal.

## Version upgrade

Deploy a new image SHA via CI (`workflow_dispatch`) or the Compose steps above. The
`migrate` job runs `alembic upgrade head` before the API restarts.

## Rollback process

1. Identify the last-good image SHA (GHCR tags / previous deploy).
2. Set `BACKEND_IMAGE`/`UI_IMAGE` to that SHA in `.env.production`.
3. If the bad release added a migration, confirm it is backward-compatible before
   rolling app code back; if not, follow [Disaster Recovery](DISASTER_RECOVERY.md).
4. `docker compose ... pull && up -d`. Verify health + a smoke investigation.
