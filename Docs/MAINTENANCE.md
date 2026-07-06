# Maintenance Guide

**Version:** `0.1.0`. Covers routine upkeep, dependencies, branching, releases, testing,
and performance.

## Scheduled background jobs (Celery beat)

Defined in `app/tasks/celery_app.py` (`app.conf.beat_schedule`), running when
`USE_CELERY=true` and `beat` is up:

| Task | Purpose |
|------|---------|
| `tasks.cleanup_old_states` | Prune old investigation state checkpoints |
| `tasks.sync_vector_embeddings` | Keep the RAG index in sync |

Verify they run via Flower or `logs beat`.

## Dependency management

- **Backend:** pinned in `Backend/requirements.txt` (e.g. fastapi 0.115.6, sqlalchemy
  2.0.36, langgraph 0.2.60, celery 5.4.0, anthropic 0.42.0). Update deliberately; run
  `ruff` + `pytest` before merging.
- **Frontend:** `UI/package.json` (Next 15, React 19, TanStack, reactflow, recharts).
  Run `pnpm lint && pnpm typecheck && pnpm test && pnpm build`.
- CI enforces all of the above on every PR (see [CICD.md](CICD.md)).

## Branching strategy

- `main` is deployable; CI runs on PRs into it and on push.
- Use short-lived feature branches; open PRs into `main`.
- Production deploy is a manual `workflow_dispatch` off `main`.

## Release process

1. Merge to `main` -> CI builds/publishes images tagged by commit SHA (+ `latest`).
2. Tag the release in git (e.g. `v0.1.x`).
3. Run `workflow_dispatch` to deploy; the `migrate` job applies `alembic upgrade head`.
4. Validate with the [post-deployment checks](DEPLOYMENT.md#5-post-deployment-validation).
5. Note changes in a CHANGELOG / release notes.

## Migration policy

- Prefer forward-only, backward-compatible migrations (add columns nullable, backfill,
  then enforce) so app rollbacks do not require DB restores.
- Never rely on `create_all` in production; Alembic is the only schema authority there.

## Testing strategy

- **Backend:** `pytest` (sqlite + stub agents; no external services). Ruff correctness
  gate (`E,F,W`).
- **Frontend:** Vitest + Testing Library; ESLint; `tsc --noEmit` typecheck.
- Add tests with features; CI blocks merges on failures.
- Gap: no end-to-end (Playwright/Cypress) suite yet - tracked in
  [Known Issues](KNOWN_ISSUES.md).

## Performance tuning

- API: tune uvicorn workers (`--workers` / `WEB_CONCURRENCY`) and DB pool
  (`DATABASE_POOL_SIZE`, `DATABASE_MAX_OVERFLOW`).
- Throughput: scale Celery worker replicas + `--concurrency`.
- Cost/latency: keep `LLM_CACHE_ENABLED=true`; tune `LLM_MAX_PROMPT_TOKENS`; pick a
  cheaper `DEFAULT_LLM_PROVIDER` / model for lightweight steps.
- DB: add indexes for hot query paths; consider PgBouncer at higher concurrency.

## Housekeeping

- Prune `request_logs` per retention policy.
- Watch `postgres_data` / `eventstore_data` volume growth.
- Keep model IDs (`*_MODEL_*`) current with provider availability.
