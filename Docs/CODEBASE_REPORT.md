# GL Guardian — Codebase Report

**Generated:** 2026-07-09 · **Version:** v0.1.0 · **Scope:** every source file, per-directory, with its purpose.

**At a glance:** 96 Python files (~16,450 LOC) + 170 TypeScript/TSX files (~13,200 LOC), plus 24 operations documents, 6 Alembic migrations, k6/Python load tests, and CI/CD. Backend is FastAPI + SQLAlchemy 2.0 + LangGraph; frontend is Next.js 15 / React 19; data plane is PostgreSQL (+pgvector), Redis, optional EventStoreDB.

---

## 1. Repository layout

| Path | What lives here |
|---|---|
| `Backend/` | FastAPI application, agent crew, LLM gateway, tests, migrations, sample data |
| `UI/` | Next.js 15 workspace app (App Router), feature views, API services, hooks |
| `Docs/` | 24-document operations/design handbook + architecture diagram assets |
| `load-tests/` | k6 scripted profiles + comprehensive Python API/agent load runner |
| `presentation/` | Decks, scripts, brand style guide, storyboard for the capstone presentation |
| `.github/workflows/` | CI/CD pipeline (lint → test → build → GHCR images → manual deploy) |
| `.kiro/specs/` | Spec-driven development artifacts (requirements, design, tasks) |
| `archive/` | Historical prototype and audit-report snapshots |

Root files: `README.md` (project overview + logo), `DEPLOYMENT_GUIDE.md` (free-tier Vercel/Railway/Neon walkthrough), `PROJECT_ANALYSIS.md` (deep project self-analysis), `docker-compose.production.yml` (full production stack reference), `production.env.example` (prod env template), `LICENSE` (MIT).

---

## 2. Backend — `Backend/app/`

### 2.1 Application core

| File | LOC | Purpose |
|---|---|---|
| `main.py` | 176 | FastAPI application factory: middleware, CORS, rate limiting, Prometheus instrumentation, lifespan startup (schema check, default-user seed, production safety assertions), router wiring. |
| `core/config.py` | 269 | Pydantic Settings for every environment: DB/Redis URLs, feature flags (`USE_CELERY`, `USE_REDIS_EVENTS`, `USE_EVENTSTORE`, `USE_REAL_AGENTS`), model tiers (`claude-sonnet-5` reasoning / `claude-haiku-4-5` lightweight), thresholds (materiality $50k, confidence 0.70, max 2 debate rounds). |
| `core/security.py` | 160 | bcrypt password hashing, HS256 JWT issue/verify, OAuth2 password-bearer dependency, role checks (`require_elevated_role`, `can_view_all_transactions`), default-user seeding. |
| `core/request_logging.py` | 97 | Middleware persisting every HTTP request to `request_logs` (method, path, status, latency, request-id correlation). |
| `core/governance_store.py` | 130 | Persistence for runtime governance settings edited on the Settings page (confidence bands, SoD toggle, debate rounds). |
| `core/metrics.py` | 69 | Prometheus registry: `gl_guardian_*` counters/histograms — LLM calls/tokens/cost, investigations by outcome, phase durations, debate rounds, verification results. |
| `core/rate_limit.py` | 40 | Fixed-window rate limiter guarding auth endpoints (token 10/window, register 5/window). |
| `db/models.py` | 474 | All 14 SQLAlchemy models: `investigations` (case spine), `investigation_states` (checkpoints), `debate_transcripts`, `evidence_artifacts`, `verification_claims`, `third_party_evidence_verifications`, `audit_log` (hash chain), `request_logs`, `llm_call_logs`, `ragas_evaluation_results`, `review_queue`, `vector_embeddings` (pgvector), `runtime_settings`, `users`, `employee_transactions`. |
| `db/session.py` | 170 | Engine/session factory, connection pooling, SQLite-vs-Postgres handling, `get_db_session` dependency. |
| `schemas/__init__.py` | 474 | Every Pydantic request/response schema for the API surface (auth, investigations, reviews, analytics, employee transactions, evaluation…). |

### 2.2 Agent crew — `app/agents/`

