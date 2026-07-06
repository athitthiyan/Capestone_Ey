# Architecture and Data Flow

**Verified against:** `Backend/app/`, `UI/`, infra manifests. **Version:** `0.1.0`.

## 1. Overview (for all audiences)

Skeptic Engine is an audit-investigation platform. Flagged general-ledger transactions
are investigated by a crew of six specialized AI agents that run an adversarial debate
(Challenger vs. Defender), grounded in retrieved evidence and third-party checks, gated
by a confidence threshold, routed to human review when needed, and recorded to an
immutable, hash-chained audit trail.

- **Frontend:** Next.js 15 / React 19 (`UI/`), TanStack Query/Table, React Flow, Recharts.
- **Backend:** FastAPI (`Backend/app/`), SQLAlchemy 2.0, Pydantic v2.
- **Agents:** LangGraph `StateGraph` orchestrating six roles (`app/agents/`).
- **Datastores:** PostgreSQL (+ `pgvector` for RAG), Redis (cache + Celery + pub/sub),
  EventStoreDB (optional immutable audit; Postgres hash-chain fallback).
- **Async:** Celery worker + beat (optional; gated by `USE_CELERY`).
- **Observability:** Prometheus metrics at `/metrics`, optional LangSmith tracing.

## 2. System context

```mermaid
flowchart LR
  User([Auditor / Reviewer]) -->|HTTPS| UI[Next.js UI]
  UI -->|REST /api/v1| API[FastAPI API]
  UI -->|WebSocket| API
  API --> PG[(PostgreSQL + pgvector)]
  API --> REDIS[(Redis: cache / broker / pub-sub)]
  API --> ESDB[(EventStoreDB - optional)]
  API -->|enqueue| WORKER[Celery worker]
  BEAT[Celery beat] -->|schedule| REDIS
  WORKER --> PG
  WORKER --> REDIS
  WORKER --> LLM[LLM Gateway]
  API --> LLM
  LLM --> ANTH[Anthropic]
  LLM --> GROQ[Groq]
  LLM --> OAI[OpenAI]
  LLM --> GEM[Gemini]
  LLM --> DS[DeepSeek]
  WORKER --> EXT[External evidence APIs: FX, registries, benchmarks]
  API -.metrics.-> PROM[(Prometheus /metrics)]
```

`USE_CELERY`, `USE_REDIS_EVENTS`, and `USE_EVENTSTORE` are feature flags. When off (the
default), investigations run in-process and audit falls back to Postgres, so a minimal
deploy needs only PostgreSQL. See [Environment Variables](ENVIRONMENT_VARIABLES.md).

## 3. The agent crew

| Agent | Role | Code |
|-------|------|------|
| Supervisor | Orchestrates the case, routes between phases | `app/agents/crew.py`, `executor.py` |
| Evidence | Collects grounded evidence (RAG + live APIs) | `executor._node_evidence` |
| Challenger | Argues the worst-case (risk) interpretation | `executor._node_challenger` |
| Defender | Argues the legitimate-business interpretation | `executor._node_defender` |
| Adjudicator | Weighs both sides into a verdict + confidence | `executor._node_adjudication` |
| Verifier | QA-gates that every claim is grounded | `executor._node_verification` |

Agents emit real Claude/LLM reasoning only when `USE_REAL_AGENTS=true`; otherwise the
executor streams deterministic stub output (`_stub_challenger`, `_stub_defender`) so the
plumbing can be developed without spending tokens.

## 4. Investigation pipeline (LangGraph state machine)

```mermaid
flowchart TD
  START([execute_investigation]) --> INIT[initialize state]
  INIT --> EVID[Evidence collection]
  EVID --> CHAL[Challenger]
  CHAL --> DEF[Defender]
  DEF --> ADJ[Adjudication - verdict + confidence]
  ADJ --> VER[Verification - grounded?]
  VER -->|rejected, retries left| RETRY[prepare retry]
  RETRY --> EVID
  VER -->|rejected, no retries| ESC[Escalate]
  VER -->|passed| GATE{Confidence gate}
  GATE -->|>= 0.90 and low risk| REPORT[Report + audit]
  GATE -->|0.70 - 0.90| REVIEW[Human review queue]
  GATE -->|< 0.70| ESC
  REVIEW --> REPORT
  ESC --> REPORT
  REPORT --> DONE([closed])
```

