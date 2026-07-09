# Documentation Audit Report and Gap Analysis

**Date:** 2026-07-06
**Method:** Every existing document was compared line-by-line against the current
implementation. Source code is the single source of truth. Verified facts are cited to
`path:symbol`. This report covers Phase 2 (audit) and Phase 4 (gap analysis) of the
documentation program.

---

## 1. Summary

The repository was already relatively well documented, but documentation had drifted
from the code in several concrete ways, and it lacked an operations layer (runbook,
incident response, DR, backup, monitoring) required for a production/enterprise project.

- **Documents reviewed:** 11 Markdown files + 5 design PDFs + 1 architecture diagram.
- **Correct as-is:** 4
- **Needs update:** 6
- **Superseded / now misleading:** 1 (`GL_Guardian_Audit_Report.md`)
- **Newly created (Phase 4):** 20 files under `docs/`.

The single most important finding: **`GL_Guardian_Audit_Report.md` (dated 2026-07-03)
is now partially stale** and should not be read as current. Several defects it lists have
since been fixed in code (see section 3).

---

## 2. Per-document audit

Legend for Status: **Correct** (matches code), **Update** (drifted, fixed or needs fix),
**Superseded** (replaced by newer docs), **New** (created in this pass).

| Document | Status | Issues found | Recommended fix | Priority |
|----------|--------|--------------|-----------------|----------|
| `README.md` (root) | Correct | Accurately lists FastAPI + LangGraph + Next.js stack and layout. Minor: does not link the new `docs/` set. | Add a link to `docs/README.md`. | Low |
| `Backend/README.md` | **Update** | "Project Structure" lists a **flat, pre-refactor layout** (`config.py`, `db_session.py`, `db_models.py`, `websocket_manager.py`, `agent_crew.py`, `investigation_executor.py`, `celery_config.py`, `eventstore_client.py`). The code is actually the `app/` package (see `Backend/STRUCTURE.md`). | Structure section rewritten in place to match `app/` package. | **High** |
| `Backend/STRUCTURE.md` | Correct | Matches the real `app/` package tree and module entrypoints. | None. | - |
| `Backend/QUICKSTART.md` | Correct | "7 services" matches default compose (postgres, redis, eventstore, api, worker, beat, flower; pgAdmin is behind the `tools` profile). Endpoints correct. | Cross-link `docs/LOCAL_DEVELOPMENT.md`. | Low |
| `Backend/PREREQUISITES.md` | Update | Item 3 says migrations are "scaffold" and item 5 says the UI "uses mock data"; both are now further along (5 Alembic revisions exist; UI has a live API service layer). Item 2 mentions only Anthropic; five providers now exist. | Note as historical planning doc; superseded by `docs/LOCAL_DEVELOPMENT.md` + `docs/ENVIRONMENT_VARIABLES.md`. | Medium |
| `Backend/LOCAL_PRODUCTION.md` | Correct | Matches `docker-compose.local-infra.yml` intent (Redis + EventStoreDB + real agents on top of local Postgres). Contains machine-specific absolute paths. | Keep; generic version is `docs/LOCAL_DEVELOPMENT.md`. | Low |
| `Backend/SETUP_COMPLETE.md` | Update | Point-in-time "setup done" note; risks being read as current state. | Treat as historical; superseded by `docs/`. | Low |
| `Backend/BACKEND_FIXES.md` | Update | Point-in-time changelog of fixes; useful history. | Fold verified items into `docs/LESSONS_LEARNED.md`. | Low |
| `DEPLOYMENT_GUIDE.md` (root) | Update | Free-tier oriented and still valid, but pre-flight says API keys are "committed to the repo" (a historical warning) and predates `docker-compose.production.yml` / Railway configs / the CI deploy job. | Superseded for production by `docs/DEPLOYMENT.md`; keep as the free-tier quickstart and cross-link. | Medium |
| `Docs/PRODUCTION_DEPLOYMENT.md` | Correct | Accurately describes `.github/workflows/ci-cd.yml` and the production compose flow (SSH, GHCR, `alembic upgrade head`). | Cross-link `docs/CICD.md` + `docs/DEPLOYMENT.md`. | Low |
| `UI/README.md` | Update | Verify against `UI/package.json` scripts and `NEXT_PUBLIC_*` env; ensure it documents the token vs username/password auth options. | Reconcile with `docs/LOCAL_DEVELOPMENT.md`. | Medium |
| `GL_Guardian_Audit_Report.md` | **Superseded** | Bug/optimization audit dated 2026-07-03; several findings are now fixed (see section 3). Reading it as current is misleading. | Add a banner noting it is a point-in-time snapshot; live status lives in `docs/KNOWN_ISSUES.md`. | **High** |
| `Docs/*.pdf` (PRD, HLD, LLD, Design, Sample output) | Correct (design intent) | Design-time artifacts; not code-verified but not contradicted. | Leave as-is; `docs/ARCHITECTURE.md` is the code-verified companion. | Low |
| `Docs/Architecture/GL_Guardian_Architecture.(png|svg)` | Correct | Architecture image; keep. `docs/ARCHITECTURE.md` adds Mermaid equivalents. | None. | Low |

