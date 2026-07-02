# Skeptic Engine

Enterprise audit investigation platform powered by a multi-agent AI crew. It automates fraud
detection and risk assessment through an adversarial debate framework (Challenger vs. Defender),
with mandatory human-in-the-loop review and an immutable, hash-chained audit log.

## How it works

```
CASE INTAKE            EVIDENCE COLLECTION        DEBATE + VERIFICATION           DECISION
CSV upload → rules  →  Supervisor + Evidence   →  Challenger ↔ Defender (≤2   →  Confidence gate:
pre-filter                agent (RAG + live         rounds) → Adjudicator          ≥0.90 verified/low
                           APIs) → citations         verdict → Verifier QA          → auto-clear
                                                                                     0.70-0.90 → review
                                                                                     <0.70 → escalate
                                                                                          ↓
                                                                              REPORT + AUDIT
                                                                              MD/HTML/PDF report,
                                                                              immutable audit log
```

**Agent roles**: Supervisor (orchestrator) · Evidence agent (RAG + live APIs) · Challenger
(risk case) · Defender (legitimacy case) · Adjudicator (verdict) · Verifier (grounding QA).

## Repository layout

```
Skeptic Engine/
├── Backend/     FastAPI service: agent orchestration, DB, audit log, LLM routing
├── Ui/          Next.js 15 / React 19 frontend
├── Docs/        PRD, architecture, HLD/LLD documents
├── Prototype/   Early static HTML prototype
└── docker-compose.production.yml, DEPLOYMENT_GUIDE.md
```

See [Backend/README.md](Backend/README.md) and [Ui/README.md](Ui/README.md) for details on each
half of the stack.

## Tech stack

**Backend** — FastAPI, PostgreSQL + pgvector (RAG), SQLAlchemy/Alembic, Redis + Celery (async
tasks), EventStoreDB (immutable audit trail), LangGraph + LangChain (agent orchestration).

**LLM providers** — Anthropic Claude, Groq, OpenAI, Google Gemini, DeepSeek, selectable per
environment with automatic fallback (`Backend/app/llm/`).

**Observability** — Prometheus metrics at `GET /metrics` (HTTP + LLM cost/latency/token +
investigation pipeline metrics) and optional LangSmith tracing for every LangGraph/LLM call.

**Frontend** — Next.js 15 App Router, React 19, TypeScript, Tailwind CSS, TanStack Query/Table,
React Flow (agent workflow visualization), Recharts.

## Getting started

### Backend

```bash
cd Backend
python -m venv .venv && .venv/Scripts/activate   # or source .venv/bin/activate on macOS/Linux
pip install -r requirements.txt
cp .env.example .env      # fill in DATABASE_URL, LLM provider keys, etc.
uvicorn app.main:app --reload
```

API docs: `http://localhost:8000/docs` · Health: `http://localhost:8000/health` · Metrics:
`http://localhost:8000/metrics`

See [Backend/QUICKSTART.md](Backend/QUICKSTART.md) and [Backend/PREREQUISITES.md](Backend/PREREQUISITES.md)
for the full local stack (Postgres, Redis, EventStoreDB via `docker-compose.local-infra.yml`).

### Frontend

```bash
cd Ui
pnpm install
cp .env.example .env      # point NEXT_PUBLIC_API_URL at the backend
pnpm dev
```

Open `http://localhost:3000/dashboard`.

## Production deployment

See [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md), `docker-compose.production.yml`, and
`Backend/k8s-deployment.yaml`.

## License

See [LICENSE](LICENSE).
