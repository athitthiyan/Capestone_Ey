# Reproducible experiments

Research evaluation, kept separate from production telemetry. Dashboard numbers are never
benchmark truth and never enter these tables.

## Research question

> Does adversarial multi-agent reasoning with retrieval and verification improve
> anomaly-detection **specificity** and **evidential groundedness** over a deterministic
> screen and a single-LLM baseline, at an acceptable cost per case?

Specificity leads deliberately. The incumbent screen on the real benchmark already has
recall 1.000; there is no recall to win. What it does not have is the ability to clear a
flagged case, and that is what an auditor's time is spent on.

## Hypotheses

| | Hypothesis | Primary measure | Test |
|---|---|---|---|
| H1 | Multi-agent reasoning improves specificity over the deterministic screen without reducing recall below 0.95 | specificity, recall | exact McNemar vs `rule_baseline`, Holm-corrected |
| H2 | The Verifier improves groundedness and citation correctness | mean groundedness, citation correctness | `full_multi_agent` vs `no_verifier`, bootstrap CI on the difference |
| H3 | Retrieval reduces unsupported conclusions | unsupported-claim rate (groundedness = 0) | `full_multi_agent` vs `no_rag` |
| H4 | Challenger–Defender debate improves accuracy on hard cases but increases cost and latency | accuracy on the `hard` slice; mean cost, p95 latency | `full_multi_agent` vs `no_challenger` / `no_defender`; cost CI |
| H5 | Agent confidence is better calibrated than the screen's | ECE, Brier score | reliability curve, per-method |

A hypothesis is only reported as supported when the Holm-adjusted p is below 0.05 **and**
the bootstrap interval on the effect excludes zero. Both are generated, not asserted.

## Benchmarks

| | `uci_audit_v1` | `gl_synthetic_v1` |
|---|---|---|
| Labels | real post-audit findings | generator ground truth |
| Held out | 346 (146+/200−) | 116 (56+/60−) |
| Build | `scripts/build_uci_audit_benchmark.py` | `scripts/generate_benchmark_dataset.py` + `scripts/build_gl_evidence_corpus.py` |
| Data card | `datasets/DATA_CARD_UCI_AUDIT.md` | `datasets/DATA_CARD.md` |

The real benchmark is primary. The synthetic one exists because the real data contains no
explicit duplicate pairs, segregation-of-duty breaches or document gaps, and those control
conditions are worth measuring — but its labels are generator agreement, not audit
judgement, and they are reported in a separate table for that reason.

## Conditions

| Method | Sees labels? | Calls per case | What it isolates |
|---|---|---:|---|
| `rule_baseline` | no | 0 | the incumbent screen, replayed exactly |
| `logistic_reference` | **development only** | 0 | signal available in the recorded fields |
| `tree_reference` | **development only** | 0 | as above, non-linear |
| `single_llm` | no | 1 | reasoning without architecture |
| `full_multi_agent` | no | 6 | the full system |
| `no_challenger` | no | 4 | the rebuttal turn |
| `no_defender` | no | 4 | the response-to-rebuttal turn |
| `no_verifier` | no | 5 | the independent citation check |
| `no_rag` | no | 6 | evidence retrieval |
| `one_debate_round` | no | 4 | depth of debate |

The two supervised references are a **ceiling, not a competitor**. They see labels the LLM
conditions never do, and they are reported so the project cannot claim credit for reasoning
where a linear model already suffices.

Ablation configs are checked by a test to differ from `full_multi_agent` in exactly one
field, so no ablation can quietly change two things at once.

## Pipeline

```bash
# data (no network needed; the raw archive is vendored with a pinned SHA-256)
python scripts/build_uci_audit_benchmark.py
python scripts/build_gl_evidence_corpus.py

# plan and price before spending anything
python scripts/run_experiment_matrix.py --benchmark uci_audit_v1 --dry-run

# conditions that need no provider
python scripts/run_experiment_matrix.py --benchmark uci_audit_v1 \
    --methods rule_baseline logistic_reference tree_reference

# live: smoke test first, then the matrix
python scripts/run_experiment_matrix.py --benchmark uci_audit_v1 \
    --methods single_llm --limit 10 --max-cost-usd 0.50
python scripts/run_experiment_matrix.py --benchmark uci_audit_v1 --all --max-cost-usd 25

# evidence quality: two judges, different models, label-blind
python scripts/score_evidence_quality.py --benchmark uci_audit_v1 --max-cost-usd 5

# independent label track (synthetic benchmark)
python scripts/adjudicate_labels.py --benchmark gl_synthetic_v1 --max-cost-usd 5

# tables, intervals, paired tests, failure cases
python scripts/analyze_results.py --benchmark uci_audit_v1

python -m pytest tests/test_experiment_pipeline.py -q
```

## Layout

- `benchmarks.py` — unified loading. `BenchmarkCase.model_view()` is the *only* path a runner
  has to a case, and it drops every label field. This is the central integrity guarantee.
- `llm.py` — Anthropic and OpenAI adapters over `urllib` (no SDK pin), retries with backoff,
  measured token counts, a versioned price table, and a content-addressed response cache.
- `prompts/` — every agent prompt as a plain file. `prompt_version` is a hash of the actual
  file contents, so a reported version cannot drift from the text that produced the run.
- `runners/` — `baselines.py` (screens and supervised references, pure stdlib),
  `llm_agents.py` (single and debate), `candidate.py` (strict external-file validation).
- `evaluators/judge.py` — label-blind, method-blind groundedness and citation judging.
- `annotation/` — rubric, agreement statistics (Cohen, weighted Cohen, Fleiss).
- `metrics.py`, `statistics.py` — classification and calibration metrics; bootstrap
  intervals, exact McNemar, permutation tests, Holm correction.
- `harness.py` — config × benchmark → run directory, with a cost guard.
- `runs/`, `results/` — generated only.

## Rules the harness enforces

1. **No fixtures standing in for measurements.** A missing credential aborts the run. It
   never emits a placeholder row.
2. **No partial credit.** A method is scored only if it covers every held-out case.
   Otherwise it is reported `incomplete`, so no method can improve its score by dropping
   the cases it found hard.
3. **No imputation.** Conditions that were not run read `Not run`.
4. **Failures count as failures.** An unparseable response becomes an error row with the raw
   text kept, scored as the wrong answer it was — not retried until it parses.
5. **Cost is measured, not estimated.** Token counts come from the provider; an unpriced
   model raises rather than reporting `0.0`.
6. **Every number is regenerated.** `RESULTS.md`, `metrics.csv`, `summary.json` and
   `statistical_tests.json` are written by `analyze_results.py` and are not hand-edited.

## Interpreting the tables

Read specificity and the `hard` slice before F1. On the real benchmark the incumbent screen
scores F1 0.816 while flagging 66 firms a human auditor then cleared — a high F1 with
specificity 0.670 is a description of over-flagging, not of success. The same trap in
reverse applies to the supervised references: 0.962 accuracy from a logistic regression is a
statement about the dataset, not about reasoning.

## Legacy artifacts

`results/` also contains the earlier single-benchmark run (`summary.json`, `metrics.csv`,
`RESEARCH_REPORT.md`, `figures/`) produced by `scripts/run_rule_baseline.py` and
`scripts/generate_research_report.py`. Current results live in the per-benchmark
subdirectories `results/uci_audit_v1/` and `results/gl_synthetic_v1/`.