Routing is implemented in `_route_after_verification` and `_route_after_confidence_gate`.
Debate runs up to `MAX_DEBATE_ROUNDS` (default 2); verification retries up to
`MAX_VERIFICATION_RETRIES` (default 1). State is checkpointed per phase
(`_checkpoint_state`) into `investigation_states`.

## 5. Real-time updates

The worker and the API are separate processes, so in-process broadcast cannot reach
browser WebSocket clients. When `USE_REDIS_EVENTS=true`:

```mermaid
sequenceDiagram
  participant W as Celery worker
  participant R as Redis pub/sub
  participant A as FastAPI WS endpoint
  participant B as Browser
  W->>R: publish investigation_events:{id}
  B->>A: connect ws /api/v1/ws/investigations/{id}
  R-->>A: event
  A-->>B: forward event
```

Code: `app/realtime/redis_bus.py` (cross-process) and `websocket_manager.py`
(same-process). With the flag off, only same-process clients receive live events.

## 6. Data model

Tables (from `app/db/models.py`, created via Alembic in `migrations/versions/`):

```mermaid
erDiagram
  users ||--o{ investigations : owns
  investigations ||--|| investigation_states : has
  investigations ||--o{ debate_transcripts : has
  investigations ||--o{ evidence_artifacts : has
  investigations ||--o{ verification_claims : has
  investigations ||--o{ third_party_evidence_verifications : has
  investigations ||--o{ audit_log : records
  investigations ||--o{ llm_call_logs : bills
  investigations ||--o{ ragas_evaluation_results : scores
  investigations ||--o{ review_queue : queues
  vector_embeddings }o--|| investigations : "knowledge base (RAG)"
  request_logs }o--|| users : "HTTP audit"
  runtime_settings ||--|| runtime_settings : "singleton governance"
```

| Table | Purpose |
|-------|---------|
| `users` | Accounts + role (`analyst`, `reviewer`, `manager`, `partner`, `admin`) |
| `investigations` | Case header (vendor, amount, risk, confidence, status) |
| `investigation_states` | Per-phase checkpoint of the pipeline state |
| `debate_transcripts` | Challenger/Defender/Adjudicator messages |
| `evidence_artifacts` | Collected evidence + citations |
| `verification_claims` | Claim-level grounding QA |
| `third_party_evidence_verifications` | External benchmark checks (FX, flight, hotel, fuel, GST, etc.) |
| `audit_log` | Immutable hash-chained event log (Postgres fallback for EventStoreDB) |
| `request_logs` | Per-request HTTP audit |
| `llm_call_logs` | Per-call cost/latency/token telemetry |
| `ragas_evaluation_results` | Real-time RAGAS LLM-judge scores |
| `review_queue` | Human review work items |
| `vector_embeddings` | RAG knowledge chunks (pgvector column) |
| `runtime_settings` | Editable governance/model settings (singleton) |

## 7. Deployment topology (production)

```mermaid
flowchart LR
  subgraph Host / Cluster
    UIc[UI container :3000]
    APIc[API container :8000]
    WKc[worker container]
    BTc[beat container]
    PGc[(postgres :5432)]
    RDc[(redis :6379)]
    ESc[(eventstore :2113)]
    MGc[migrate job: alembic upgrade head]
  end
  Internet -->|TLS| LB[Reverse proxy / LB]
  LB --> UIc
  LB --> APIc
  UIc --> APIc
  APIc --> PGc & RDc & ESc
  WKc --> PGc & RDc
  BTc --> RDc
  MGc --> PGc
```

Reference implementations: `docker-compose.production.yml`, `Backend/k8s-deployment.yaml`,
`Backend/railway.*.json`. See [Deployment](DEPLOYMENT.md) and [Infrastructure](INFRASTRUCTURE.md).
