"""Experiment orchestration: config x benchmark -> a run directory.

Every run writes three artifacts next to each other so a result can never drift from the
settings that produced it:

``<method>.jsonl``            one row per evaluation case, in the frozen schema
``<method>.config.json``      the fully resolved configuration, plus its SHA-256
``<method>.run.json``         wall-clock, cost, cache hit rate, error counts

The resolved-config SHA-256 is stamped into every result row, so an analysis script can
refuse to mix rows produced under different settings.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from experiments.benchmarks import Benchmark
from experiments.llm import LLMConfig, ProviderError, ResponseCache, build_provider
from experiments.runners.base import ExperimentConfig
from experiments.runners.baselines import run_rule_baseline, run_supervised_reference
from experiments.runners.llm_agents import run_multi_agent, run_single_llm
from experiments.schema import ExperimentResult

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "experiments" / "runs"

LLM_METHODS = frozenset({
    "single_llm", "full_multi_agent", "no_challenger", "no_defender", "no_verifier",
    "no_rag", "no_evidence_retrieval", "one_debate_round", "two_debate_rounds",
})
DETERMINISTIC_METHODS = frozenset({"rule_baseline"})
SUPERVISED_METHODS = {"logistic_reference": "logistic", "tree_reference": "tree"}


class CostLimitExceeded(RuntimeError):
    """Raised before a run starts if its projected cost breaches the configured ceiling."""


@dataclass
class RunReport:
    method: str
    benchmark: str
    cases: int
    errors: int
    parse_failures: int
    provider_failures: int
    cost_usd: float
    wall_seconds: float
    cache_hits: int
    cache_misses: int
    config_sha256: str
    started_at: str
    finished_at: str


def resolved_config_sha256(config: ExperimentConfig, benchmark: str,
                           llm: LLMConfig | None) -> str:
    payload = {"experiment": asdict(config), "benchmark": benchmark}
    if llm is not None:
        payload["llm"] = {k: v for k, v in asdict(llm).items() if k != "api_key_env"}
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def estimate_calls(config: ExperimentConfig, cases: int) -> int:
    """Number of model calls a run will make. Used by the cost guard, exact by construction."""
    if config.method in DETERMINISTIC_METHODS or config.method in SUPERVISED_METHODS:
        return 0
    if config.method == "single_llm":
        return cases
    per_case = 1  # detective
    rounds = max(0, config.debate_rounds)
    per_case += rounds * (int(config.challenger_enabled) + int(config.defender_enabled))
    per_case += int(config.verifier_enabled)
    return cases * per_case


def project_cost(config: ExperimentConfig, llm: LLMConfig, cases: int, *,
                 mean_input_tokens: int = 900, mean_output_tokens: int = 260) -> float:
    calls = estimate_calls(config, cases)
    price_in, price_out = llm.prices()
    return round(
        calls * (mean_input_tokens / 1e6 * price_in + mean_output_tokens / 1e6 * price_out), 6)


def run_method(benchmark: Benchmark, config: ExperimentConfig, *,
               llm: LLMConfig | None = None, limit: int | None = None,
               max_cost_usd: float | None = None,
               cache: ResponseCache | None = None) -> tuple[list[ExperimentResult], RunReport]:
    cases = benchmark.evaluation
    if limit is not None:
        cases = cases[:limit]
    if not cases:
        raise ValueError(f"benchmark {benchmark.name} has no evaluation cases")

    started_at = datetime.now(timezone.utc).isoformat()
    clock = time.perf_counter()
    cache = cache if cache is not None else ResponseCache()

    if config.method in DETERMINISTIC_METHODS:
        results = run_rule_baseline(cases, benchmark.name, method=config.method)
    elif config.method in SUPERVISED_METHODS:
        results = run_supervised_reference(
            benchmark.development, cases, benchmark.name,
            kind=SUPERVISED_METHODS[config.method])
    elif config.method in LLM_METHODS:
        if llm is None:
            raise ValueError(f"method {config.method} requires an LLMConfig")
        projected = project_cost(config, llm, len(cases))
        if max_cost_usd is not None and projected > max_cost_usd:
            raise CostLimitExceeded(
                f"{config.method} on {len(cases)} cases projects ${projected:.2f}, "
                f"above the ${max_cost_usd:.2f} ceiling. Raise --max-cost-usd or "
                f"reduce --limit."
            )
        provider = build_provider(llm, cache)
        runner = run_single_llm if config.method == "single_llm" else run_multi_agent
        results = runner(cases, provider, benchmark.corpus, config)
    else:
        raise ValueError(f"unknown method {config.method!r}")

    digest = resolved_config_sha256(config, benchmark.name, llm)
    for result in results:
        result.resolved_config_sha256 = digest

    errors = [r for r in results if r.error]
    report = RunReport(
        method=config.method, benchmark=benchmark.name, cases=len(results),
        errors=len(errors),
        parse_failures=sum(1 for r in errors if r.error.startswith("parse_failure")),
        provider_failures=sum(1 for r in errors if r.error.startswith("provider_failure")),
        cost_usd=round(sum(r.cost_usd for r in results), 6),
        wall_seconds=round(time.perf_counter() - clock, 3),
        cache_hits=cache.hits, cache_misses=cache.misses, config_sha256=digest,
        started_at=started_at, finished_at=datetime.now(timezone.utc).isoformat())
    return results, report


def write_run(benchmark: Benchmark, config: ExperimentConfig, results: list[ExperimentResult],
              report: RunReport, llm: LLMConfig | None) -> Path:
    directory = RUNS / benchmark.name
    directory.mkdir(parents=True, exist_ok=True)

    rows = directory / f"{config.method}.jsonl"
    rows.write_text(
        "".join(json.dumps(r.to_dict(), sort_keys=True) + "\n" for r in results),
        encoding="utf-8")

    payload = {"experiment": asdict(config), "benchmark": benchmark.name,
               "sha256": report.config_sha256}
    if llm is not None:
        payload["llm"] = {k: v for k, v in asdict(llm).items() if k != "api_key_env"}
    (directory / f"{config.method}.config.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    (directory / f"{config.method}.run.json").write_text(
        json.dumps(asdict(report), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return rows


def load_run(benchmark_name: str, method: str) -> list[dict]:
    path = RUNS / benchmark_name / f"{method}.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def available_runs(benchmark_name: str) -> list[str]:
    directory = RUNS / benchmark_name
    if not directory.exists():
        return []
    return sorted(p.stem for p in directory.glob("*.jsonl"))


__all__ = [
    "CostLimitExceeded", "RunReport", "available_runs", "estimate_calls", "load_run",
    "project_cost", "resolved_config_sha256", "run_method", "write_run",
    "ProviderError",
]
