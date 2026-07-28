# Research gap audit

Audit date: 2026-07-28. Scope: backend, UI, agents, RAG, providers, data, tests, CI,
containers, deployment, documentation, generated artifacts, and repository hygiene.

## Current state and strengths

GL Guardian is a substantial full-stack implementation: FastAPI and Next.js, PostgreSQL/pgvector
retrieval, Redis/Celery, EventStoreDB-style audit events, LangGraph orchestration, six explicit
agent roles, provider routing, human review, Prometheus metrics, load tests, Docker/Kubernetes,
and extensive unit/API tests. The live graph has bounded debate and verification-retry cycles.
Cost, token, latency, evidence, citations, verdicts, and reviewer ground truth have persistence
models. CI already tests backend/frontend and builds images.

## Gaps and risks found

- The earlier 1,000-row synthetic ledger was 93.7% proxy-positive; its rule result had zero
  specificity and could not support comparative research claims.
- Operational RAGAS telemetry proxies were presented beside judge scores. Completion and
  confidence are not factual correctness or semantic similarity.
- No frozen balanced benchmark, multiple normalized baseline outputs, executable ablation
  protocol, uncertainty estimates, annotation agreement pipeline, or generated research report.
- Groundedness and citation rubrics lacked a label-blinded research interface and mandatory
  human-review status.
- The production graph does not yet consume the new research ablation configs; live ablation
  adapters remain manual work. Provider credentials and human annotations are unavailable.
- Full local tests require the pinned `ragas` package; the inspected environment did not have it.
- Generated presentation binaries and duplicate historical assets increase repository size;
  they are documented assets and were not deleted without ownership review.
- Environment templates contain safe blank secrets and local development passwords. Deployment
  workflows pass credentials through GitHub secrets, but secret scanning was not a CI gate.
- Documentation contains historical casing/encoding inconsistencies (`Ui` versus `UI`, mojibake).
- Synthetic identities and controls cannot establish real deployment prevalence or fairness.

## Implemented remediation, in priority order

1. Balanced deterministic benchmark generator, manifest, data card, and leakage boundary.
2. Strict normalized result schema, rule execution, live-method configs, dry-run validation.
3. Full classification/calibration/operation metrics, bootstrap CIs, McNemar and permutation tools.
4. Human/model-assisted annotation guide, schema, agreement code, and label-blind evidence rubrics.
5. Generated reports, failure CSV/Markdown, statistical JSON, and reproducible SVG.
6. Research tests and CI research/security jobs.
7. Formal protocol, responsible-AI, validity, model/data, privacy, reproduction, and portfolio docs.

## Remaining prioritized work

P0: obtain two qualified human reviewers and execute single-LLM/full-crew/major ablations on the
frozen split. P1: wire every config flag into a separate research graph factory and externally
review judge prompts. P2: add a licensed, de-identified real-world benchmark under governance,
test provider/model drift, and conduct subgroup/control-domain analyses. Until P0 is complete,
the repository is not fully research-ready.
