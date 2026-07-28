from __future__ import annotations

import csv
import json
from pathlib import Path

from experiments.metrics import classification_metrics, operational_metrics
from experiments.statistics import bootstrap_ci, stratified_bootstrap_ci


def load_inputs(dataset_path: Path, run_path: Path) -> tuple[list[dict], list[dict]]:
    with dataset_path.open(encoding="utf-8", newline="") as handle:
        dataset = [r for r in csv.DictReader(handle) if r["split"] == "evaluation"]
    results = [json.loads(line) for line in run_path.read_text(encoding="utf-8").splitlines() if line]
    ids = [r["transaction_id"] for r in results]; expected = {r["transaction_id"] for r in dataset}
    if len(ids) != len(set(ids)) or set(ids) != expected:
        raise ValueError("results must contain exactly one prediction for each evaluation row")
    return dataset, results


def build_summary(dataset: list[dict], results: list[dict]) -> dict:
    by_id = {r["transaction_id"]: r for r in results}
    labels = [int(r["risk_label"]) for r in dataset]
    predictions = [int(by_id[r["transaction_id"]]["prediction"]) for r in dataset]
    scores = [float(by_id[r["transaction_id"]]["confidence"]) for r in dataset]
    metrics = classification_metrics(labels, predictions, scores)
    per_category = {}
    for category in sorted({r["risk_category"] for r in dataset}):
        subset = [r for r in dataset if r["risk_category"] == category]
        per_category[category] = classification_metrics(
            [int(r["risk_label"]) for r in subset],
            [int(by_id[r["transaction_id"]]["prediction"]) for r in subset],
            [float(by_id[r["transaction_id"]]["confidence"]) for r in subset],
        )
    correctness = [float(y == p) for y, p in zip(labels, predictions)]
    operational = operational_metrics(results)
    latency = [float(r["latency_ms"]) for r in results if not r.get("error")]
    cost = [float(r["cost_usd"]) for r in results if not r.get("error")]
    return {"method": results[0]["method"], "classification": metrics,
            "operational": operational, "per_category": per_category,
            "uncertainty": {"accuracy_bootstrap_95_ci": bootstrap_ci(correctness),
                            "accuracy_stratified_bootstrap_95_ci": stratified_bootstrap_ci(
                                correctness, [r["risk_category"] for r in dataset]),
                            "latency_mean_bootstrap_95_ci": bootstrap_ci(latency),
                            "cost_mean_bootstrap_95_ci": bootstrap_ci(cost)},
            "executed_methods": [results[0]["method"]],
            "not_run": ["single_llm", "full_multi_agent", "no_challenger", "no_verifier", "no_rag", "no_defender", "one_debate_round", "two_debate_rounds"]}


def failure_rows(dataset: list[dict], results: list[dict]) -> list[dict]:
    data = {r["transaction_id"]: r for r in dataset}; failures = []
    for result in results:
        truth = int(data[result["transaction_id"]]["risk_label"]); prediction = int(result["prediction"])
        kind = "false_positive" if truth == 0 and prediction == 1 else "false_negative" if truth == 1 and prediction == 0 else "high_confidence_incorrect" if truth != prediction and float(result["confidence"]) >= .8 else ""
        if kind or result.get("error") or result.get("groundedness") == 0 or result.get("citation_correctness") == 0:
            failures.append({"transaction_id": result["transaction_id"], "failure_type": kind or "quality_or_runtime", "risk_category": data[result["transaction_id"]]["risk_category"], "amount_usd": data[result["transaction_id"]]["amount_usd"], "prediction": prediction, "label": truth, "confidence": result["confidence"], "error": result.get("error", "")})
    return failures


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        if not rows: handle.write(""); return
        writer = csv.DictWriter(handle, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)


def write_svg(path: Path, metrics: dict) -> None:
    names = ["precision", "recall", "specificity", "f1", "balanced_accuracy"]
    bars = []
    for index, name in enumerate(names):
        value = metrics.get(name) or 0; x = 55 + index * 105; height = value * 180
        bars.append(f'<rect x="{x}" y="{220-height:.1f}" width="62" height="{height:.1f}" fill="#2563eb"/><text x="{x+31}" y="242" text-anchor="middle" font-size="11">{name}</text><text x="{x+31}" y="{210-height:.1f}" text-anchor="middle" font-size="11">{value:.3f}</text>')
    svg = '<svg xmlns="http://www.w3.org/2000/svg" width="620" height="270" role="img" aria-label="Rule baseline metrics"><rect width="100%" height="100%" fill="white"/><text x="20" y="24" font-size="16">Executed rule baseline — synthetic evaluation split</text><line x1="35" y1="220" x2="600" y2="220" stroke="black"/>' + "".join(bars) + "</svg>"
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text(svg, encoding="utf-8")


def write_confusion_svg(path: Path, matrix: dict) -> None:
    cells = [("TN", matrix["tn"], 70, 70), ("FP", matrix["fp"], 210, 70),
             ("FN", matrix["fn"], 70, 170), ("TP", matrix["tp"], 210, 170)]
    content = "".join(f'<rect x="{x}" y="{y}" width="120" height="80" fill="#dbeafe" stroke="#1e3a8a"/><text x="{x+60}" y="{y+38}" text-anchor="middle">{name}: {value}</text>' for name, value, x, y in cells)
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="400" height="290"><rect width="100%" height="100%" fill="white"/><text x="20" y="25">Rule baseline confusion matrix</text>{content}</svg>'
    path.write_text(svg, encoding="utf-8")


def write_reliability_svg(path: Path, curve: list[dict]) -> None:
    points = " ".join(f"{50 + row['mean_confidence'] * 240:.1f},{250 - row['positive_rate'] * 200:.1f}" for row in curve)
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="340" height="290"><rect width="100%" height="100%" fill="white"/><text x="15" y="22">Reliability diagram</text><line x1="50" y1="250" x2="290" y2="50" stroke="#999"/><polyline points="{points}" fill="none" stroke="#dc2626" stroke-width="3"/></svg>'
    path.write_text(svg, encoding="utf-8")
