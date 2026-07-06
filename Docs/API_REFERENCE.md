# API Reference

**Verified against:** `Backend/app/api/routes/*.py` + `app/main.py`. **Version:** `0.1.0`.

All business routers are mounted under `API_ROOT_PATH` (default `/api/v1`). Health lives
at the root. Interactive docs: `GET /docs` (Swagger) and `GET /openapi.json`.

## Conventions

- **Base URL (local):** `http://localhost:8000`
- **API root:** `/api/v1`
- **Auth:** Bearer JWT from `POST /api/v1/auth/token`. Enforcement depends on
  `AUTH_REQUIRED` (forced `true` when `ENV=production`). See [Security](SECURITY.md).
- **Metrics:** `GET /metrics` (Prometheus; excluded from OpenAPI).

## Health (root)

| Method | Path | Notes |
|--------|------|-------|
| GET | `/health` | Liveness: `{status, app, version}` |
| GET | `/health/detailed` | Readiness: DB `SELECT 1`, active investigations, WS counts; 503 on failure |

## Auth - `/api/v1/auth`

| Method | Path | Notes |
|--------|------|-------|
| POST | `/auth/token` | OAuth2 password grant -> access token |
| POST | `/auth/register` | Create a user |
| GET | `/auth/me` | Current user profile |

## Intake - `/api/v1/intake`

| Method | Path | Notes |
|--------|------|-------|
| POST | `/intake` | Upload/normalize ledger rows and pre-filter |
| GET | `/intake/summary` | Intake summary |
| DELETE | `/intake/imported` | Remove imported rows |

## Investigations - `/api/v1/investigations`

| Method | Path | Notes |
|--------|------|-------|
| POST | `/investigations` | Create a case |
| GET | `/investigations` | List (filter/paginate) |
| GET | `/investigations/{id}` | Case detail |
| GET | `/investigations/{id}/workspace` | One-shot workspace payload |
| GET | `/investigations/{id}/debate` | Debate transcript |
| GET | `/investigations/{id}/evidence` | Evidence artifacts |
| GET | `/investigations/{id}/verification` | Verification result |
| GET | `/investigations/{id}/audit` | Audit trail for the case |
| GET | `/investigations/{id}/replay` | Step replay |
| POST | `/investigations/{id}/execute` | Run the pipeline |
| DELETE | `/investigations/all` | Destructive: delete all (elevated role / see Security) |

## Reviews - `/api/v1/reviews`

| Method | Path | Notes |
|--------|------|-------|
| GET | `/reviews/queue` | Human review queue |
| POST | `/reviews/{id}/approve` | Approve |
| POST | `/reviews/{id}/reject` | Reject |
| POST | `/reviews/{id}/escalate` | Escalate |
| POST | `/reviews/{id}/request-evidence` | Request more evidence |

## Claims - `/api/v1/claims`

| Method | Path | Notes |
|--------|------|-------|
| GET | `/claims/{claim_id}/verification` | Claim grounding detail |
| POST | `/claims/verify-preview` | Preview verification of a claim |

## Agents - `/api/v1/agents`

| Method | Path | Notes |
|--------|------|-------|
| GET | `/agents` | Agent registry/health |
| GET | `/agents/workflow/{id}` | Workflow graph for a case |

## Analytics - `/api/v1/analytics`

| Method | Path | Notes |
|--------|------|-------|
| GET | `/analytics/summary` | KPI summary |
| GET | `/analytics/kpis` | KPI targets vs actuals |
| GET | `/analytics/trend` | Confidence/volume trend |
| GET | `/analytics/agent-accuracy` | Per-agent accuracy |
| GET | `/analytics/llm/summary` | LLM cost/latency summary |
| GET | `/analytics/llm/by-provider` | Cost by provider |
| GET | `/analytics/llm/by-model` | Cost by model |
| GET | `/analytics/llm/recent-calls` | Recent LLM calls |
| GET | `/analytics/llm/cost-trends` | Cost over time |
| GET | `/analytics/llm/providers` | Configured providers |

## Evaluation - `/api/v1/evaluation`

| Method | Path | Notes |
|--------|------|-------|
| GET | `/evaluation/summary` | Crew vs baseline A/B summary |
| GET | `/evaluation/case/{id}` | Per-case evaluation |

## Reports - `/api/v1/reports`

| Method | Path | Notes |
|--------|------|-------|
| GET | `/reports` | List generated reports |
| GET | `/reports/{id}` | Fetch a report (MD/HTML/PDF) |

## Knowledge base - `/api/v1/knowledge`

| Method | Path | Notes |
|--------|------|-------|
| GET | `/knowledge/sources` | Policy sources |
| GET | `/knowledge/chunks` | Indexed chunks |
| GET | `/knowledge/search` | RAG search |
| GET | `/knowledge/stats/summary` | Index freshness/stats |
| POST | `/knowledge/reindex` | Re-embed the corpus |

## Audit - `/api/v1/audit`

| Method | Path | Notes |
|--------|------|-------|
| GET | `/audit` | Query the immutable audit log |
| GET | `/audit/recent` | Recent audit events |
| GET | `/audit/requests` | HTTP request log |

## Settings (governance) - `/api/v1/settings`

| Method | Path | Notes |
|--------|------|-------|
| GET | `/settings` | Read runtime governance settings |
| PUT | `/settings` | Update governance settings |
| GET | `/settings/llm` | LLM model/provider settings |
| PUT | `/settings/llm` | Update LLM settings |

## WebSocket - `/api/v1`

| Protocol | Path | Notes |
|----------|------|-------|
| WS | `/api/v1/ws/investigations/{id}` | Live pipeline events. Cross-process delivery requires `USE_REDIS_EVENTS=true`. |

> This table is generated from route decorators. For request/response schemas, use the
> live OpenAPI at `/docs` or `/openapi.json`, which is always authoritative.
