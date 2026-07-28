from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from experiments.reporting import (build_summary, failure_rows, load_inputs, write_confusion_svg,
                                   write_csv, write_reliability_svg, write_svg)


def fmt(value): return "Not available" if value is None else f"{value:.4f}" if isinstance(value, float) else str(value)


def main() -> None:
    output = Path("experiments/results"); output.mkdir(parents=True, exist_ok=True)
    dataset, results = load_inputs(Path("datasets/gl_guardian_benchmark_v1.csv"), Path("experiments/runs/rule_baseline.jsonl"))
    summary = build_summary(dataset, results); failures = failure_rows(dataset, results)
    (output / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output / "statistical_tests.json").write_text(json.dumps({"rule_baseline": summary["uncertainty"], "paired_tests": "Not run: only one method executed"}, indent=2) + "\n", encoding="utf-8")
    metrics = summary["classification"]
    write_csv(output / "metrics.csv", [{"method": summary["method"], **{k: v for k, v in metrics.items() if not isinstance(v, (dict, list))}}])
    write_csv(output / "failure_cases.csv", failures)
    (output / "failure_report.json").write_text(json.dumps(failures, indent=2) + "\n", encoding="utf-8")
    write_svg(output / "figures" / "rule_baseline_metrics.svg", metrics)
    write_confusion_svg(output / "figures" / "confusion_matrix.svg", metrics["confusion_matrix"])
    write_reliability_svg(output / "figures" / "reliability_diagram.svg", metrics["reliability_curve"])
    failure_md = "# Failure analysis\n\nGenerated from executed predictions only.\n\n" + f"- Total flagged failures: {len(failures)}\n" + "- Categories: " + ", ".join(f"{c} ({sum(r['risk_category']==c for r in failures)})" for c in sorted({r['risk_category'] for r in failures})) + "\n\nRecommended next experiments: execute the frozen single-LLM and crew configurations, independently review explanations and citations, and use paired McNemar tests.\n"
    (output / "FAILURE_ANALYSIS.md").write_text(failure_md, encoding="utf-8")
    report = f"""# GL Guardian research report

## Abstract

This report tests deterministic audit-risk screening on a balanced, privacy-safe synthetic benchmark and establishes a frozen protocol for future single-LLM, multi-agent, and ablation comparisons. Only the rule baseline has been executed.

## Problem statement and research question

Does adversarial multi-agent reasoning with retrieval and verification improve anomaly-detection precision, specificity, evidential groundedness, and citation correctness over deterministic rules and a single-LLM baseline?

## Hypotheses

H1–H6 cover specificity, verification, retrieval, debate trade-offs, difficult cases, and calibration; formal acceptance criteria are in `Docs/RESEARCH_PROTOCOL.md`.

## System overview

The production system combines Supervisor, Evidence, Challenger, Defender, Adjudicator, and Verifier roles.

## Dataset and annotation process

Benchmark v1 has 600 balanced synthetic transactions with a deterministic development/evaluation split. Research-only labels are excluded from method inputs. Human annotation is Not run; the blinded annotation/adjudication protocol is implemented.

## Experimental design, baselines, architecture, and ablations

Configurations freeze dataset version, seed, prompts, retrieval, roles, debate rounds, timeout, and retries. The executed baseline is deterministic rules. Single LLM, full crew, and configured ablations are Not run.

## Metrics

Classification, calibration, evidence-quality, operational, category, bootstrap, and paired-comparison metrics are implemented. Undefined metrics remain null.

## Results

| Method | Accuracy | Precision | Recall | Specificity | F1 | Balanced accuracy | MCC | ROC-AUC | PR-AUC |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Rule baseline | {fmt(metrics['accuracy'])} | {fmt(metrics['precision'])} | {fmt(metrics['recall'])} | {fmt(metrics['specificity'])} | {fmt(metrics['f1'])} | {fmt(metrics['balanced_accuracy'])} | {fmt(metrics['mcc'])} | {fmt(metrics['roc_auc'])} | {fmt(metrics['pr_auc'])} |
| Single LLM | Not run | Not run | Not run | Not run | Not run | Not run | Not run | Not run | Not run |
| Full multi-agent | Not run | Not run | Not run | Not run | Not run | Not run | Not run | Not run | Not run |

## Statistical uncertainty and calibration

Accuracy has a deterministic bootstrap 95% interval stored in `summary.json`. Paired significance tests are Not run because only one method has executed. Brier score, ECE, and reliability-curve data are stored in the same artifact; rule confidence is heuristic and is not claimed to be calibrated.

## Cost and latency analysis

Groundedness and citation correctness are Not run because they require independently reviewed generated explanations. Rule latency and cost are measured in the generated artifacts. Live LLM costs are Not run.

## Groundedness and citation correctness

Both are Not run pending independently reviewed generated explanations.

## Ablations and statistical significance

No-Challenger, no-Verifier, no-RAG, no-Defender, and debate-round configurations are implemented and validated, but their live experiments are Not run.

## Failure analysis

See `FAILURE_ANALYSIS.md` and `failure_cases.csv`. These artifacts contain no private prompts or chain-of-thought.

## Responsible AI discussion

The system is decision support and must not replace a qualified auditor or autonomously accuse or clear material transactions.

## Threats to validity, limitations, and future work

Synthetic labels are audit-risk proxies, not fraud judgments. This decision-support system cannot replace a qualified auditor. Key threats are generator artifacts, synthetic-to-real distribution shift, model-judge bias, provider drift, and missing human annotation. Next work requires blinded human annotation, live frozen-split method runs, paired tests, and external audit-domain review.

## Reproduction

From `Backend/`: run `python scripts/generate_benchmark_dataset.py`, `python scripts/run_rule_baseline.py`, then `python scripts/generate_research_report.py`.
"""
    (output / "RESEARCH_REPORT.md").write_text(report, encoding="utf-8")
    print(f"generated report for {len(dataset)} evaluation rows; {len(failures)} failures")


if __name__ == "__main__": main()