| File | LOC | Purpose |
|---|---|---|
| `crew.py` | 424 | LangGraph `StateGraph` definition: Supervisor, Evidence, Challenger, Defender, Adjudicator, Verifier nodes; `InvestigationState` TypedDict; `route_debate` conditional edge enforcing `max_debate_rounds` (2); prompt construction per role with model-tier routing. |
| `executor.py` | 1,209 | The heart of the pipeline. Orchestrates a full investigation run: builds the graph with `MemorySaver` checkpointing (thread_id = investigation id), executes phases (evidence → debate → adjudication → verification → confidence gate), emits WebSocket events per step, persists transcripts/evidence/claims, runs the third-party verification, applies the confidence-gate routing (risk ≥ medium OR confidence < 0.70 OR unclean third-party ⇒ human review), upserts the review queue, generates the report, and appends hash-chained audit events. Includes deterministic stub-agent mode (`USE_REAL_AGENTS=false`). |

### 2.3 API routes — `app/api/routes/` (16 modules)

| File | LOC | Purpose |
|---|---|---|
| `investigations.py` | 765 | Investigation CRUD, execute (sync/Celery), stats summary, sub-resources (debate, audit, state), bulk delete of intake-imported or all cases. |
| `analytics.py` | 617 | Aggregations for dashboards: case trends, agent accuracy, KPIs, request telemetry, LLM cost by provider/model, recent calls. |
| `agents.py` | 343 | Agent health/workflow telemetry derived from persisted investigation state. |
| `reviews.py` | 336 | Human review queue: list, approve/reject/request-evidence decisions with SoD enforcement, review history, `resume()` of interrupted runs. |
| `employee_transactions.py` | 149 | Employee-linked transaction CRUD with RBAC (own-vs-all), filtering, sorting, soft archive. |
| `claims.py` | 132 | Claim-level third-party evidence verification endpoints (verify, preview, fetch result). |
| `evaluation.py` | 131 | RAGAS evaluation endpoints (summary, per-case scores). |
| `intake.py` | 113 | Intake summary reconstructed from persisted `owner="intake"` investigations (file name, rule stats, flagged rows). |
| `reports.py` | 102 | Report artifacts derived from completed investigations (MD/HTML). |
| `auth.py` | 79 | OAuth2 token login, registration, `/me` — all rate-limited. |
| `websocket.py` | 76 | `/ws` realtime route; subscribes clients to investigation event streams. |
| `settings.py` | 72 | Runtime governance settings GET/PUT for the UI. |
| `knowledge.py` | 63 | Knowledge-base sources/chunks/search/reindex backing the Evidence agent RAG. |
| `audit.py` | 41 | Global recent audit events across all cases. |
| `health.py` | 38 | `/health` and `/health/detailed` (DB connectivity, active runs, WS connections). |

### 2.4 LLM gateway — `app/llm/`

| File | LOC | Purpose |
|---|---|---|
| `service.py` | 375 | Orchestration: request typing → model routing → same-provider tenacity retry → ordered 5-provider fallback → response cache → per-call cost/latency logging to `llm_call_logs`. |
| `routing.py` | 105 | Quality guardrails: critical request types (adjudication, verification, report, compliance) always route to reasoning-class models; prompt compaction never touches instructions. |
| `types.py` | 115 | Shared request/response/provider-error dataclasses. |
| `settings_store.py` | 166 | Runtime LLM settings persistence + provider status for the Settings UI. |
| `pricing.py` | 73 | Per-model $/1M token pricing table and cost calculation. |
| `tokenization.py` | 62 | Dependency-free token estimation and prompt trimming. |
| `cache.py` | 41 | Small in-process cache for explicitly safe repeat calls. |
| `providers/base.py` | 71 | Shared HTTP helpers + error normalization. |
| `providers/anthropic.py` | 94 | Anthropic Messages API client. |
| `providers/openai.py` / `gemini.py` / `groq.py` / `deepseek.py` | 66–72 | OpenAI-compatible chat-completion clients per provider. |

### 2.5 Evidence & knowledge

| File | LOC | Purpose |
|---|---|---|
| `evidence_verification/service.py` | 665 | Third-party verification engine: normalizes a claim (category inference from text: fx/gst/fuel/flight/hotel/cab/food; GSTIN regex; route and litres parsing), selects a provider, applies tolerance rules, persists an audit-friendly verification row. Statuses: VERIFIED / FLAGGED / API_UNAVAILABLE / NEEDS_MANUAL_REVIEW — never fabricates benchmarks. |
| `evidence_verification/providers.py` | 976 | Concrete adapters: Frankfurter FX (keyless, live), IndianAPI fuel prices, Aviationstack flights, GSTINCheck registry, Duffel flights + stays. |
| `knowledge/retriever.py` | 245 | Local hybrid retriever over the curated policy corpus (keyword + embedding). |
| `knowledge/corpus.json` | 196 | Curated policy KB: approval matrices, SOPs, vendor/related-party reference data. |
| `audit/eventstore.py` | 318 | Immutable audit trail: EventStoreDB streams when enabled, otherwise Postgres SHA-256 hash chain (`hashₙ = SHA-256(hashₙ₋₁ + evtₙ)`) with per-investigation sequences and `verify_chain_integrity()`. |

