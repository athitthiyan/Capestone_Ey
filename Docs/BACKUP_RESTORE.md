# Backup and Restore Guide

**Version:** `0.1.0`. Applies to the self-hosted Compose stack; adapt paths for managed DBs.

## What to back up

| Store | Contains | Criticality |
|-------|----------|-------------|
| PostgreSQL (`postgres_data`) | All cases, states, transcripts, evidence, audit log, users, settings | Critical |
| EventStoreDB (`eventstore_data`) | Immutable audit streams (if `USE_EVENTSTORE=true`) | High |
| Redis (`redis_data`) | Cache + transient broker/results | Low (rebuildable) |
| `.env.production` / secrets | Runtime config | Critical (store in a secret manager, not with backups) |

Redis is transient; do not rely on it for durable state. The system of record is Postgres
(with the audit trail mirrored to EventStore when enabled).

## PostgreSQL backup

```bash
# logical dump (compose service name: postgres, db: gl_guardian, user: gl_guardian)
docker compose -f docker-compose.production.yml exec -T postgres \
  pg_dump -U gl_guardian -d gl_guardian -Fc > gl_guardian_$(date +%Y%m%d_%H%M%S).dump
```

Schedule nightly (cron/systemd timer or the platform's managed backup). Encrypt at rest,
store off-host, and keep >= 30 days plus a monthly long-term copy (align retention with
`AUDIT_RETENTION_YEARS=7` for audit data).

## PostgreSQL restore

```bash
# into a running postgres (destructive to the target DB)
cat gl_guardian_YYYYMMDD_HHMMSS.dump | docker compose -f docker-compose.production.yml \
  exec -T postgres pg_restore -U gl_guardian -d gl_guardian --clean --if-exists
# re-enable pgvector if restoring into a fresh instance
docker compose -f docker-compose.production.yml exec -T postgres \
  psql -U gl_guardian -d gl_guardian -c "CREATE EXTENSION IF NOT EXISTS vector;"
# confirm schema version
docker compose --env-file .env.production -f docker-compose.production.yml run --rm migrate alembic current
```

## EventStoreDB backup

Back up the `eventstore_data` volume (stop the container or use a filesystem snapshot for
consistency):

```bash
docker run --rm -v gl-guardian-production_eventstore_data:/data \
  -v "$PWD":/backup alpine tar czf /backup/eventstore_$(date +%Y%m%d).tgz -C /data .
```

If EventStore is lost and `AUDIT_FALLBACK_TO_POSTGRES=true`, the Postgres audit chain
remains the durable record.

## Volume-level backup (any named volume)

```bash
docker run --rm -v <volume_name>:/data -v "$PWD":/backup alpine \
  tar czf /backup/<name>_$(date +%Y%m%d).tgz -C /data .
```

## Verify backups (do not skip)

- Monthly: restore the latest Postgres dump into a scratch instance, run `alembic current`,
  and hit `/health/detailed`.
- Confirm the audit chain verifies after restore.

## RPO / RTO targets (recommended defaults)

| Metric | Target |
|--------|--------|
| RPO (max data loss) | <= 24h (nightly) or lower with PITR/managed DB |
| RTO (time to restore) | <= 2h from a known-good dump |
