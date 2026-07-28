from __future__ import annotations

import csv
import json
from pathlib import Path

from experiments.schema import ExperimentResult


def load_candidate(path: Path, expected_ids: set[str]) -> list[ExperimentResult]:
    with path.open(encoding="utf-8", newline="") as handle: rows = list(csv.DictReader(handle))
    if not rows: raise ValueError("prediction file is empty")
    required = {"transaction_id", "method", "prediction", "confidence", "explanation", "evidence_ids", "citations", "input_tokens", "output_tokens", "cost_usd", "latency_ms", "model", "provider", "prompt_version", "run_id", "experiment_timestamp", "random_seed", "resolved_config_sha256", "error"}
    missing_columns = required - set(rows[0])
    if missing_columns: raise ValueError(f"missing required columns: {sorted(missing_columns)}")
    ids = [row["transaction_id"] for row in rows]
    if len(ids) != len(set(ids)): raise ValueError("duplicate transaction IDs")
    if set(ids) != expected_ids: raise ValueError(f"prediction IDs do not match frozen split: missing={len(expected_ids-set(ids))}, unknown={len(set(ids)-expected_ids)}")
    output = []
    for row in rows:
        try: prediction = int(row["prediction"])
        except ValueError as exc: raise ValueError("prediction must be 0 or 1") from exc
        result = ExperimentResult(transaction_id=row["transaction_id"], method=row["method"], prediction=prediction,
            confidence=float(row["confidence"]), explanation=row["explanation"], evidence_ids=json.loads(row["evidence_ids"] or "[]"),
            citations=json.loads(row["citations"] or "[]"), groundedness=float(row["groundedness"]) if row.get("groundedness") else None,
            citation_correctness=float(row["citation_correctness"]) if row.get("citation_correctness") else None,
            input_tokens=int(row["input_tokens"]), output_tokens=int(row["output_tokens"]), cost_usd=float(row["cost_usd"]),
            latency_ms=float(row["latency_ms"]), model=row["model"], provider=row["provider"], prompt_version=row["prompt_version"], run_id=row["run_id"], experiment_timestamp=row["experiment_timestamp"], random_seed=int(row["random_seed"]), resolved_config_sha256=row["resolved_config_sha256"], error=row["error"])
        result.validate(); output.append(result)
    return output
