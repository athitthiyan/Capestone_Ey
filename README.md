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

### Two benchmarks, and why both

| | `uci_audit_v1` | `gl_synthetic_v1` |
|---|---|---|
| Labels | **Real** post-audit findings | Generator ground truth |
| Source | [UCI Audit Data, dataset 475](https://archive.ics.uci.edu/dataset/475/audit+data) — 776 firms examined by a government external-audit office | Generated corpus |
| Held-out cases | **346** (146 positive / 200 negative) | 116 (56 / 60) |
| Role | Primary. External validity on real labels. | Secondary. Control conditions the real data cannot express — explicit duplicate pairs, segregation-of-duty breaches, document gaps. |

The real benchmark is the primary one because it has a property that makes the research
question sharp. The archive records each firm at two stages: the **pre-audit screen** and the
**post-audit finding**. The screen's flags are strictly nested inside the findings — no firm the
audit found risky was missed by the screen — so on the held-out split the incumbent screen has
**recall 1.000 and specificity 0.670**, and 66 firms were flagged and then cleared by a human
auditor. Those 66 are real hard negatives, and the operational question is exactly:

> can adversarial reasoning clear more of them without losing a single true positive?

Leakage control matters here and is enforced in code. `Risk` is a threshold on `Audit_Risk`,
which is computed from the audit office's own scoring intermediates, so all 16 of those columns
are dropped; the build asserts their presence in the archive and fails loudly if a future
revision adds another. See the [real-data card](Backend/datasets/DATA_CARD_UCI_AUDIT.md) and the
[synthetic data card](Backend/datasets/DATA_CARD.md). Labels, category, difficulty and split are
excluded from model input by construction — `BenchmarkCase.model_view()` is the only path a
runner has to a case, and a test asserts the label cannot appear in a rendered prompt.

### Measured results — `uci_audit_v1` (real labels, 346 held-out cases)

| Method | Accuracy [95% CI] | Precision | Recall | Specificity [95% CI] | F1 | MCC |
|---|---|---:|---:|---|---:|---:|
| `rule_baseline` (incumbent screen) | 0.809 [0.769, 0.850] | 0.689 | **1.000** | 0.670 [0.604, 0.735] | 0.816 | 0.679 |
| `logistic_reference` *(supervised ceiling)* | 0.962 [0.942, 0.983] | 0.946 | 0.966 | 0.960 [0.930, 0.985] | 0.956 | 0.923 |
| `tree_reference` *(supervised ceiling)* | 0.957 [0.934, 0.977] | 0.971 | 0.925 | 0.980 [0.959, 0.995] | 0.947 | 0.911 |
| `single_llm` | Not run | Not run | Not run | Not run | Not run | Not run |
| `full_multi_agent` | Not run | Not run | Not run | Not run | Not run | Not run |
| ablations (`no_challenger`, `no_defender`, `no_verifier`, `no_rag`, `one_debate_round`) | Not run | | | | | |

Read the two reference rows carefully: they are **fitted on the development split** and see
labels the LLM conditions never do. They are not competitors — they are a ceiling that says how
much signal the nine recorded fields contain at all, and they are reported precisely so this
project cannot claim credit for reasoning where a logistic regression on six numbers already
suffices. The honest headline is that on this dataset the tabular ceiling is high (0.962), so the
interesting margin for an agent system is not raw accuracy but **specificity on the 66 real hard
negatives, evidential groundedness, and cost per case**.

The incumbent screen's confusion matrix is `TP=146, FP=66, FN=0, TN=134`. Its F1 of 0.816 is
*not* evidence that it works well — it never misses, and pays for that with 66 false positives.
Both supervised references beat it at Holm-corrected p < 1e-9 (exact McNemar, family of 2).

Intervals are percentile bootstrap over 2,000 case-level resamples; resampling whole cases keeps
label, prediction and score aligned. Generated artifacts — per-category and per-difficulty
slices, calibration, paired tests, every failure case — are under
[`Backend/experiments/results/uci_audit_v1/`](Backend/experiments/results/uci_audit_v1/RESULTS.md)
and are regenerated, never hand-edited.

### What is still Not run, and why

The LLM and multi-agent conditions have no results because **no valid provider credential is
present in this checkout**. Everything needed to produce them exists and is tested: live
Anthropic and OpenAI adapters, the debate orchestration with real role toggles, a cost guard, a
content-addressed response cache, and a runner that records a parse failure as an error row
rather than guessing a prediction. One command fills the table:

```bash
cd Backend
export ANTHROPIC_API_KEY=...            # or set it in Backend/.env
python scripts/run_experiment_matrix.py --benchmark uci_audit_v1 --all --max-cost-usd 25
python scripts/score_evidence_quality.py --benchmark uci_audit_v1 --max-cost-usd 5
python scripts/analyze_results.py --benchmark uci_audit_v1
```

A dry run prices the full matrix at **$22.84** on `claude-haiku-4-5` (346 cases × 10 conditions,
9,096 model calls). Nothing is imputed in the meantime: unrun conditions read `Not run`, and a
run that covers only part of the held-out set is reported as `incomplete` and refused a score, so
no method can improve its numbers by dropping the cases it found hard.

### Evidence quality and label adjudication

Groundedness and citation correctness are scored by **two independent judges on different
models**, label-blind and method-blind, against a three-point rubric. Agreement is reported as
percentage agreement and quadratic-weighted Cohen's kappa; items where the judges differ by more
than one rubric step are written to `adjudication_queue.csv` for a human decision rather than
averaged away.

For the synthetic benchmark, `scripts/adjudicate_labels.py` produces a second, independent label
track: two models re-annotate every evaluation case under the written rubric without seeing the
existing label, and the gap between generator labels and independent judgement is itself a
reported number. On the real benchmark the same script measures auditor–model agreement but
never overrides the real findings.

### Reproduce

```bash
cd Backend
python scripts/build_uci_audit_benchmark.py --verify-only   # committed data == fresh build
python scripts/build_gl_evidence_corpus.py --verify-only
python scripts/run_experiment_matrix.py --benchmark uci_audit_v1 --dry-run
python scripts/run_experiment_matrix.py --benchmark uci_audit_v1 \
    --methods rule_baseline logistic_reference tree_reference
python scripts/analyze_results.py --benchmark uci_audit_v1
python -m pytest tests/test_experiment_pipeline.py -q                # 85 tests
```

The raw UCI archive is vendored at `Backend/datasets/raw/` with its SHA-256 pinned, so the
benchmark rebuilds byte-identically with no network access. The split is content-addressed —
`sha256(salt + case_id)`, no RNG state — so it is the same on any checkout.

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
