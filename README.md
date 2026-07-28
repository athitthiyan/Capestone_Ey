<img src="Docs/branding/gl_guardian_logo.svg" alt="GL Guardian - Automated Audit" width="420" />

# GL Guardian - Automated Audit

[![CI/CD](https://github.com/athitthiyan/Capestone_Ey/actions/workflows/ci-cd.yml/badge.svg)](https://github.com/athitthiyan/Capestone_Ey/actions/workflows/ci-cd.yml)
[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](Backend/pyproject.toml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

Enterprise audit-investigation decision support powered by a multi-agent AI crew. It prioritizes
synthetic audit-risk indicators through adversarial Challenger–Defender reasoning, retrieval,
verification, human review, and an immutable hash-chained audit log. It does not replace a
qualified auditor or establish that fraud occurred.

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
GL Guardian/
├── Backend/          FastAPI service: agent orchestration, DB, audit log, LLM routing
│   └── history/      Historical engineering notes (BACKEND_FIXES, SETUP_COMPLETE)
├── UI/               Next.js 15 / React 19 frontend (live-API driven, no mock data)
├── Docs/             PRD, architecture, ops handbook, LIVE_DATA_VALIDATION
├── load-tests/       k6 profiles + comprehensive Python API/agent load runner
├── presentation/     Story assets: storyboard bible, scripts, brand guide, POV deck
├── archive/          Historical artifacts: early HTML prototype, dated audit report
├── GL_Guardian_Presentation.pptx            14-scene demo deck (+ live evidence)
├── GL_Guardian_Executive_Presentation.pptx  Executive/technical review deck
└── docker-compose.production.yml, DEPLOYMENT_GUIDE.md
```

See [Backend/README.md](Backend/README.md) and [UI/README.md](UI/README.md) for details on each
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
cd UI
pnpm install
cp .env.example .env      # point NEXT_PUBLIC_API_URL at the backend
pnpm dev
```

Open `http://localhost:3000/dashboard`.

## Experiments and Evaluation

**Research question:** Does adversarial multi-agent reasoning with retrieval and verification
improve anomaly-detection precision, specificity, evidential groundedness, and citation
correctness over deterministic rules and a single-LLM baseline?

The six preregistered hypotheses test specificity, the Verifier, RAG, debate cost/quality,
difficult-case performance, and calibration. Variables, tests, acceptance criteria, and
confounders are defined in [the research protocol](Docs/RESEARCH_PROTOCOL.md).

### Dataset and split

Benchmark v1 contains 600 generated transactions: 300 positive and 300 negative synthetic
audit-risk labels, including normal, hard-negative, hard-positive, borderline, materiality,
related-party, document-gap, segregation-of-duty, and duplicate cases. Seed `20260728` produces
484 development and 116 frozen evaluation rows (56 positive, 60 negative), with SHA-256
`b9c5db808d6c4b8c8d8c144d0e34f00c67e0c35c10eb401e707ed3ac863908f0`.
Research-only labels, categories, difficulty, and split are excluded from method inputs. See the
[data card](Backend/datasets/DATA_CARD.md). These labels are not confirmed real-world fraud.

### Measured results

| Method | Accuracy | Precision | Recall | Specificity | F1 | Balanced accuracy | Groundedness | Citation correctness |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Rule baseline | 0.7155 | 0.6386 | 0.9464 | 0.5000 | 0.7626 | 0.7232 | Not run | Not run |
| Single LLM | Not run | Not run | Not run | Not run | Not run | Not run | Not run | Not run |
| Full multi-agent | Not run | Not run | Not run | Not run | Not run | Not run | Not run | Not run |

The executed rule confusion matrix is `TP=53, FP=30, FN=3, TN=30`; MCC is 0.4945, ROC-AUC
0.7232, PR-AUC 0.9811, Brier score 0.1959, and ECE 0.0534. The unusually high PR-AUC reflects
scenario-generated confidence ordering and must not be generalized to real audit data. Generated
results, bootstrap uncertainty, category slices, calibration data, failures, and the reproducible
SVG are under [`Backend/experiments/results`](Backend/experiments/results/RESEARCH_REPORT.md).

### Agentic evaluation, groundedness, and citations

Frozen configurations cover rules, single LLM, full crew, no Challenger, no Verifier, no RAG,
no Defender, no evidence retrieval, and one/two debate rounds. Dry-run validation does not create
research metrics. Live agentic results remain Not run because credentials and complete normalized
outputs are unavailable. Human annotation and agreement are also Not run. Operational dashboard
proxies are not benchmark truth.

### Ablations and failure cases

The generated failure report contains 33 rule errors: 30 false positives and 3 false negatives.
Hard negatives expose the cost of naïvely flagging legitimate high-value/manual journals;
borderline cases account for the missed positives. No ablation result is claimed.

### Reproduce

```bash
cd Backend
python scripts/generate_benchmark_dataset.py
python scripts/run_all_experiments.py --dry-run
python scripts/run_rule_baseline.py
python scripts/generate_research_report.py
python scripts/check_research_artifacts.py
python -m pytest tests/test_research_pipeline.py -q
```

Do not hand-edit generated results or infer missing values. See
[reproduction instructions](Docs/EXPERIMENT_REPRODUCTION.md),
[responsible AI](Docs/RESPONSIBLE_AI.md), and [threats to validity](Docs/THREATS_TO_VALIDITY.md).

## Documentation index

- [Research gap audit](Docs/RESEARCH_GAP_AUDIT.md) · [research protocol](Docs/RESEARCH_PROTOCOL.md)
- [Research report](Backend/experiments/results/RESEARCH_REPORT.md) · [failure analysis](Backend/experiments/results/FAILURE_ANALYSIS.md)
- [Data card](Backend/datasets/DATA_CARD.md) · [model card](Docs/MODEL_CARD.md)
- [Annotation guide](Backend/experiments/annotation/ANNOTATION_GUIDE.md)
- [Responsible AI](Docs/RESPONSIBLE_AI.md) · [security and privacy](Docs/SECURITY_AND_PRIVACY.md)
- [Threats to validity](Docs/THREATS_TO_VALIDITY.md) · [MBZUAI portfolio summary](Docs/MBZUAI_PORTFOLIO_SUMMARY.md)

## Live deployment

- **UI:** https://capestone-ey.vercel.app
- **API:** https://capestoneey-production.up.railway.app (`/health`, `/health/detailed`, `/metrics`)

All UI pages consume the live API — there is no mock data layer. See
[Docs/LIVE_DATA_VALIDATION.md](Docs/LIVE_DATA_VALIDATION.md) for the audit, live-data
evidence, measured latency, and remaining limitations (validated 2026-07-08).

## Production deployment

See [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md), `docker-compose.production.yml`, and
`Backend/k8s-deployment.yaml`.

## License

See [LICENSE](LICENSE).
