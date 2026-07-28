from __future__ import annotations

import json
import time
from collections.abc import Callable
from uuid import uuid4

from experiments.schema import ExperimentResult


def run(rows: list[dict[str, str]], complete: Callable[[dict[str, str]], dict], *, provider: str,
        model: str, prompt_version: str = "single-v1") -> list[ExperimentResult]:
    """Run a provider adapter. Tests inject a mock; this module never silently fixtures live results."""
    run_id = f"single-{uuid4().hex[:12]}"
    output = []
    forbidden = {"risk_label", "risk_category", "difficulty", "split", "generator_version"}
    for source in rows:
        row = {key: value for key, value in source.items() if key not in forbidden}
        started = time.perf_counter()
        try:
            response = complete(row)
            result = ExperimentResult(
                transaction_id=row["transaction_id"], method="single_llm",
                prediction=int(response["prediction"]), confidence=float(response["confidence"]),
                explanation=str(response.get("explanation", "")),
                evidence_ids=list(response.get("evidence_ids", [])), citations=list(response.get("citations", [])),
                input_tokens=int(response.get("input_tokens", 0)), output_tokens=int(response.get("output_tokens", 0)),
                cost_usd=float(response.get("cost_usd", 0)), latency_ms=(time.perf_counter() - started) * 1000,
                model=model, provider=provider, prompt_version=prompt_version, run_id=run_id,
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            result = ExperimentResult(transaction_id=row["transaction_id"], method="single_llm",
                prediction=0, confidence=0, model=model, provider=provider, prompt_version=prompt_version,
                run_id=run_id, latency_ms=(time.perf_counter() - started) * 1000,
                error=f"parse_failure:{type(exc).__name__}")
        result.validate(); output.append(result)
    return output
