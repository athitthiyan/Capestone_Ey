#!/usr/bin/env python3
"""Independently re-annotate benchmark labels with two judges, then adjudicate.

Why this exists
---------------
On ``gl_synthetic_v1`` the label is generator ground truth. Evaluating against it measures
agreement with the generator, not agreement with audit judgement. This script produces a
second, independent label track: two different models annotate every evaluation case
under the written rubric in ``experiments/annotation/ANNOTATION_GUIDE.md``, without
seeing the existing label. Agreement is reported with Cohen's kappa; disagreements go to
a human queue.

The resulting ``adjudicated_labels.csv`` is *not* used automatically. It is a separate
label track a reviewer can compare against the generator labels, and the comparison
itself - how far the generator's notion of risk sits from independent judgement - is a
reportable result.

On ``uci_audit_v1`` the labels are real post-audit findings, so re-annotation measures
model/auditor agreement rather than correcting the labels. That comparison is reported
but never overrides the real label.

Usage
-----
    python scripts/adjudicate_labels.py \
        --benchmark gl_synthetic_v1 \
        --judge-models anthropic:claude-haiku-4-5-20251001 openai:gpt-4o-mini \
        --max-cost-usd 5
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments import benchmarks  # noqa: E402
from experiments.annotation.agreement import cohens_kappa, percentage_agreement  # noqa: E402
from experiments.llm import (  # noqa: E402
    ProviderError,
    ResponseCache,
    build_provider,
    parse_verdict,
)
from experiments.runners.llm_agents import render_case  # noqa: E402
from scripts.run_experiment_matrix import load_dotenv  # noqa: E402
from scripts.score_evidence_quality import build_judges  # noqa: E402

RESULTS = ROOT / "experiments" / "results"

ANNOTATOR_SYSTEM = """\
You are an experienced external auditor annotating a case for a research benchmark.

Apply the rubric exactly:

Label 1 (escalate) - the recorded evidence would cause a competent auditor to raise a
fraud-risk finding: discrepancies large relative to the population, several independent
findings pointing the same way, a material prior-misstatement record, or a control
breakdown that cannot be explained by the evidence available.

Label 0 (clear) - the evidence is consistent with an ordinary transaction or entity. A
screening flag on its own is not grounds for label 1; screens are over-inclusive by
design and clearing a flagged case is a valid annotation.

Annotate what the evidence supports, not what you guess the benchmark intends. If the
evidence is genuinely ambiguous, choose the label you would defend to a review panel and
set confidence below 0.6 so the case can be routed to adjudication.

Respond with a single JSON object and nothing else:

{"prediction": 0|1, "confidence": 0..1, "explanation": "two sentences",
 "citations": ["evidence_id", ...]}
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--benchmark", default="gl_synthetic_v1",
                        choices=sorted(benchmarks.REGISTRY))
    parser.add_argument("--judge-models", nargs="+", default=[])
    parser.add_argument("--split", default="evaluation",
                        choices=["evaluation", "development"])
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
    cases = list(benchmark.split(args.split))
    if args.limit:
        cases = cases[:args.limit]
    if not cases:
        print(f"no cases in split {args.split}")
        return 1

    judges = build_judges(args.judge_models, args.timeout, args.retries, not args.no_cache)
    calls = len(cases) * len(judges)
    projected = sum(c.prices()[0] * 800 / 1e6 + c.prices()[1] * 200 / 1e6
                    for _, c in judges) * len(cases)

    print(f"benchmark {benchmark.name}  split={args.split}  cases={len(cases)}")
    print(f"annotators: {', '.join(f'{n}={c.provider}:{c.model}' for n, c in judges)}")
    print(f"planned calls {calls}, projected cost ${projected:.2f}")
    if benchmark.label_kind == "real":
        print("note: this benchmark has real labels; annotation is reported as "
              "auditor-model agreement and never overrides them")
    if args.max_cost_usd is not None and projected > args.max_cost_usd:
        print(f"ABORT: projected ${projected:.2f} exceeds ceiling ${args.max_cost_usd:.2f}")
        return 2
    if args.dry_run:
        print("dry run: nothing executed")
        return 0

    cache = ResponseCache()
    providers = [(name, build_provider(config, cache)) for name, config in judges]
    annotations: dict[str, dict[str, dict]] = defaultdict(dict)

    for case in cases:
        user = render_case(case, benchmark.corpus, include_evidence=True)
        allowed = set(case.evidence(benchmark.corpus))
        for name, provider in providers:
            try:
                completion = provider.complete(ANNOTATOR_SYSTEM, user)
                verdict = parse_verdict(completion.text, allowed_citations=allowed)
                annotations[case.case_id][name] = {
                    "label": verdict.prediction, "confidence": verdict.confidence,
                    "explanation": verdict.explanation, "citations": verdict.citations,
                    "model": provider.config.model, "error": "",
                    "cost_usd": completion.cost_usd,
                }
            except (ProviderError, ValueError, KeyError, TypeError) as exc:
                annotations[case.case_id][name] = {
                    "label": None, "confidence": None, "explanation": "", "citations": [],
                    "model": provider.config.model,
                    "error": f"{type(exc).__name__}:{exc}", "cost_usd": 0.0,
                }

    names = [name for name, _ in providers]
    paired: dict[str, list[int]] = {name: [] for name in names}
    reference: list[int] = []
    by_case = {case.case_id: case for case in cases}
    for case_id in sorted(annotations):
        values = [annotations[case_id].get(n, {}).get("label") for n in names]
        if all(v is not None for v in values):
            for name, value in zip(names, values):
                paired[name].append(value)
            reference.append(by_case[case_id].label)

    agreement: dict = {"n_paired": len(reference), "annotators": names,
                       "benchmark_label_kind": benchmark.label_kind}
    if len(names) >= 2 and reference:
        a, b = paired[names[0]], paired[names[1]]
        agreement["inter_annotator"] = {
            "percentage_agreement": round(percentage_agreement(a, b), 4),
            "cohens_kappa": round(cohens_kappa(a, b), 4),
        }
        for name in names:
            agreement[f"{name}_vs_benchmark_label"] = {
                "percentage_agreement": round(percentage_agreement(paired[name], reference), 4),
                "cohens_kappa": round(cohens_kappa(paired[name], reference), 4),
            }

    consensus: list[dict] = []
    queue: list[dict] = []
    for case_id in sorted(annotations):
        case = by_case[case_id]
        values = [annotations[case_id].get(n, {}).get("label") for n in names]
        usable = [v for v in values if v is not None]
        counts = Counter(usable)
        if not usable:
            status, adjudicated = "no_usable_annotation", None
        elif len(counts) == 1:
            status, adjudicated = "unanimous", usable[0]
        else:
            status, adjudicated = "disagreement", None
        row = {
            "transaction_id": case_id,
            "benchmark_label": case.label,
            "adjudicated_label": "" if adjudicated is None else adjudicated,
            "status": status,
            "agrees_with_benchmark": ("" if adjudicated is None
                                      else int(adjudicated == case.label)),
            "category": case.category, "difficulty": case.difficulty,
        }
        for name in names:
            entry = annotations[case_id].get(name, {})
            row[f"{name}_label"] = "" if entry.get("label") is None else entry["label"]
            row[f"{name}_confidence"] = entry.get("confidence") or ""
        consensus.append(row)
        if status != "unanimous":
            queue.append(row | {"human_label": "", "adjudicator": "", "rationale": ""})

    directory = RESULTS / benchmark.name / "annotation"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "raw_annotations.json").write_text(
        json.dumps(annotations, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    agreement["unanimous"] = sum(r["status"] == "unanimous" for r in consensus)
    agreement["disagreement"] = sum(r["status"] == "disagreement" for r in consensus)
    agreement["failed"] = sum(r["status"] == "no_usable_annotation" for r in consensus)
    agreement["unanimous_matching_benchmark_label"] = sum(
        1 for r in consensus if r["status"] == "unanimous" and r["agrees_with_benchmark"] == 1)
    (directory / "agreement.json").write_text(
        json.dumps(agreement, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def dump(path: Path, rows: list[dict]) -> None:
        if not rows:
            path.write_text("", encoding="utf-8")
            return
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)

    dump(directory / "adjudicated_labels.csv", consensus)
    dump(directory / "adjudication_queue.csv", queue)

    print(f"\nunanimous {agreement['unanimous']}, disagreement "
          f"{agreement['disagreement']}, failed {agreement['failed']}")
    if "inter_annotator" in agreement:
        print(f"inter-annotator kappa: {agreement['inter_annotator']['cohens_kappa']}")
        for name in names:
            key = f"{name}_vs_benchmark_label"
            print(f"{name} vs benchmark label: kappa {agreement[key]['cohens_kappa']}")
    print(f"-> {directory.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
