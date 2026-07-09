# Engineering Challenges and Lessons Learned

**Version:** `0.1.0`. Every entry below is **evidence-backed** by the repository
(`Backend/BACKEND_FIXES.md`, git history, Dockerfile/config comments,
`GL_Guardian_Audit_Report.md`). Reasonable inferences are labelled **[Inference]**;
everything else is verified from those sources.

## How to read this

Each challenge: Problem -> Symptoms -> Root cause -> Investigation -> Solution ->
Alternatives -> Decision -> Lesson -> Prevention.

---

## 1. App crashed on import: reserved `metadata` column (verified)

- **Problem:** `VectorEmbedding.metadata` used a name reserved by SQLAlchemy's declarative API.
- **Symptoms:** `InvalidRequestError` at import; the whole app failed to start.
- **Root cause:** `metadata` is owned by the declarative base.
- **Investigation:** Import smoke test surfaced it immediately (`BACKEND_FIXES.md` #1).
- **Solution:** Renamed the attribute to `meta` (mapped to a `meta` column).
- **Alternatives:** Use a different ORM base - rejected as overkill.
- **Decision:** Rename.
- **Lesson:** Avoid ORM-reserved names in models.
- **Prevention:** Import smoke test in CI (`pytest` collects the app).

## 2. SQLAlchemy 2.0 raw SQL and pooling breakages (verified)

- **Problem:** `db.execute("SELECT 1")` and NullPool + pool kwargs.
- **Symptoms:** `ObjectNotExecutableError`; `TypeError` on the SQLite branch.
- **Root cause:** SQLAlchemy 2.0 requires `text()`; `NullPool` rejects pool sizing args.
- **Solution:** Wrap raw SQL in `sqlalchemy.text()`; pass pool args only for PostgreSQL.
- **Lesson:** 2.0 is stricter than 1.x; test both the sqlite (test) and pg (runtime) paths.
- **Prevention:** Tests run on sqlite; runtime on pg - both exercised.

## 3. Real-time events never reached the browser (verified) 

- **Problem:** Worker-emitted events did not reach WebSocket clients.
- **Symptoms:** UI showed no live progress during investigations.
- **Root cause:** The executor runs in the **Celery worker process**; the in-memory
  `connection_manager` lives in the **API process** - different memory space.
- **Investigation:** Traced the emit path across processes (`BACKEND_FIXES.md` #6).
- **Solution:** Added `redis_bus.py` (Redis pub/sub). Worker publishes to
  `investigation_events:{id}`; the WS endpoint subscribes and forwards.
- **Alternatives:** Run agents in-process (loses async isolation) - kept as the
  `USE_CELERY=false` mode instead.
- **Decision:** Redis pub/sub bridge, gated by `USE_REDIS_EVENTS`.
- **Lesson:** In multi-process systems, in-memory fan-out cannot cross the process boundary.
- **Prevention:** Documented in [Architecture](ARCHITECTURE.md#5-real-time-updates) and
  [Troubleshooting](TROUBLESHOOTING.md).

## 4. Debate could infinite-loop (verified)

- **Problem:** The Challenger/Defender cycle could loop forever.
- **Root cause:** `route_debate` read `debate_round` but nothing incremented it in the cycle.
- **Solution:** Increment `debate_round` in the defender node; added tests proving
  termination. Bounded by `MAX_DEBATE_ROUNDS`.
- **Lesson:** Every cyclic graph edge needs a guaranteed progress variable + a hard bound.
- **Prevention:** Termination test in the suite; recursion limit in the executor.

## 5. The agent graph was dead code (verified; note this is now fixed)

- **Problem:** The LangGraph graph was compiled but never invoked; the executor used
  `asyncio.sleep` + hardcoded verdicts.
- **Solution:** The executor now invokes the real agent nodes when `USE_REAL_AGENTS=true`
  (off-thread via `asyncio.to_thread`) and persists evidence/transcripts/claims.
- **Lesson:** Compiling a graph is not running it; wire and test the real invocation.
- **Note:** The 2026-07-03 `GL_Guardian_Audit_Report.md` still describes this as dead
  code - that description is now **stale** (see [Audit Report](AUDIT_REPORT.md#3)).

## 6. Non-root container could not run its entrypoints (verified via git)

- **Problem:** After adding `USER appuser`, `uvicorn`/`celery`/`alembic` failed with
  "Permission denied".
- **Root cause:** `pip install --user` puts console scripts in `/root/.local`, which is
  `0700` and unreachable by a non-root user.
- **Solution:** Install dependencies **system-wide** so `/usr/local/bin` scripts are
  world-executable (commit `6ea2ff0`; see the comment block in `Backend/Dockerfile`).
- **Lesson:** Non-root images and `pip --user` do not mix; install to `/usr/local`.
- **Prevention:** Documented inline in the Dockerfile.

## 7. Audit hash chain was fake (verified)

- **Problem:** `verify_chain_integrity` computed hashes and discarded them.
- **Solution:** Real SHA-256 chain (each row hashes the previous hash + per-investigation
  `sequence`); a test tampers a row and confirms detection.
- **Lesson:** For a compliance feature, prove tamper-detection with a test, not a comment.

## 8. Wrong/abandoned EventStore client and port (verified)

- **Problem:** Imported the unmaintained `esdb` package; compose used legacy TCP port 1113.
- **Solution:** Rewrote against the maintained `esdbclient`, lazy-imported, with a Postgres
  hash-chain **fallback** when EventStore is down; compose uses gRPC port 2113.
- **Lesson:** Pick maintained clients; design a graceful fallback for optional infra.

## 9. Pydantic v2 migration and list env-var parsing (verified)

- **Problem:** Deprecated `class Config`; list env vars failed to parse.
- **Solution:** `SettingsConfigDict` + a validator accepting JSON lists **or** CSV for
  `CORS_ORIGINS`/`ALLOWED_HOSTS` (and other list settings).
- **Lesson:** Env vars are strings; explicitly define list coercion.

## 10. API design: request bodies and failure states (verified)

- **Problem:** `POST /investigations` took query params; failures were marked `CLOSED`.
- **Solution:** Added Pydantic `schemas.py` (validated JSON body, HTTP 201) and a real
  `FAILED` status + `error_message` with rollback.
- **Lesson:** Model the failure path as a first-class state, not a synonym for "done".

## 11. Managed-platform config drift [Inference, evidence: git + memory]

- **Problem:** Railway runs api/worker/beat as separate services that must share DB/Redis.
- **Evidence:** `add railway config-as-code for api/worker/beat` (commit `a453a74`); project
  memory notes a shared-variable reference gotcha.
- **Lesson:** With split services, verify each resolves the **same** shared variables, or
  the worker/beat will connect to a different backend than the API.
- **Prevention:** Documented in [Deployment - Railway](DEPLOYMENT.md#2-railway-managed---three-services-from-one-image).

## 12. CI stabilization [Inference, evidence: git]

- **Evidence:** commits `86af044 fix: CI test failures unrelated to prior feature work`,
  `cced496 fix lint`.
- **Lesson:** Keep the correctness gate (ruff `E,F,W` + pytest) green independently of
  feature work; flaky/unrelated failures erode trust in CI.

## 13. LLM fallback should not replace same-provider retry (verified)

- **Problem:** The historical audit reported provider failures falling through to the next
  provider without retry/backoff.
- **Current solution:** `LLMService.complete` wraps provider calls in `tenacity.Retrying`
  for transient timeout, network, and provider-error failures before trying fallback.
- **Regression guard:** `Backend/tests/test_llm_service.py` proves a transient provider
  error retries the same provider before succeeding.
- **Lesson:** Fallback is a resilience layer, not a substitute for retrying transient
  failures on the selected provider.

## 14. Bounded analytics and tables prevent dashboard over-fetch (verified)

- **Problem:** Dashboard analytics and review tables can turn routine page loads into
  large synchronous render/query work when data volume grows.
- **Solution:** `/analytics/trend` now has a bounded `limit` parameter, the shared
  `DataTable` uses TanStack pagination, and the intake flagged-row preview renders one
  page at a time.
- **Regression guard:** Backend and frontend tests assert the limit/pagination behavior.
- **Lesson:** Operational dashboards should have explicit row limits and page models by
  default; "small demo data" should not define production behavior.

## 15. Realtime clients need intentional close semantics (verified)

- **Problem:** The historical audit reported WebSocket reconnects and polling as possible
  duplicate refresh sources.
- **Current solution:** `useInvestigationRealtime` caps reconnect attempts and respects
  normal/policy close codes; the case workspace keeps polling only as a slower fallback
  safety net while realtime events drive primary invalidation.
- **Lesson:** Treat WebSocket closure codes as part of the protocol. A reconnect loop is
  only useful while the server is actually inviting reconnection.
