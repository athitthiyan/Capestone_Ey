"""Reproducible offline evaluation for GL Guardian.

The bundled ledger is synthetic. Its ``risk_hint`` column is used only as an
evaluation label and is never exposed to a method. Candidate outputs can be
supplied as CSV files, which keeps live LLM execution separate from scoring.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import time
from collections import Counter
from pathlib import Path
from typing import Any, Callable

POSITIVE = {"1", "true", "yes", "y", "positive", "flagged", "fraud", "suspicious"}


def _bool(value: Any) -> bool:
    return str(value).strip().lower() in POSITIVE


def label_from_risk_hint(row: dict[str, str]) -> bool:
    """Synthetic anomaly proxy; do not interpret as confirmed fraud."""
    return row.get("risk_hint", "").strip().lower() not in {"", "normal"}


def split_for(transaction_id: str, seed: int = 20260728) -> str:
    digest = hashlib.sha256(f"{seed}:{transaction_id}".encode()).digest()
    return "evaluation" if int.from_bytes(digest[:8], "big") % 100 < 20 else "development"


def rule_baseline(row: dict[str, str]) -> bool:
    """Rules use observable ledger fields only (never ``risk_hint``)."""
    amount = float(row.get("amount_usd") or 0)
    document_status = row.get("document_status", "").strip().lower()
    posted_by = row.get("posted_by", "").strip().lower()
    approved_by = row.get("approved_by", "").strip().lower()
    return any(
        (
            amount >= 50_000,
            row.get("related_party_flag", "").strip().upper() == "Y",
            bool(posted_by) and posted_by == approved_by,
            not row.get("po_number", "").strip(),
            row.get("payment_method", "").strip().lower() == "manual journal",
            document_status not in {"", "complete"},
        )
    )


def classification_metrics(labels: list[bool], predictions: list[bool]) -> dict[str, Any]:
    tp = sum(y and p for y, p in zip(labels, predictions))
    fp = sum(not y and p for y, p in zip(labels, predictions))
    fn = sum(y and not p for y, p in zip(labels, predictions))
    tn = sum(not y and not p for y, p in zip(labels, predictions))
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return {
        "n": len(labels),
        "accuracy": round((tp + tn) / len(labels), 4) if labels else None,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "specificity": round(tn / (tn + fp), 4) if tn + fp else 0.0,
        "f1": round(2 * precision * recall / (precision + recall), 4)
        if precision + recall
        else 0.0,
        "confusion_matrix": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
    }


def _mean(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 4) if values else None


def evaluate_method(
    name: str,
    rows: list[dict[str, str]],
    predict: Callable[[dict[str, str]], bool],
    metadata: dict[str, dict[str, str]] | None = None,
) -> dict[str, Any]:
    labels, predictions, latencies = [], [], []
    failures: list[dict[str, str]] = []
    for row in rows:
        start = time.perf_counter_ns()
        prediction = predict(row)
        latencies.append((time.perf_counter_ns() - start) / 1_000_000)
        label = label_from_risk_hint(row)
        labels.append(label)
        predictions.append(prediction)
        if label != prediction and len(failures) < 10:
            failures.append(
                {
                    "transaction_id": row["transaction_id"],
                    "label": str(label).lower(),
                    "prediction": str(prediction).lower(),
                    "risk_hint": row.get("risk_hint", ""),
                }
            )
    result = {"method": name, **classification_metrics(labels, predictions)}
    result["average_latency_ms"] = round(sum(latencies) / len(latencies), 6)
    result["failure_cases"] = failures
    result["groundedness"] = None
    result["citation_correctness"] = None
    result["cost_usd_per_investigation"] = 0.0 if name == "Rule baseline" else None
    if metadata:
        grounded = [float(v["groundedness"]) for v in metadata.values() if v.get("groundedness")]
        citations = [
            float(v["citation_correctness"])
            for v in metadata.values()
            if v.get("citation_correctness")
        ]
        costs = [float(v["cost_usd"]) for v in metadata.values() if v.get("cost_usd")]
        measured_latency = [
            float(v["latency_ms"]) for v in metadata.values() if v.get("latency_ms")
        ]
        result.update(
            groundedness=_mean(grounded),
            citation_correctness=_mean(citations),
            cost_usd_per_investigation=_mean(costs),
            average_latency_ms=_mean(measured_latency) or result["average_latency_ms"],
        )
    return result


def load_predictions(path: Path) -> dict[str, dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    required = {"transaction_id", "prediction"}
    if not rows or not required <= set(rows[0]):
        raise ValueError(f"{path} must contain columns: {sorted(required)}")
    return {row["transaction_id"]: row for row in rows}


def run(dataset: Path, prediction_files: list[Path]) -> dict[str, Any]:
    with dataset.open(encoding="utf-8-sig", newline="") as handle:
        all_rows = list(csv.DictReader(handle))
    evaluation_rows = [r for r in all_rows if split_for(r["transaction_id"]) == "evaluation"]
    result: dict[str, Any] = {
        "protocol_version": 1,
        "dataset": {
            "path": dataset.as_posix(),
            "type": "synthetic ledger; risk_hint is an anomaly proxy, not confirmed fraud",
            "total_rows": len(all_rows),
            "development_rows": len(all_rows) - len(evaluation_rows),
            "evaluation_rows": len(evaluation_rows),
            "evaluation_positive": sum(label_from_risk_hint(r) for r in evaluation_rows),
            "split": "deterministic SHA-256 80/20 split; seed 20260728",
            "label_distribution": dict(Counter(r.get("risk_hint", "") for r in evaluation_rows)),
        },
        "methods": [evaluate_method("Rule baseline", evaluation_rows, rule_baseline)],
        "limitations": [
            "Synthetic proxy labels do not establish real-world fraud-detection performance.",
            "No model is trained; the development partition is reserved for "
            "rule/prompt development.",
            "Groundedness and citation correctness require independently scored candidate outputs.",
        ],
    }
    ids = {r["transaction_id"] for r in evaluation_rows}
    for path in prediction_files:
        predictions = load_predictions(path)
        missing = sorted(ids - predictions.keys())
        if missing:
            raise ValueError(f"{path} is missing {len(missing)} evaluation predictions")
        result["methods"].append(
            evaluate_method(
                path.stem,
                evaluation_rows,
                lambda row, p=predictions: _bool(p[row["transaction_id"]]["prediction"]),
                predictions,
            )
        )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=Path("sample_data/sample_gl_1000.csv"))
    parser.add_argument("--predictions", type=Path, action="append", default=[])
    parser.add_argument("--output", type=Path, default=Path("experiments/results/latest.json"))
    args = parser.parse_args()
    result = run(args.dataset, args.predictions)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