### 2.6 Evaluation, realtime, tasks

| File | LOC | Purpose |
|---|---|---|
| `evaluation/ragas.py` | 171 | RAGAS metric computation for crew outputs (faithfulness, relevance). |
| `evaluation/ragas_judge.py` | 376 | Real-time LLM-judge scoring pipeline, including ground-truth comparison from reviewer fields. |
| `realtime/websocket_manager.py` | 190 | WS connection pooling, per-investigation broadcast, reconnection handling. |
| `realtime/redis_bus.py` | 72 | Redis pub/sub fan-out so events reach WS clients across processes (flag-gated; same-process bus fallback). |
| `tasks/celery_app.py` | 380 | Celery app + tasks: async investigation execution, evidence retrieval, report generation, beat schedules (flag-gated). |
| `employee_transactions/service.py` | 220 | Business logic: RBAC access predicates, filtered/sorted queries, create/update, soft archive; unknown `employee_id` → 404. |

### 2.7 Backend scripts, tests, migrations

**`Backend/scripts/`** — `check_local_stack.py` (preflight for local prod-like stack), `ensure_schema.py` (deploy-time schema bootstrap), `production_smoke.py` (live API/UI smoke checks), `probe_duffel.py` / `probe_flight_api.py` / `probe_fuel_api.py` / `probe_gst_api.py` (one-off provider probes), `seed_employee_transactions.py` (API-driven demo data seeder), `create_local_db.sql` + `create_sample_ledger_table.sql` (pgAdmin local setup).

**`Backend/tests/`** — 13 modules, 95 tests: `test_agents.py` (state machine, termination proof), `test_audit.py` (hash chain incl. tamper-detection proof), `test_executor.py` (end-to-end with stub agents), `test_llm_service.py` (routing/fallback/cost), `test_evidence_verification.py`, `test_employee_transactions.py`, `test_endpoints.py`, `test_pages.py`, `test_evaluation.py`, `test_ragas_judge.py`, `test_ground_truth_scoring.py`, `test_api.py`, `test_auth.py`, plus `conftest.py` fixtures.

**`Backend/migrations/`** — Alembic env + 6 versions: initial schema (2026-06-25) → third-party verifications → request logs → LLM settings/call logs → RAGAS realtime scoring → employee transactions (2026-07-07).

**`Backend/sample_data/`** — `sample_gl_1000.csv` (+`_diff`) synthetic ledgers; `sample_gl_fx_verifiable.csv` (100 rows tuned for live FX checks); `sample_gl_50_live_demo.csv`/`.xlsx` (50-row demo exercising every intake rule and every third-party provider, FX math tied to ECB 2026-07-08 rates).

**Backend root** — `Dockerfile` (multi-stage, non-root), `docker-compose.yml` + `docker-compose.local-infra.yml` (dev stacks), `k8s-deployment.yaml` (manifest, certification pending), `railway.api/worker/beat.json` (config-as-code), `alembic.ini`, `pyproject.toml`, `requirements.txt`, `.env.example`, and docs (`README`, `QUICKSTART`, `PREREQUISITES`, `LOCAL_PRODUCTION`, `STRUCTURE`), plus `history/` (BACKEND_FIXES, SETUP_COMPLETE — engineering log).

---

## 3. Frontend — `UI/`

### 3.1 App Router — `app/`

`layout.tsx` (root metadata "GL Guardian - Automated Audit" + providers), `icon.svg` (favicon, brand shield), `page.tsx` (redirect to dashboard), `error/loading/not-found` boundaries. Under `(app)/`: one thin `page.tsx` per surface — dashboard, intake, investigations (+ `[caseId]` workspace), workspace, debate, evidence, verification (fact check), human-review, review, replay, reports, audit-logs, analytics, evaluation (quality scores), knowledge-base, employee-transactions, settings, unauthorized — each delegating to a feature view.

### 3.2 Feature views — `features/` (the real pages)

