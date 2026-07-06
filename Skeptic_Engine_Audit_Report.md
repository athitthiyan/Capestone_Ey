# Skeptic Engine — Bug & Optimization Audit

> **[Historical snapshot - 2026-07-03]** This bug/optimization audit is a point-in-time report. Several findings have since been fixed (global exception handler, real LangGraph invocation, production auth/secret safety checks). Do not read it as current status. Live status: `docs/KNOWN_ISSUES.md`; what changed: `docs/AUDIT_REPORT.md` section 3.

Date: 2026-07-03

Scope: `Backend/` (FastAPI + SQLAlchemy + Celery + Redis + LangGraph) and `UI/` (Next.js 15 / React 19 App Router). Findings are cited with file:line and grouped by severity. "Bugs" break correctness/security; "Optimizations" hurt latency, scalability, or bundle size but aren't outright broken.

---

## BACKEND

### Critical bugs (security/data-loss)

1. **`app/api/routes/websocket.py:14-17`** — WebSocket endpoint has no auth check at all, unlike every REST route (`Depends(get_current_user)`). Anyone can stream live investigation data.
2. **`app/core/config.py:196-232`** — `SECRET_KEY` is only required when `AUTH_REQUIRED=True`, but `AUTH_REQUIRED` defaults to `False`. A misconfigured env can run with no auth and a blank secret key.
3. **`app/api/routes/investigations.py:196-251`** — `delete_all_investigations` is a single destructive endpoint, no confirmation/dry-run, gated only by the auth flag that's disabled by default (#2). Anyone could wipe the case DB.
4. **`app/api/routes/auth.py:37-64`** — `/auth/register` has no rate limiting; distinguishable 409 vs 201 responses enable user enumeration/brute force.
5. **`app/core/security.py:39-43`** — `verify_password` only catches `ValueError`; other exceptions (e.g. `TypeError` on `None`) propagate as raw 500s — no global exception handler in `main.py` to stop stack-trace leakage.

### Correctness bugs

6. **`app/db/session.py:9-11,43`** — Despite being framed as async SQLAlchemy 2.0, the session factory is sync (`Session`/`sessionmaker`), and routes (`investigations.py`, `claims.py`, `auth.py`) call `db.query()`/`db.commit()` inside `async def` handlers with no `run_in_threadpool` — blocks the event loop on every request.
7. **`app/core/request_logging.py:59-78`** — Middleware opens a synchronous `SessionLocal()` and commits on *every* request (including health checks) inside `async def __call__`.
8. **`app/api/routes/investigations.py:670`** — `_celery_broker_available()` does a blocking sync `redis.Redis.from_url(...).ping()` inside an async handler.
9. **`app/evidence_verification/service.py:230-239`, `providers.py:75-86`** — Sync `requests.post/get` to external FX/benchmark providers called directly inside `async def create_investigation` (`investigations.py:146`), no `to_thread` wrap.
10. **`app/agents/crew.py:397-417`** — The compiled LangGraph `StateGraph` is dead code; `executor.py` hand-rolls control flow instead, so declared retry/branch logic never runs.
11. **`app/agents/executor.py:616-618`** — `adjudication.get("confidence", 0.5)` is never clamped to [0,1] before being persisted/used in thresholds — a malformed LLM JSON response can inject out-of-range values.
12. **`app/tasks/celery_app.py:57-77`** — Celery retry/backoff (`max_retries=3`) is unreachable: `executor.py:189-206` swallows all exceptions internally and marks the investigation `FAILED` instead of raising, so task-level retries never fire.
13. **`app/llm/providers/anthropic.py:26-34`, `app/llm/service.py:148-172`** — No retry/backoff at the provider layer despite `tenacity` being a pinned, unused dependency; a transient failure immediately falls through to the next provider instead of retrying.
14. **`app/db/models.py:347-362` vs `app/knowledge/retriever.py:48-71`** — `VectorEmbedding.embedding` is plain `JSON`, not pgvector's `Vector` type. Similarity search is brute-force Python cosine over 64-dim hashed bag-of-words vectors — `pgvector` is installed but never actually used for ANN search.

### Optimizations

