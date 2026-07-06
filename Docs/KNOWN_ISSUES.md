# Known Issues and Workarounds

**Version:** `0.1.0`. Live status of open items. Supersedes the point-in-time
`Skeptic_Engine_Audit_Report.md` (2026-07-03). Items there that are **fixed** are listed in
[Audit Report - section 3](AUDIT_REPORT.md#3-stale-claims-in-skeptic_engine_audit_reportmd-verified-against-current-code)
and [Lessons Learned](LESSONS_LEARNED.md).

Legend: **Verified-open** (confirmed this pass), **Maturity** (known product stage).

## Backend

| # | Status | Issue | Workaround / plan |
|---|--------|-------|-------------------|
| B1 | Verified-open | Some DB calls run synchronously inside `async def` handlers (for example request logging and several investigation/auth routes), which can block the event loop under load. | Move sync DB/IO work behind `run_in_threadpool`/`asyncio.to_thread`, or migrate these surfaces to `AsyncSession`. |
| B3 | Verified-open | pgvector is installed, but knowledge retrieval still stores embeddings as JSON and ranks with Python cosine over deterministic hashed vectors. | Move to a real `Vector` column + ANN index when production semantic retrieval is in scope; keep the current local/offline retriever honest in docs. |
| B5 | Maturity | Evidence connectors partly return placeholder data unless external provider URLs/keys are set. | Configure `*_PROVIDER_URL`/`_API_KEY`; keep `USE_REAL_AGENTS` expectations honest. |

## Frontend

| # | Status | Issue | Workaround / plan |
|---|--------|-------|-------------------|
| F4 | Maturity | No end-to-end (Playwright/Cypress) test suite. | Add E2E coverage for the core investigation flow. |

## Operations / product maturity

| # | Status | Issue | Plan |
|---|--------|-------|------|
| O1 | Maturity | `k8s-deployment.yaml` should be reviewed for probes/resources/replicas before real cluster use. | Validate manifest against [Deployment - Kubernetes](DEPLOYMENT.md#3-kubernetes). |
| O2 | Maturity | Backups are documented but automation is environment-specific. | Wire scheduled backups + monthly restore drills ([Backup and Restore](BACKUP_RESTORE.md)). |
| O3 | Housekeeping | Multiple historical docs (`SETUP_COMPLETE.md`, `BACKEND_FIXES.md`) can read as current. | Consolidated into `docs/`; keep historical files clearly dated. |

> When you close an item, move it to [Lessons Learned](LESSONS_LEARNED.md) with the fix.
