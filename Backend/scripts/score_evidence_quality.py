#!/usr/bin/env python3
"""Score groundedness and citation correctness on completed runs, with two judges.

The judges are label-blind and method-blind: they see only the evidence, the explanation
and the citations. Two different models judge every item independently; items where they
differ by more than one rubric step are written to an adjudication queue for a human
instead of being averaged away.

Outputs, under ``experiments/results/<benchmark>/evidence_quality/``:

``<method>.judgments.json``   every raw judgment from every judge, with reasoning
``<method>.agreement.json``   percentage agreement and quadratic-weighted Cohen's kappa
``adjudication_queue.csv``    items needing a human decision, one row per item and metric

Resolved scores are written back into ``experiments/runs/<benchmark>/<method>.jsonl`` so
``analyze_results.py`` picks them up on the next pass.

Usage
-----
    python scripts/score_evidence_quality.py --benchmark uci_audit_v1 \
        --methods single_llm full_multi_agent \
        --judge-models claude-haiku-4-5-20251001 gpt-4o-mini \
        --max-cost-usd 5
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments import benchmarks  # noqa: E402
from experiments.annotation.agreement import cohens_kappa, percentage_agreement  # noqa: E402
from experiments.evaluators.judge import (  # noqa: E402
    AgreementReport,
    Judgment,
    judge_row,
    reconcile,
)
from experiments.harness import RUNS, available_runs, load_run  # noqa: E402
from experiments.llm import LLMConfig, ResponseCache, build_provider  # noqa: E402
from scripts.run_experiment_matrix import load_dotenv  # noqa: E402

RESULTS = ROOT / "experiments" / "results"
METRICS = ("groundedness", "citation_correctness")

DEFAULT_JUDGES = [("judge_a", "anthropic", "claude-haiku-4-5-20251001"),
                  ("judge_b", "openai", "gpt-4o-mini")]


def build_judges(specs: list[str], timeout: int, retries: int,
                 use_cache: bool) -> list[tuple[str, LLMConfig]]:
    """``specs`` are ``provider:model`` pairs, or bare models resolved by prefix."""
    if not specs:
        return [(name, LLMConfig(provider=provider, model=model, temperature=0.0,
                                 max_tokens=400, timeout_seconds=timeout, retries=retries,
                                 use_cache=use_cache))
                for name, provider, model in DEFAULT_JUDGES]
    judges = []
    for index, spec in enumerate(specs):
        if ":" in spec:
            provider, model = spec.split(":", 1)
        else:
            model = spec
            provider = "anthropic" if model.startswith("claude") else "openai"
        judges.append((f"judge_{chr(ord('a') + index)}",
                       LLMConfig(provider=provider, model=model, temperature=0.0,
                                 max_tokens=400, timeout_seconds=timeout, retries=retries,
                                 use_cache=use_cache)))
    return judges


def agreement_report(metric: str, judgments: dict[str, list[Judgment]],
                     names: list[str]) -> AgreementReport:
    if len(names) < 2:
        return AgreementReport(metric, names[0] if names else "", "", 0)
    first_name, second_name = names[0], names[1]
    paired_a: list[float] = []
    paired_b: list[float] = []
    for items in judgments.values():
        by_judge = {j.judge: getattr(j, metric) for j in items}
        a, b = by_judge.get(first_name), by_judge.get(second_name)
        if a is not None and b is not None:
            paired_a.append(a)
            paired_b.append(b)

    report = AgreementReport(metric, first_name, second_name, len(paired_a))
    if not paired_a:
        return report
    report.percentage_agreement = round(percentage_agreement(paired_a, paired_b), 4)
    try:
        report.cohens_kappa_quadratic = round(
            cohens_kappa(paired_a, paired_b, weights="quadratic"), 4)
    except (ValueError, ZeroDivisionError):
        report.cohens_kappa_quadratic = None
    report.exact_match = sum(a == b for a, b in zip(paired_a, paired_b))
    report.within_one_step = sum(abs(a - b) <= 0.5 for a, b in zip(paired_a, paired_b))
    report.distribution = {
        first_name: {str(v): paired_a.count(v) for v in sorted(set(paired_a))},
        second_name: {str(v): paired_b.count(v) for v in sorted(set(paired_b))},
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--benchmark", default="uci_audit_v1",
                        choices=sorted(benchmarks.REGISTRY))
    parser.add_argument("--methods", nargs="+", default=None,
                        help="defaults to every method with a run artifact")
    parser.add_argument("--judge-models", nargs="+", default=[],
                        help="provider:model pairs; two are expected")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--max-cost-usd", type=float, default=None)
    parser.add_argument("--timeout", type=int, default=90)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--env-file", default=str(ROOT / ".env"))
    args = parser.parse_args()

    load_dotenv(Path(args.env_file))
    benchmark = benchmarks.load(args.benchmark)
    methods = args.methods or available_runs(benchmark.name)
    if not methods:
        print(f"no run artifacts under {RUNS / benchmark.name}")
        return 1

    judges = build_judges(args.judge_models, args.timeout, args.retries, not args.no_cache)
    if len(judges) < 2:
        print("WARNING: fewer than two judges; inter-judge agreement cannot be computed")

    cases = {case.case_id: case for case in benchmark.evaluation}
    scored_rows = 0
    for method in methods:
        rows = load_run(benchmark.name, method)
        rows = [r for r in rows if r["transaction_id"] in cases]
        if args.limit:
            rows = rows[:args.limit]
        scored_rows += len(rows) * len(judges)
    price_estimate = sum(
        config.prices()[0] * 700 / 1e6 + config.prices()[1] * 120 / 1e6
        for _, config in judges) * (scored_rows / max(1, len(judges)))

    print(f"benchmark {benchmark.name}")
    print(f"methods:  {', '.join(methods)}")
    print(f"judges:   {', '.join(f'{n}={c.provider}:{c.model}' for n, c in judges)}")
    print(f"planned judge calls: {scored_rows}, projected cost ${price_estimate:.2f}")
    if args.max_cost_usd is not None and price_estimate > args.max_cost_usd:
        print(f"ABORT: projected ${price_estimate:.2f} exceeds ceiling ${args.max_cost_usd:.2f}")
        return 2
    if args.dry_run:
        print("dry run: nothing executed")
        return 0

    cache = ResponseCache()
    providers = [(name, build_provider(config, cache)) for name, config in judges]
    directory = RESULTS / benchmark.name / "evidence_quality"
    directory.mkdir(parents=True, exist_ok=True)
    queue: list[dict] = []

    for method in methods:
        rows = load_run(benchmark.name, method)
        rows = [r for r in rows if r["transaction_id"] in cases]
        if args.limit:
            rows = rows[:args.limit]
        if not rows:
            continue

        judgments: dict[str, list[Judgment]] = defaultdict(list)
        for row in rows:
            case = cases[row["transaction_id"]]
            evidence = case.evidence(benchmark.corpus)
            for name, provider in providers:
                judgments[case.case_id].append(judge_row(
                    provider, name, case.case_id, evidence,
                    row.get("explanation", ""), row.get("citations") or []))

        (directory / f"{method}.judgments.json").write_text(
            json.dumps({case_id: [j.to_dict() for j in items]
                        for case_id, items in sorted(judgments.items())},
                       indent=2, sort_keys=True) + "\n", encoding="utf-8")

        names = [name for name, _ in providers]
        reports = {}
        resolved: dict[str, dict[str, float]] = defaultdict(dict)
        for metric in METRICS:
            reports[metric] = agreement_report(metric, judgments, names).to_dict()
            rows_for_metric = reconcile(judgments, metric)
            escalated = 0
            for entry in rows_for_metric:
                if entry.needs_human:
                    escalated += 1
                    queue.append({
                        "benchmark": benchmark.name, "method": method,
                        "transaction_id": entry.transaction_id, "metric": metric,
                        "scores": json.dumps(entry.scores), "gap": entry.gap,
                        "notes": entry.notes, "human_score": "", "adjudicator": "",
                    })
                elif entry.resolved is not None:
                    resolved[entry.transaction_id][metric] = entry.resolved
            reports[metric]["escalated_to_human"] = escalated
            reports[metric]["resolved_automatically"] = len(rows_for_metric) - escalated

        (directory / f"{method}.agreement.json").write_text(
            json.dumps(reports, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        path = RUNS / benchmark.name / f"{method}.jsonl"
        original = load_run(benchmark.name, method)
        for row in original:
            scores = resolved.get(row["transaction_id"], {})
            if "groundedness" in scores:
                row["groundedness"] = scores["groundedness"]
            if "citation_correctness" in scores:
                row["citation_correctness"] = scores["citation_correctness"]
        path.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in original),
                        encoding="utf-8")

        summary = reports["groundedness"]
        print(f"  {method:<20} n={summary['n']} "
              f"agreement={summary.get('percentage_agreement')} "
              f"kappa={summary.get('cohens_kappa_quadratic')} "
              f"escalated={summary.get('escalated_to_human')}")

    with (directory / "adjudication_queue.csv").open("w", newline="",
                                                     encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "benchmark", "method", "transaction_id", "metric", "scores", "gap", "notes",
            "human_score", "adjudicator"])
        writer.writeheader()
        writer.writerows(queue)

    print(f"\n{len(queue)} item(s) queued for human adjudication -> "
          f"{(directory / 'adjudication_queue.csv').relative_to(ROOT)}")
    print("Re-run scripts/analyze_results.py to fold the resolved scores into the tables.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
