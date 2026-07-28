#!/usr/bin/env python3
"""Run the experiment matrix over a benchmark.

Examples
--------
    # what would run, what it would cost, no calls made
    python scripts/run_experiment_matrix.py --benchmark uci_audit_v1 --dry-run

    # conditions that need no provider
    python scripts/run_experiment_matrix.py --benchmark uci_audit_v1 \
        --methods rule_baseline logistic_reference tree_reference

    # small live smoke test before committing to the full matrix
    python scripts/run_experiment_matrix.py --benchmark uci_audit_v1 \
        --methods single_llm --limit 10 --max-cost-usd 0.50

    # everything
    python scripts/run_experiment_matrix.py --benchmark uci_audit_v1 --all \
        --max-cost-usd 25

The harness refuses to write a results file it could not produce from real execution:
a missing API key aborts the run instead of emitting placeholder rows.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments import benchmarks  # noqa: E402
from experiments.harness import (  # noqa: E402
    CostLimitExceeded,
    estimate_calls,
    project_cost,
    run_method,
    write_run,
)
from experiments.llm import LLMConfig, ProviderError, ResponseCache  # noqa: E402
from experiments.runners.base import ExperimentConfig, load_config  # noqa: E402

CONFIG_DIR = ROOT / "experiments" / "configs"

DEFAULT_METHODS = [
    "rule_baseline", "logistic_reference", "tree_reference", "single_llm",
    "full_multi_agent", "no_challenger", "no_defender", "no_verifier", "no_rag",
    "one_debate_round",
]

NEEDS_PROVIDER = frozenset({
    "single_llm", "full_multi_agent", "no_challenger", "no_defender", "no_verifier",
    "no_rag", "one_debate_round", "two_debate_rounds",
})


def load_dotenv(path: Path) -> int:
    """Populate os.environ from a .env file without overwriting real environment values."""
    if not path.exists():
        return 0
    loaded = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and value and not os.environ.get(key):
            os.environ[key] = value
            loaded += 1
    return loaded


def build_llm_config(config: ExperimentConfig, args: argparse.Namespace) -> LLMConfig:
    return LLMConfig(
        provider=args.provider or config.provider,
        model=args.model or config.model,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
        timeout_seconds=config.timeout_seconds,
        retries=config.retries,
        use_cache=not args.no_cache,
        price_per_mtok_in=args.price_in,
        price_per_mtok_out=args.price_out,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--benchmark", default="uci_audit_v1",
                        choices=sorted(benchmarks.REGISTRY))
    parser.add_argument("--methods", nargs="+", default=None,
                        help="method names; defaults to the standard matrix")
    parser.add_argument("--all", action="store_true", help="run every config in configs/")
    parser.add_argument("--limit", type=int, default=None,
                        help="use only the first N evaluation cases (smoke tests)")
    parser.add_argument("--max-cost-usd", type=float, default=None,
                        help="abort a run whose projected cost exceeds this ceiling")
    parser.add_argument("--provider", default=None, help="override the configured provider")
    parser.add_argument("--model", default=None, help="override the configured model")
    parser.add_argument("--price-in", type=float, default=None,
                        help="USD per million input tokens, for models absent from the table")
    parser.add_argument("--price-out", type=float, default=None,
                        help="USD per million output tokens")
    parser.add_argument("--no-cache", action="store_true",
                        help="bypass the response cache and force fresh calls")
    parser.add_argument("--dry-run", action="store_true",
                        help="report planned calls and projected cost without calling anything")
    parser.add_argument("--env-file", default=str(ROOT / ".env"))
    args = parser.parse_args()

    load_dotenv(Path(args.env_file))
    benchmark = benchmarks.load(args.benchmark)

    if args.all:
        methods = sorted(p.stem for p in CONFIG_DIR.glob("*.yaml")
                         if p.stem != "no_evidence_retrieval")
    else:
        methods = args.methods or DEFAULT_METHODS

    cases = len(benchmark.evaluation) if args.limit is None else min(
        args.limit, len(benchmark.evaluation))
    print(f"benchmark {benchmark.name}  ({benchmark.label_kind} labels)")
    print(f"evaluation cases: {cases} of {len(benchmark.evaluation)}\n")

    cache = ResponseCache()
    total_projected = 0.0
    plan = []
    for method in methods:
        path = CONFIG_DIR / f"{method}.yaml"
        if not path.exists():
            print(f"  ! no config for {method}, skipping")
            continue
        config = load_config(path)
        llm = build_llm_config(config, args) if method in NEEDS_PROVIDER else None
        calls = estimate_calls(config, cases)
        cost = project_cost(config, llm, cases) if llm else 0.0
        total_projected += cost
        plan.append((config, llm, calls, cost))
        print(f"  {method:<20} calls={calls:<6} projected=${cost:.4f}")

    print(f"\ntotal projected cost: ${total_projected:.2f}")
    if args.max_cost_usd is not None and total_projected > args.max_cost_usd:
        print(f"ABORT: projected ${total_projected:.2f} exceeds ceiling "
              f"${args.max_cost_usd:.2f}")
        return 2
    if args.dry_run:
        print("\ndry run: nothing was executed and no artifacts were written")
        return 0

    failed = []
    for config, llm, _, _ in plan:
        print(f"\n>>> {config.method}")
        try:
            results, report = run_method(
                benchmark, config, llm=llm, limit=args.limit,
                max_cost_usd=args.max_cost_usd, cache=cache)
        except (CostLimitExceeded, ProviderError, ValueError, KeyError) as exc:
            print(f"    FAILED: {type(exc).__name__}: {exc}")
            failed.append(config.method)
            continue
        path = write_run(benchmark, config, results, report, llm)
        print(f"    {report.cases} rows, {report.errors} errors "
              f"({report.parse_failures} parse, {report.provider_failures} provider), "
              f"${report.cost_usd:.4f}, {report.wall_seconds}s, "
              f"cache {report.cache_hits}h/{report.cache_misses}m")
        print(f"    -> {path.relative_to(ROOT)}")

    if failed:
        print(f"\n{len(failed)} method(s) failed: {', '.join(failed)}")
        return 1
    print("\nall methods completed. Next: python scripts/analyze_results.py "
          f"--benchmark {benchmark.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