| File | LOC | Purpose |
|---|---|---|
| `intake/intake-view.tsx` | 478 | Upload CSV/TSV/XLSX → client-side rule pre-filter → flagged-rows table → "Create cases & run crew" (creates investigations, starts execution, imports employee transactions, redirects to workspace). Also delete/replace imported data flows. |
| `investigations/case-workspace-view.tsx` | 542 | The case workspace: live agent progress (WebSocket), debate transcript, evidence, verification, gate result, review actions. |
| `employee-transactions/employee-transactions-view.tsx` | 296 | Filterable/sortable transaction ledger per employee with stat cards and create/edit dialog. |
| `debate/debate-view.tsx` | 246 | Challenger/Defender/Adjudicator transcript viewer per round. |
| `analytics/analytics-view.tsx` | 222 | Trends, KPIs, request telemetry, LLM cost panels. |
| `investigations/investigations-view.tsx` | 201 | Case list with risk/status/confidence columns. |
| `evidence/evidence-view.tsx` | 183 | Evidence cards with citations and third-party verification results. |
| `replay/replay-view.tsx` | 177 | Step-by-step replay of a checkpointed investigation. |
| `knowledge-base/knowledge-base-view.tsx` | 177 | Policy KB sources, chunks, search, reindex. |
| `audit/audit-logs-view.tsx` | 125 | Hash-chain explorer with integrity banner. |
| `dashboard/dashboard-view.tsx` | 114 | Risk distribution, case trends, agent health, cost summary. |
| `verification/verification-view.tsx` | 100 | Claim-level grounding QA + RAGAS scores. |
| `review/human-review-view.tsx` | 97 | Review queue with approve/escalate/request-evidence. |
| `evaluation/evaluation-view.tsx` | 94 | RAGAS scorecards. |
| `reports/reports-view.tsx` | 82 | Case report previews + export. |
| `settings/settings-view.tsx` | 52 | Governance + LLM provider settings forms. |
| `intake/intake-limits.ts` | 9 | `MAX_CASES_PER_INTAKE_RUN` cap helpers. |

### 3.3 Services — `services/` (typed API layer; 1 file ↔ 1 backend domain)

`api.ts` (fetch wrapper: base URL, JWT header, error classes, WS URL) · `cases.service.ts` (363 — investigations CRUD/execute/delete + dashboard summary + review queue) · `intake.service.ts` (414 — client-side ledger parsing: quote-aware CSV/TSV, XLSX via `xlsx-lite`, the 7 pre-filter rules, employee-transaction seed extraction) · `analytics.service.ts` (224) · `employee-transactions.service.ts` (172) · `evidence.service.ts` (167) · `audit.service.ts` (142) · `settings.service.ts` (137) · `evidence-verification.service.ts` (135) · plus `agents`, `debate`, `evaluation`, `knowledge`, `replay`, `reports`, `reviews`, `verification`, `workspace` services (38–79 each). `__tests__/` holds 8 vitest suites for the parsing/mapping logic.

### 3.4 Hooks — `hooks/` (TanStack Query bindings)

One hook file per domain wrapping the services with query keys and cache invalidation: `use-cases` (154), `use-investigation-realtime` (271 — merges WS events into query cache live), `use-analytics` (96), `use-employee-transactions` (63), `use-knowledge` (46), `use-evidence-verification` (45), `use-settings` (41), `use-review` (30), plus thin single-query hooks (11–24 LOC each) for intake, debate, evidence, evaluation, replay, reports, verification, workspace, agent workflow, active-case id.

### 3.5 Components — `components/`

- `layout/app-shell.tsx` (212) — sidebar navigation with GL Guardian logo mark, header, command palette, live status pill.
- `brand/logo-mark.tsx` — the shield/ledger/checkmark brand SVG as a themable React component.
- Domain widgets: `agents/agent-workflow.tsx` (198, React Flow pipeline graph), `analytics/llm-analytics-panel.tsx` (303), `review/human-review-panel.tsx` (269), `employee-transactions/employee-transaction-dialog.tsx` (280) + table, `evidence/evidence-verification-card.tsx` (163), `intake/flagged-rows-table.tsx` (116) + `rule-prefilter.tsx`, `debate/debate-message.tsx`, `audit/audit-timeline.tsx`, `dashboard/` charts, `reports/report-preview.tsx`, `replay/replay-controls.tsx`, `verification/verification-claim-card.tsx`, `knowledge-base/knowledge-source-card.tsx`, `evaluation/evaluation-scorecard.tsx`, `forms/settings-form.tsx` (226) + `llm-provider-settings.tsx` (246).
- `tables/data-table.tsx` (186) — generic sortable TanStack table.
- `shared/` — stat cards, badges (risk/status), confidence meter, page header, empty/error/loading states, typed confirm dialog, chart skeleton.
- `ui/` — shadcn-style primitives (button, card, badge, input, textarea, progress).

