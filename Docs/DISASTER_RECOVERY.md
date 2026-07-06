# Disaster Recovery Guide

**Version:** `0.1.0`. Pairs with [Backup and Restore](BACKUP_RESTORE.md) and
[Runbook](RUNBOOK.md).

## Scope and principles

- **System of record:** PostgreSQL. **Audit:** Postgres hash-chain (+ EventStore if
  enabled). **Everything else** (API/UI/worker) is stateless and rebuilt from images.
- Recover data first, then bring stateless services back on the last-good image SHA.

## Scenarios

### 1. Application host lost (stateless services gone, data intact)
1. Provision a new host with Docker + Compose.
2. Restore `.env.production` from the secret manager.
3. Point `DATABASE_URL`/`REDIS_URL`/`EVENTSTORE_URL` at the surviving datastores (or
   restore them per Backup and Restore).
4. `pull` images (last-good SHA) -> `run --rm migrate` -> `up -d` -> validate health.

### 2. Database lost or corrupted
1. Stop `api`/`worker`/`beat` to prevent writes.
2. Provision a fresh Postgres; restore the latest good dump
   ([Backup and Restore](BACKUP_RESTORE.md)); re-enable `pgvector`.
3. `alembic current` must equal head; if the dump predates a migration, run
   `alembic upgrade head`.
4. Restart services; verify `/health/detailed` and a smoke investigation.

### 3. Bad release / bad migration
1. Roll app back to the previous image SHA.
2. If the release added a **backward-incompatible** migration, restore the DB to the
   pre-migration backup, then redeploy the prior app version.
3. Post-incident: add a forward-only, backward-compatible migration policy
   ([Maintenance](MAINTENANCE.md)).

### 4. EventStoreDB lost
With `AUDIT_FALLBACK_TO_POSTGRES=true`, the Postgres audit chain is authoritative. Rebuild
EventStore from its volume backup or start fresh; new events resume writing.

### 5. Secret compromise
Rotate `SECRET_KEY` (invalidates tokens), provider keys, and `POSTGRES_PASSWORD`; redeploy;
audit access via `request_logs`/`audit_log`. See [Security](SECURITY.md).

### 6. Region/cluster loss
Restore to another region from off-site backups following scenario 2 + 1. Keep backups and
secrets replicated off the primary region to make this possible.

## DR drill checklist (run quarterly)

- [ ] Restore latest Postgres dump into a scratch env.
- [ ] `alembic current` == head; `/health/detailed` green.
- [ ] Audit chain verifies.
- [ ] Stateless services boot on last-good SHA.
- [ ] Record actual RTO/RPO vs targets; file gaps in [Known Issues](KNOWN_ISSUES.md).
