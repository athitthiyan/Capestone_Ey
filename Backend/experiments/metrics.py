from __future__ import annotations

import math
from statistics import mean, median


def _safe(n: float, d: float) -> float | None:
    return n / d if d else None


def _rank_auc(labels: list[int], scores: list[float]) -> float | None:
    positives = [s for y, s in zip(labels, scores) if y == 1]
    negatives = [s for y, s in zip(labels, scores) if y == 0]
    if not positives or not negatives:
        return None
    wins = sum((p > n) + 0.5 * (p == n) for p in positives for n in negatives)
    return wins / (len(positives) * len(negatives))


def _pr_auc(labels: list[int], scores: list[float]) -> float | None:
    if not any(labels):
        return None
    ranked = sorted(zip(scores, labels), reverse=True)
    tp = fp = 0
    previous_recall = 0.0
    area = 0.0
    total_positive = sum(labels)
    for _, label in ranked:
        tp += label
        fp += 1 - label
        recall = tp / total_positive
        precision = tp / (tp + fp)
        area += (recall - previous_recall) * precision
        previous_recall = recall
    return area


def classification_metrics(labels: list[int], predictions: list[int], scores: list[float] | None = None) -> dict:
    if not labels or len(labels) != len(predictions):
        raise ValueError("labels and predictions must be non-empty and equally sized")
    tp = sum(y == 1 and p == 1 for y, p in zip(labels, predictions))
    tn = sum(y == 0 and p == 0 for y, p in zip(labels, predictions))
    fp = sum(y == 0 and p == 1 for y, p in zip(labels, predictions))
    fn = sum(y == 1 and p == 0 for y, p in zip(labels, predictions))
    precision, recall = _safe(tp, tp + fp), _safe(tp, tp + fn)
    specificity = _safe(tn, tn + fp)
    f1 = _safe(2 * (precision or 0) * (recall or 0), (precision or 0) + (recall or 0))
    denominator = math.sqrt((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn))
    result = {
        "n": len(labels), "accuracy": (tp + tn) / len(labels), "precision": precision,
        "recall": recall, "specificity": specificity, "f1": f1,
        "balanced_accuracy": mean([recall, specificity]) if recall is not None and specificity is not None else None,
        "mcc": (tp * tn - fp * fn) / denominator if denominator else None,
        "false_positive_rate": _safe(fp, fp + tn), "false_negative_rate": _safe(fn, fn + tp),
        "negative_predictive_value": _safe(tn, tn + fn), "positive_predictive_value": precision,
        "confusion_matrix": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
    }
    if scores is not None:
        result.update(roc_auc=_rank_auc(labels, scores), pr_auc=_pr_auc(labels, scores))
        result["brier_score"] = mean((s - y) ** 2 for y, s in zip(labels, scores))
        result["expected_calibration_error"] = expected_calibration_error(labels, scores)
        result["reliability_curve"] = reliability_curve(labels, scores)
    return result


def reliability_curve(labels: list[int], scores: list[float], bins: int = 10) -> list[dict]:
    output = []
    for index in range(bins):
        low, high = index / bins, (index + 1) / bins
        values = [(y, s) for y, s in zip(labels, scores) if low <= s <= high and (index == bins - 1 or s < high)]
        if values:
            output.append({"low": low, "high": high, "count": len(values), "mean_confidence": mean(s for _, s in values), "positive_rate": mean(y for y, _ in values)})
    return output


def expected_calibration_error(labels: list[int], scores: list[float], bins: int = 10) -> float:
    return sum(row["count"] / len(labels) * abs(row["mean_confidence"] - row["positive_rate"]) for row in reliability_curve(labels, scores, bins))


def operational_metrics(rows: list[dict]) -> dict:
    def percentile(values: list[float], q: float) -> float | None:
        if not values:
            return None
        ordered = sorted(values); position = (len(ordered) - 1) * q; lo = int(position); hi = min(lo + 1, len(ordered) - 1)
        return ordered[lo] + (ordered[hi] - ordered[lo]) * (position - lo)
    latencies = [float(r["latency_ms"]) for r in rows if not r.get("error")]
    costs = [float(r["cost_usd"]) for r in rows if not r.get("error")]
    grounded = [float(r["groundedness"]) for r in rows if r.get("groundedness") is not None]
    citations = [float(r["citation_correctness"]) for r in rows if r.get("citation_correctness") is not None]
    with_evidence = [bool(r.get("evidence_ids")) for r in rows]
    unsupported = [float(r["groundedness"] == 0) for r in rows if r.get("groundedness") is not None]
    return {"mean_latency_ms": mean(latencies) if latencies else None, "median_latency_ms": median(latencies) if latencies else None,
            "p90_latency_ms": percentile(latencies, .9), "p95_latency_ms": percentile(latencies, .95), "p99_latency_ms": percentile(latencies, .99),
            "mean_cost_usd": mean(costs) if costs else None, "median_cost_usd": median(costs) if costs else None,
            "mean_groundedness": mean(grounded) if grounded else None, "median_groundedness": median(grounded) if grounded else None,
            "mean_citation_correctness": mean(citations) if citations else None,
            "evidence_coverage": mean(with_evidence) if with_evidence else None,
            "unsupported_claim_rate": mean(unsupported) if unsupported else None,
            "confidence_summary": {"mean": mean(float(r["confidence"]) for r in rows),
                                   "median": median(float(r["confidence"]) for r in rows)} if rows else None,
            "mean_input_tokens": mean(float(r.get("input_tokens", 0)) for r in rows), "mean_output_tokens": mean(float(r.get("output_tokens", 0)) for r in rows),
            "failure_rate": sum(bool(r.get("error")) for r in rows) / len(rows) if rows else None,
            "timeout_rate": sum("timeout" in str(r.get("error", "")).lower() for r in rows) / len(rows) if rows else None}
