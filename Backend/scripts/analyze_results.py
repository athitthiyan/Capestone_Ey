#!/usr/bin/env python3
"""Turn run artifacts into the reported results.

Reads every ``experiments/runs/<benchmark>/*.jsonl`` produced by the matrix runner and
writes, under ``experiments/results/<benchmark>/``:

``summary.json``            per-method metrics, bootstrap intervals, operational figures
``metrics.csv``             flat table for the README
``statistical_tests.json``  paired McNemar tests against the reference, Holm-corrected
``failure_cases.csv``       every disagreement with the gold label, for error analysis
``RESULTS.md``              the tables, generated - never hand-edited

Guarantees that keep the numbers honest:

* A method is analysed only if it covers **every** evaluation case. Partial runs are
  reported as incomplete rather than scored on the subset they happened to finish, so
  no method can improve its score by dropping hard cases.
* Methods that were never run are listed under ``not_run`` and appear as ``Not run`` in
  the tables. Nothing is imputed.
* Rows carrying an ``error`` are counted in the failure rate and, because the schema
  forces them to ``prediction=0``, are scored as they behaved: a wrong answer.

Usage
-----
    python scripts/analyze_results.py --benchmark uci_audit_v1
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments import benchmarks  # noqa: E402
from experiments.harness import RUNS, available_runs, load_run  # noqa: E402
from experiments.metrics import classification_metrics, operational_metrics  # noqa: E402
from experiments.statistics import (  # noqa: E402
    bootstrap_ci,
    bootstrap_metric_ci,
    holm_bonferroni,
    mcnemar_test,
)

RESULTS = ROOT / "experiments" / "results"
REFERENCE_METHOD = "rule_baseline"

ALL_METHODS = [
    "rule_baseline", "logistic_reference", "tree_reference", "single_llm",
    "full_multi_agent", "no_challenger", "no_defender", "no_verifier", "no_rag",
    "one_debate_round", "two_debate_rounds",
]

CI_METRICS = ("accuracy", "precision", "recall", "specificity", "f1",
              "balanced_accuracy", "mcc")

METRIC_FUNCTIONS = {
    name: (lambda labels, predictions, scores, key=name:
           classification_metrics(labels, predictions).get(key))
    for name in CI_METRICS
}


def _aligned(rows: list[dict], cases) -> tuple[list[int], list[int], list[float], list]:
    by_id = {row["transaction_id"]: row for row in rows}
    labels, predictions, scores, ordered = [], [], [], []
    for case in cases:
        row = by_id[case.case_id]
        labels.append(case.label)
        predictions.append(int(row["prediction"]))
        scores.append(float(row["confidence"]))
        ordered.append(case)
    return labels, predictions, scores, ordered


def _slice_metrics(labels, predictions, scores, cases, attribute: str) -> dict:
    groups: dict[str, list[int]] = {}
    for index, case in enumerate(cases):
        groups.setdefault(getattr(case, attribute), []).append(index)
    output = {}
    for name, index in sorted(groups.items()):
        output[name] = classification_metrics(
            [labels[i] for i in index], [predictions[i] for i in index],
            [scores[i] for i in index])
    return output


def analyse_method(method: str, rows: list[dict], benchmark) -> dict:
    evaluation = benchmark.evaluation
    expected = {case.case_id for case in evaluation}
    seen = [row["transaction_id"] for row in rows]

    if len(seen) != len(set(seen)):
        return {"status": "invalid", "reason": "duplicate transaction ids in run output"}
    missing = expected - set(seen)
    unknown = set(seen) - expected
    if missing or unknown:
        return {"status": "incomplete",
                "reason": (f"run covers {len(seen)} of {len(expected)} evaluation cases "
                           f"(missing {len(missing)}, unknown {len(unknown)}); partial "
                           f"runs are not scored"),
                "missing": sorted(missing)[:20], "unknown": sorted(unknown)[:20]}

    digests = {row.get("resolved_config_sha256", "") for row in rows}
    labels, predictions, scores, cases = _aligned(rows, evaluation)

    classification = classification_metrics(labels, predictions, scores)
    intervals = {
        name: bootstrap_metric_ci(labels, predictions, scores, METRIC_FUNCTIONS[name])
        for name in CI_METRICS
    }

    operational = operational_metrics(rows)
    latencies = [float(r["latency_ms"]) for r in rows if not r.get("error")]
    costs = [float(r["cost_usd"]) for r in rows if not r.get("error")]
    operational["latency_ms_ci"] = bootstrap_ci(latencies) if latencies else None
    operational["latency_ms_median_ci"] = (
        bootstrap_ci(latencies, statistic=median) if latencies else None)
    operational["cost_usd_ci"] = bootstrap_ci(costs) if costs else None

    grounded = [float(r["groundedness"]) for r in rows if r.get("groundedness") is not None]
    citation = [float(r["citation_correctness"]) for r in rows
                if r.get("citation_correctness") is not None]
    operational["groundedness_ci"] = bootstrap_ci(grounded) if grounded else None
    operational["citation_correctness_ci"] = bootstrap_ci(citation) if citation else None
    operational["groundedness_scored"] = len(grounded)
    operational["citation_correctness_scored"] = len(citation)

    return {
        "status": "complete",
        "method": method,
        "n": len(labels),
        "classification": classification,
        "confidence_intervals": intervals,
        "operational": operational,
        "per_category": _slice_metrics(labels, predictions, scores, cases, "category"),
        "per_difficulty": _slice_metrics(labels, predictions, scores, cases, "difficulty"),
        "config_sha256": sorted(digests),
        "model": sorted({row.get("model", "") for row in rows}),
        "prompt_version": sorted({row.get("prompt_version", "") for row in rows}),
    }


def paired_tests(analysed: dict[str, dict], runs: dict[str, list[dict]], benchmark,
                 reference: str) -> dict:
    complete = {m: a for m, a in analysed.items() if a.get("status") == "complete"}
    if reference not in complete:
        return {"reference": reference, "status": "reference method has no complete run",
                "comparisons": {}}
    labels, reference_predictions, _, _ = _aligned(runs[reference], benchmark.evaluation)

    comparisons: dict[str, dict] = {}
    p_values: dict[str, float] = {}
    for method in complete:
        if method == reference:
            continue
        _, predictions, _, _ = _aligned(runs[method], benchmark.evaluation)
        test = mcnemar_test(labels, reference_predictions, predictions)
        comparisons[method] = test
        p_values[method] = test["p_value"]

    corrected = holm_bonferroni(p_values)
    for method, values in corrected.items():
        comparisons[method].update(values)
    return {
        "reference": reference,
        "family_size": len(p_values),
        "correction": "Holm-Bonferroni, family-wise alpha 0.05",
        "interpretation": ("discordant_first_only counts cases the reference got right and "
                           "the method got wrong; discordant_second_only is the reverse"),
        "comparisons": comparisons,
    }


def failure_rows(analysed: dict[str, dict], runs: dict[str, list[dict]], benchmark) -> list[dict]:
    by_case = {case.case_id: case for case in benchmark.evaluation}
    output = []
    for method, analysis in analysed.items():
        if analysis.get("status") != "complete":
            continue
        for row in runs[method]:
            case = by_case[row["transaction_id"]]
            prediction = int(row["prediction"])
            if prediction == case.label:
                continue
            output.append({
                "method": method, "transaction_id": case.case_id,
                "gold_label": case.label, "prediction": prediction,
                "error_type": "false_positive" if prediction == 1 else "false_negative",
                "confidence": row["confidence"], "category": case.category,
                "difficulty": case.difficulty,
                "run_error": row.get("error", ""),
                "citations": ";".join(row.get("citations") or []),
                "explanation": (row.get("explanation") or "").replace("\n", " ")[:500],
            })
    return output


def write_metrics_csv(path: Path, analysed: dict[str, dict]) -> None:
    columns = ["method", "status", "n", "accuracy", "accuracy_lo", "accuracy_hi",
               "precision", "recall", "specificity", "specificity_lo", "specificity_hi",
               "f1", "balanced_accuracy", "mcc", "roc_auc", "brier_score",
               "expected_calibration_error", "mean_groundedness",
               "mean_citation_correctness", "mean_latency_ms", "p95_latency_ms",
               "mean_cost_usd", "failure_rate"]
    lines = [",".join(columns)]
    for method in ALL_METHODS:
        analysis = analysed.get(method)
        if analysis is None:
            lines.append(f"{method},not_run" + "," * (len(columns) - 2))
            continue
        if analysis.get("status") != "complete":
            lines.append(f"{method},{analysis['status']}" + "," * (len(columns) - 2))
            continue
        c = analysis["classification"]
        ci = analysis["confidence_intervals"]
        o = analysis["operational"]

        def fmt(value):
            return "" if value is None else (f"{value:.6f}" if isinstance(value, float)
                                             else str(value))

        lines.append(",".join(fmt(v) for v in [
            method, "complete", analysis["n"], c["accuracy"],
            ci["accuracy"]["lower"], ci["accuracy"]["upper"], c["precision"], c["recall"],
            c["specificity"], ci["specificity"]["lower"], ci["specificity"]["upper"],
            c["f1"], c["balanced_accuracy"], c["mcc"], c.get("roc_auc"),
            c.get("brier_score"), c.get("expected_calibration_error"),
            o.get("mean_groundedness"), o.get("mean_citation_correctness"),
            o.get("mean_latency_ms"), o.get("p95_latency_ms"), o.get("mean_cost_usd"),
            o.get("failure_rate"),
        ]))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def render_markdown(benchmark, analysed: dict[str, dict], tests: dict, not_run: list[str],
                    manifest: dict) -> str:
    def cell(value, digits=3):
        return "–" if value is None else f"{value:.{digits}f}"

    def interval(analysis, name):
        ci = analysis["confidence_intervals"][name]
        if ci["lower"] is None:
            return cell(ci["estimate"])
        return f"{cell(ci['estimate'])} [{cell(ci['lower'])}, {cell(ci['upper'])}]"

    records = manifest.get("records", {})
    lines = [
        f"# Results — `{benchmark.name}`",
        "",
        "*Generated by `scripts/analyze_results.py`. Do not edit by hand.*",
        "",
        f"- Label kind: **{benchmark.label_kind}**",
        f"- {benchmark.description}",
        f"- Evaluation cases: **{len(benchmark.evaluation)}** "
        f"({records.get('evaluation_positive', '?')} positive / "
        f"{records.get('evaluation_negative', '?')} negative)",
        f"- Development cases (never scored): {len(benchmark.development)}",
        "",
        "## Classification, with 95% bootstrap intervals",
        "",
        "| Method | n | Accuracy | Precision | Recall | Specificity | F1 | MCC |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for method in ALL_METHODS:
        analysis = analysed.get(method)
        if analysis is None:
            lines.append(f"| `{method}` | – | Not run | Not run | Not run | Not run "
                         f"| Not run | Not run |")
            continue
        if analysis.get("status") != "complete":
            lines.append(f"| `{method}` | – | {analysis['status']}: "
                         f"{analysis.get('reason', '')} | | | | | |")
            continue
        c = analysis["classification"]
        lines.append(
            f"| `{method}` | {analysis['n']} | {interval(analysis, 'accuracy')} "
            f"| {cell(c['precision'])} | {cell(c['recall'])} "
            f"| {interval(analysis, 'specificity')} | {interval(analysis, 'f1')} "
            f"| {cell(c['mcc'])} |")

    lines += ["", "## Evidence quality, cost and latency", "",
              "| Method | Groundedness | Citation correctness | Scored | Mean latency (ms) "
              "| p95 latency (ms) | Mean cost (USD) | Failure rate |",
              "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for method in ALL_METHODS:
        analysis = analysed.get(method)
        if analysis is None or analysis.get("status") != "complete":
            lines.append(f"| `{method}` | Not run | Not run | – | – | – | – | – |")
            continue
        o = analysis["operational"]
        lines.append(
            f"| `{method}` | {cell(o.get('mean_groundedness'))} "
            f"| {cell(o.get('mean_citation_correctness'))} "
            f"| {o.get('groundedness_scored', 0)} "
            f"| {cell(o.get('mean_latency_ms'), 1)} | {cell(o.get('p95_latency_ms'), 1)} "
            f"| {cell(o.get('mean_cost_usd'), 5)} | {cell(o.get('failure_rate'))} |")

    comparisons = tests.get("comparisons", {})
    lines += ["", f"## Paired McNemar tests against `{tests.get('reference')}`", ""]
    if not comparisons:
        lines.append("_No completed method to compare against the reference yet._")
    else:
        lines += [
            f"Family of {tests.get('family_size')} comparisons, "
            f"{tests.get('correction')}.", "",
            "| Method | Reference right, method wrong | Method right, reference wrong "
            "| p | p (Holm) | Significant |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
        for method, test in sorted(comparisons.items()):
            lines.append(
                f"| `{method}` | {test['discordant_first_only']} "
                f"| {test['discordant_second_only']} | {test['p_value']:.4f} "
                f"| {test.get('p_adjusted', float('nan')):.4f} "
                f"| {'yes' if test.get('significant') else 'no'} |")

    if not_run:
        lines += ["", "## Not run", "",
                  "These conditions have no results artifact. They are reported as `Not run` "
                  "rather than estimated:", ""]
        lines += [f"- `{method}`" for method in not_run]

    lines += ["", "## Reading these numbers", "",
              "- `rule_baseline` is the incumbent screen, uses no labels, and is the "
              "comparator the system must beat.",
              "- `logistic_reference` and `tree_reference` are **fitted on the development "
              "split** and therefore see labels the LLM conditions never do. They are a "
              "ceiling on how much signal the recorded fields contain, not competitors.",
              "- LLM conditions are zero-shot: they receive no labelled examples.",
              "- Intervals are percentile bootstrap over 2,000 case-level resamples.", ""]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--benchmark", default="uci_audit_v1",
                        choices=sorted(benchmarks.REGISTRY))
    parser.add_argument("--reference", default=REFERENCE_METHOD)
    args = parser.parse_args()

    benchmark = benchmarks.load(args.benchmark)
    present = available_runs(benchmark.name)
    if not present:
        print(f"no run artifacts under {RUNS / benchmark.name}. "
              f"Run scripts/run_experiment_matrix.py first.")
        return 1

    runs = {method: load_run(benchmark.name, method) for method in present}
    analysed = {method: analyse_method(method, rows, benchmark)
                for method, rows in runs.items()}
    not_run = [m for m in ALL_METHODS if m not in analysed]

    tests = paired_tests(analysed, runs, benchmark, args.reference)
    failures = failure_rows(analysed, runs, benchmark)

    directory = RESULTS / benchmark.name
    directory.mkdir(parents=True, exist_ok=True)

    summary = {
        "benchmark": benchmark.name,
        "label_kind": benchmark.label_kind,
        "description": benchmark.description,
        "evaluation_cases": len(benchmark.evaluation),
        "development_cases": len(benchmark.development),
        "dataset_manifest": benchmark.manifest.get("provenance", {}),
        "executed_methods": sorted(m for m, a in analysed.items()
                                   if a.get("status") == "complete"),
        "incomplete_methods": sorted(m for m, a in analysed.items()
                                     if a.get("status") != "complete"),
        "not_run": not_run,
        "methods": analysed,
        "statistical_tests": tests,
    }
    (directory / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    (directory / "statistical_tests.json").write_text(
        json.dumps(tests, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_metrics_csv(directory / "metrics.csv", analysed)

    with (directory / "failure_cases.csv").open("w", newline="", encoding="utf-8") as handle:
        columns = ["method", "transaction_id", "gold_label", "prediction", "error_type",
                   "confidence", "category", "difficulty", "run_error", "citations",
                   "explanation"]
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(failures)

    (directory / "RESULTS.md").write_text(
        render_markdown(benchmark, analysed, tests, not_run, benchmark.manifest),
        encoding="utf-8")

    print(f"analysed {len(summary['executed_methods'])} complete method(s) on "
          f"{benchmark.name}")
    for method in summary["executed_methods"]:
        c = analysed[method]["classification"]
        print(f"  {method:<20} acc={c['accuracy']:.3f} spec="
              f"{(c['specificity'] if c['specificity'] is not None else float('nan')):.3f} "
              f"rec={(c['recall'] if c['recall'] is not None else float('nan')):.3f} "
              f"f1={(c['f1'] if c['f1'] is not None else float('nan')):.3f}")
    if summary["incomplete_methods"]:
        print(f"  incomplete: {', '.join(summary['incomplete_methods'])}")
    if not_run:
        print(f"  not run: {', '.join(not_run)}")
    print(f"-> {(directory / 'RESULTS.md').relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