---

## 3. Stale claims in `GL_Guardian_Audit_Report.md` (verified against current code)

These items from the 2026-07-03 audit no longer reflect the code and must not be quoted
as current:

| Old claim | Current reality | Evidence |
|-----------|-----------------|----------|
| "No global exception handler in `main.py`." | A global handler exists and returns `{detail, request_id}`, hiding internals unless `DEBUG`. | `Backend/app/main.py` `unhandled_exception_handler` |
| "The compiled LangGraph `StateGraph` is dead code; `executor.py` hand-rolls control flow." | The executor builds and routes a real graph (`_build_graph`, `_get_graph`, `_route_after_verification`, `_route_after_confidence_gate`). | `Backend/app/agents/executor.py` |
| "`SECRET_KEY` can run blank while `AUTH_REQUIRED=false`." | Config generates a per-process key if blank, and **requires** an explicit >=32-char key when `ENV=production`. | `config.py` `_production_safety_checks` |
| "Anyone could wipe the DB via `delete_all_investigations` (auth off by default)." | Production forces `AUTH_REQUIRED=true` (`ENV=production` safety check); still verify route-level guard. | `config.py` `_production_safety_checks` |
| "Provider-layer retry/backoff may not be wired." | Provider calls are retried with tenacity for transient timeout/network/provider errors before fallback. | `Backend/app/llm/service.py`; `Backend/tests/test_llm_service.py` |
| "Analytics trend queries may lack `LIMIT`." | `/analytics/trend` now accepts a bounded `limit` and applies it to investigation and claim trend inputs. | `Backend/app/api/routes/analytics.py`; `Backend/tests/test_pages.py` |
| "Large tables may lack pagination/virtualization." | Shared investigation tables use TanStack pagination, and intake flagged-row previews render one page at a time. | `UI/components/tables/data-table.tsx`; `UI/components/intake/flagged-rows-table.tsx` |
| "WebSocket reconnect/polling can duplicate refresh work." | Reconnects are capped and close-code aware; the workspace poll is a slower fallback while realtime events drive invalidation. | `UI/hooks/use-investigation-realtime.ts`; `UI/features/investigations/case-workspace-view.tsx` |

Items from that report that **remain open** are tracked in
[Known Issues and Workarounds](KNOWN_ISSUES.md).

---

## 4. Gap analysis - documentation that was missing

An enterprise/production project needs an operations layer that did not exist. Created in
this pass under `docs/`:

| Missing area | New document |
|--------------|--------------|
| Consolidated, role-based entry point | `docs/README.md` |
| Code-verified architecture + data flow | `ARCHITECTURE.md` |
| Complete environment variable reference | `ENVIRONMENT_VARIABLES.md` |
| API surface reference | `API_REFERENCE.md` |
| Security and secrets | `SECURITY.md` |
| Unified local dev guide | `LOCAL_DEVELOPMENT.md` |
| Unified deployment guide (compose/Railway/k8s/cloud) | `DEPLOYMENT.md` |
| CI/CD guide | `CICD.md` |
| Infrastructure guide | `INFRASTRUCTURE.md` |
| Operations runbook | `RUNBOOK.md` |
| Monitoring and logging | `MONITORING_LOGGING.md` |
| Incident response | `INCIDENT_RESPONSE.md` |
| Troubleshooting | `TROUBLESHOOTING.md` |
| Backup and restore | `BACKUP_RESTORE.md` |
| Disaster recovery | `DISASTER_RECOVERY.md` |
| Maintenance | `MAINTENANCE.md` |
| Known issues / workarounds | `KNOWN_ISSUES.md` |
| Lessons learned | `LESSONS_LEARNED.md` |
| Final validation + recommendations | `VALIDATION_REPORT.md` |

---

## 5. Changes applied in place (Phase 3)

Per the chosen strategy (rewrite stale docs in place), the following existing files were
edited. Each edit is marked in-file with an HTML comment `<!-- Updated 2026-07-06 ... -->`.

- `Backend/README.md` - "Project Structure" rewritten to the real `app/` package; quick
  start reconciled with `docker-compose.yml`.
- `GL_Guardian_Audit_Report.md` - banner added noting it is a 2026-07-03 snapshot and
  pointing to `docs/KNOWN_ISSUES.md` for live status.

See [VALIDATION_REPORT.md](VALIDATION_REPORT.md) for the final reproducibility check.