### 3.6 Lib, state, types

- `lib/xlsx-lite.ts` (246) — dependency-free XLSX reader (zip + XML via browser APIs, date-serial conversion) powering Excel intake.
- `lib/report-export.ts` (127) — client-side report JSON/PDF downloads; `lib/download.ts`; `lib/friendly-error.ts` (humanizes provider errors); `lib/status.ts` (risk/status label maps); `lib/utils.ts` (`cn`, currency/percent formatting).
- `store/ui-state.tsx` — sidebar/command-palette state context; `providers/app-providers.tsx` — QueryClient + UI state.
- `constants/navigation.tsx` + `routes.ts` — sidebar sections and route builders.
- `types/domain.ts` (505) — the single source of truth for UI types (risk levels, investigations, intake summary + employee seeds, employee transactions, evaluation, etc.); `types/forms.ts` — zod schemas; the other `*.types.ts` files are 1-line re-export stubs kept for import stability.
- `tests/setup.ts` (635) — vitest setup with extensive API mocks; `data/` — mock fixtures for views not yet wired to live APIs.

UI root: `Dockerfile`, `next.config.ts`, `tailwind.config.ts`, `vitest.config.ts`, `eslint.config.mjs`, `components.json`, `package.json` (name `gl-guardian`), `README.md`.

---

## 4. Load tests, CI/CD, specs

| File | Purpose |
|---|---|
| `load-tests/k6/gl-guardian-api.js` | k6 scripted journey with profiles: smoke(1 VU), baseline(5), presentation(10→25), stress(20→50→100); thresholds p95 < 1.5 s, errors < 3%. |
| `load-tests/comprehensive_api_agents_load_test.py` | 1,145-line Python runner exercising API + agent workflows and asserting Prometheus counters move. |
| `load-tests/README.md` | How to run profiles and decode reports. |
| `.github/workflows/ci-cd.yml` | Parallel backend (ruff + pytest, Py 3.11) and frontend (lint/typecheck/vitest/build, Node 22) checks gating Docker builds → GHCR (SHA + latest tags) → manual `workflow_dispatch` SSH deploy with Alembic migrate-before-switch. |
| `.kiro/specs/storytelling/*` | 2,939 lines of spec-first artifacts: requirements (EARS-style), design, tasks with story points, scene acceptance criteria, vertical-slice plan. |

---

## 5. Documentation — `Docs/` (24 files)

Operations: `RUNBOOK`, `INCIDENT_RESPONSE`, `DISASTER_RECOVERY`, `BACKUP_RESTORE`, `MAINTENANCE`, `MONITORING_LOGGING`, `TROUBLESHOOTING`, `KNOWN_ISSUES`. Platform: `ARCHITECTURE` (verified against code), `INFRASTRUCTURE`, `DEPLOYMENT`, `PRODUCTION_DEPLOYMENT`, `CICD`, `ENVIRONMENT_VARIABLES`, `SECURITY`, `API_REFERENCE`, `LOCAL_DEVELOPMENT`. Product/analysis: `EMPLOYEE_TRANSACTIONS`, `FREE_EVIDENCE_VERIFICATION_APIS`, `LIVE_DATA_VALIDATION`, `VALIDATION_REPORT`, `AUDIT_REPORT`, `LESSONS_LEARNED` (15 documented challenges), `README` (index).

Assets: `Docs/Architecture/GL_Guardian_Architecture.svg/.png` (full pipeline + runtime/deployment diagram), `Docs/branding/` (logo lockup + mark, SVG/PNG), PDFs (`GL_Guardian_PRD`, `GL_Guardian_Design_Document`, HLD, LLD, `Sample_output/GL_Guardian_Sample_Output.pdf`).

---

## 6. How it fits together (one paragraph)

A CSV/XLSX ledger lands in the **intake view**, is rule-scored client-side (`intake.service.ts`), and flagged rows become `investigations` via the API; running the crew hands each case to the **executor**, which walks the LangGraph **crew** (evidence → bounded debate → adjudication → verification) using the **LLM gateway** for model calls and the **evidence-verification service** for live third-party checks; every step streams over **WebSocket** to the case workspace, persists to Postgres, and appends to the **hash-chained audit log**; the **confidence gate** routes each verdict to auto-clear or the **human review queue** (SoD enforced), a **report** is generated, and **analytics/RAGAS/metrics** expose cost, quality, and performance — all behind JWT/RBAC **auth**, deployable as UI + API + Postgres minimum with Celery/Redis/EventStoreDB as opt-in flags.