15. **`app/api/routes/analytics.py:277-278`** — Trend queries have no `LIMIT` — full unbounded table scans on every dashboard load.
16. **`app/agents/executor.py:405,510,541,618,635,739`** — Multiple `db.commit()` calls per investigation phase instead of one batched transaction.
17. **`app/llm/service.py` / `app/agents/crew.py`** — Challenger/Defender LLM calls run strictly sequentially; no `asyncio.gather` anywhere despite independent agent calls per round.
18. **`app/api/routes/investigations.py:162-193`** — `list_investigations` does `query.count()` + separate `.all()` — two round trips instead of a window-function query.
19. **`app/api/routes/investigations.py:330-420`** — `get_investigation_workspace` issues 7+ sequential queries/service calls with no `asyncio.gather`, defeating the point of a "one-shot" endpoint.
20. **`app/evaluation/ragas.py:102-123`** — Loads all investigations via `.all()` then filters in Python instead of filtering in SQL.
21. **`app/knowledge/retriever.py`** — `_rank_chunks` recomputes ranking over the full corpus on every call; only `load_corpus()` is cached.
22. **`app/db/session.py:33-38`** — Pool is 20+10 overflow, but request-logging middleware (#7) and per-call LLM telemetry sessions (`llm/service.py:311`) each open extra sessions per request — real headroom is smaller than it looks under concurrent runs.
23. **`app/api/routes/reports.py:93`, `intake.py`** — Full ORM rows serialized per request, no caching, no column pruning for list/report views.
24. **Migrations** — `AuditLog.investigation_id` has only a plain index, while `RequestLog`/`LLMCallLog` get composite `(investigation_id, created_at)` indexes — inconsistent indexing for a frequently-filtered audit trail.

---

## FRONTEND

### Bugs

1. **`services/cases.service.ts:309-317,351-359`** — `createInvestigations`/`executeInvestigations` loop with sequential `await` instead of `Promise.all`. A batch intake upload or bulk case run is fully serialized, and one failure mid-loop aborts everything after it with no partial-success reporting.
2. **`hooks/use-investigation-realtime.ts:239-249`** — `onclose` always reconnects (capped backoff, no max-retry count) even on intentional server closes (case complete, unauthorized) — infinite reconnect loop every 10s.
3. **`features/investigations/case-workspace-view.tsx:239-249`** — A 10s polling `setInterval` runs *in addition to* the WebSocket subscription that already invalidates the same queries — duplicate network traffic while a pipeline is running.
4. **`features/investigations/case-workspace-view.tsx:410`** — `error={null}` is hardcoded for `EvidenceVerificationCard` even though `workspaceQuery.error` exists and is used elsewhere in the same component — verification fetch errors are silently swallowed.
5. **`components/forms/settings-form.tsx:27-29`** — `useEffect(() => reset(settings), [reset, settings])` re-runs whenever `settings` gets a new object reference (including right after a successful save triggers `invalidateQueries`), discarding any in-progress unsaved edits.
6. **No per-route `loading.tsx`/`error.tsx`** — None of the 18 route segments under `app/(app)/*` have segment-level loading/error boundaries; a render error in any feature view bubbles to the root instead of being scoped, and there's no streaming fallback.
7. **`features/intake/intake-view.tsx:104-144`** — `window.confirm(...)` gates a "delete everything" action — blocking, not keyboard-accessible, no typed confirmation for a destructive action in an audit tool.
8. **`services/api.ts:152-159`** — On a 401, retries once; if the retry also 401s it's handled but `tokenPromise` is left null with no backoff, so every subsequent request re-pays a full token round trip.
9. **`hooks/use-active-investigation-id.ts:7`** — Picks the first investigation from an unsorted API response as "active" — no explicit ordering, so the "active case" can silently change between reloads.
10. **`components/agents/agent-workflow.tsx:105-115`** — Edge IDs are derived positionally (`steps[index]` against a sliced array) rather than from `step.id` — works today but will break if step reordering is ever added.

### Optimizations

11. **`components/tables/data-table.tsx`, `components/intake/flagged-rows-table.tsx`** — No pagination or virtualization. `DataTable` wires `getSortedRowModel` but not `getPaginationRowModel`; `useInvestigations` defaults to `limit: 500` and renders straight into the table; `FlaggedRowsTable` has no cap at all — thousands of rows can mount synchronously.
12. **`hooks/use-analytics.ts:48-96`** — 5 separate hooks (`useLlmSummary`, `useLlmByProvider`, `useLlmByModel`, `useLlmRecentCalls`, `useLlmCostTrends`) each poll every 30s independently — 5x the request volume for what's logically one "LLM telemetry" fetch.
13. **`hooks/use-cases.ts:23-29`** — Query key includes `limit`, so `useInvestigations({limit:500})` and `useInvestigations({limit:1})` (dashboard vs. active-case lookup) are cached as unrelated entries instead of deriving from one cached fetch — duplicate fetches for overlapping data.
14. **`features/investigations/case-workspace-view.tsx:143-193`** — `workflowFromInvestigation` is wrapped in `useMemo` keyed on `investigation`, but `investigation` is a new object reference on every poll/WebSocket message even when field values are unchanged — the memo never actually hits, so the workflow graph recomputes constantly.
15. **`components/agents/agent-workflow.tsx:86-146`** — Because of #14, ReactFlow's `nodes`/`edges` recompute and re-trigger the `fitView` effect on every background refresh, not just on real state changes.
16. **`store/ui-state.tsx`** — One context holds both `commandOpen` and `sidebarOpen`; toggling either re-renders every consumer (`AppHeader`, `CommandOverlay`, `SidebarContent`) since they're bundled in one provider value.
17. **`next.config.ts`** — No bundle analyzer, no `images` remote-pattern config, no evidence of `next/image` use for attachment thumbnails — worth adding given recharts + reactflow + react-table are all bundled dependencies.
18. **`components/dashboard/case-trend-chart.tsx`, `components/dashboard/risk-distribution.tsx`, `components/evaluation/*`** — Only `AgentWorkflow`, `CaseTrendChart`, and `AnalyticsCharts` are confirmed lazy-loaded via `next/dynamic`; other chart-heavy components should be checked for the same treatment.
19. **`package.json:27-34`** — All deps use caret ranges with no exact-version pinning policy — worth tightening for a compliance/audit product where reproducible builds matter.
20. **`features/dashboard/dashboard-view.tsx:31-42,79-81`** — `metricIcons` is matched to `data.metrics` positionally with a fallback icon — if the backend ever reorders/changes metric count, icons silently misalign with labels instead of being keyed by `metric.label`.

---

## Suggested priority order
1. Fix the auth gaps (backend #1-4) and the blocking-sync-in-async pattern (backend #6-9) — these are security and stability issues, not just style.
2. Fix the dead-letter retry logic (backend #10,12,13) so failures actually get retried instead of silently failing.
3. Add pagination/virtualization to frontend tables (#11) and stop the duplicate WS+polling refresh (#2,3) — biggest real-world latency/cost wins.
4. Everything else (indexing, caching, bundle size) can be tackled incrementally.
