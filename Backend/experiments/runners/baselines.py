"""Non-LLM reference conditions.

Two kinds, and the distinction matters when reading the results table:

**Deterministic screens** (``rule_baseline``) use no labels at all. On the real benchmark
this is the audit office's own pre-audit screen, replayed exactly. It is the incumbent
the system has to beat, so it is the honest comparator.

**Supervised references** (``logistic_reference``, ``tree_reference``) are *fitted on the
development split* and therefore see labels the LLM conditions never do. They are not
competitors; they are a ceiling that says how much signal the recorded fields contain at
all. Reporting them prevents the paper from claiming credit for reasoning when a linear
model on six numbers would have done as well.

Everything here is pure standard library, so the reference numbers reproduce exactly on
any checkout without a pinned scientific stack.
"""

from __future__ import annotations

import math
import time
from collections.abc import Sequence
from dataclasses import dataclass
from uuid import uuid4

from experiments.benchmarks import BenchmarkCase
from experiments.schema import ExperimentResult

# Numeric fields usable as supervised inputs, per benchmark. Label-derived columns are
# already excluded upstream by the dataset builder.
FEATURE_SETS = {
    "uci_audit_v1": (
        "sector_score", "para_a_discrepancy_cr", "para_b_discrepancy_cr",
        "total_discrepancy_cr", "discrepancy_count", "money_value_cr",
        "district_loss_score", "history_score", "prior_screen_flag",
        "prior_screen_score",
    ),
    "gl_synthetic_v1": ("amount_usd",),
}


# ---------------------------------------------------------------------------
# Deterministic screens
# ---------------------------------------------------------------------------

def screen_uci_audit(view: dict[str, str]) -> tuple[int, float, list[str], list[str]]:
    """Replay the audit office's pre-audit screen, which is recorded in the data.

    No threshold is invented here: ``prior_screen_flag`` is the screen's own decision.
    Confidence is derived from the screen score so the baseline is not forced to a
    degenerate two-point distribution.
    """
    flagged = int(float(view.get("prior_screen_flag", 0)))
    score = float(view.get("prior_screen_score", 0) or 0)
    confidence = max(0.05, min(0.95, score / 6.0)) if flagged else max(
        0.02, min(0.45, score / 12.0))
    reasons = ["pre-audit screen flagged the case"] if flagged else [
        "pre-audit screen cleared the case"]
    citations = [f"{view.get('transaction_id', '')}:prior-screen"] if view.get(
        "transaction_id") else []
    return flagged, confidence, reasons, citations


def screen_gl_synthetic(view: dict[str, str]) -> tuple[int, float, list[str], list[str]]:
    reasons: list[str] = []
    if float(view.get("amount_usd", 0) or 0) >= 50_000:
        reasons.append("materiality")
    if view.get("related_party_flag") == "Y":
        reasons.append("related_party")
    if view.get("posted_by") and view.get("posted_by") == view.get("approved_by"):
        reasons.append("segregation_of_duties")
    if not view.get("po_number") or view.get("document_status") != "complete":
        reasons.append("document_gap")
    if view.get("duplicate_of"):
        reasons.append("duplicate")
    prediction = int(bool(reasons))
    confidence = min(0.95, 0.55 + 0.1 * len(reasons)) if prediction else 0.25
    return prediction, confidence, reasons or ["no rule fired"], []


SCREENS = {"uci_audit_v1": screen_uci_audit, "gl_synthetic_v1": screen_gl_synthetic}


def run_rule_baseline(cases: Sequence[BenchmarkCase], benchmark_name: str,
                      method: str = "rule_baseline") -> list[ExperimentResult]:
    if benchmark_name not in SCREENS:
        raise KeyError(f"no deterministic screen defined for {benchmark_name!r}")
    screen = SCREENS[benchmark_name]
    run_id = f"rule-{uuid4().hex[:12]}"
    results = []
    for case in cases:
        started = time.perf_counter_ns()
        view = case.model_view() | {"transaction_id": case.case_id}
        prediction, confidence, reasons, citations = screen(view)
        result = ExperimentResult(
            transaction_id=case.case_id, method=method, prediction=prediction,
            confidence=confidence, explanation="; ".join(reasons),
            evidence_ids=list(case.evidence_ids),
            citations=[c for c in citations if c in set(case.evidence_ids)],
            latency_ms=(time.perf_counter_ns() - started) / 1_000_000,
            run_id=run_id, prompt_version="screen-v1", model="deterministic",
            provider="none")
        result.validate()
        results.append(result)
    return results


# ---------------------------------------------------------------------------
# Supervised references
# ---------------------------------------------------------------------------

def _features(case: BenchmarkCase, columns: Sequence[str]) -> list[float]:
    view = case.model_view()
    output = []
    for column in columns:
        raw = view.get(column, 0)
        try:
            output.append(float(raw))
        except (TypeError, ValueError):
            output.append(0.0)
    return output


@dataclass
class LogisticReference:
    columns: tuple[str, ...]
    weights: list[float]
    bias: float
    means: list[float]
    scales: list[float]

    def probability(self, features: Sequence[float]) -> float:
        z = self.bias + sum(
            w * (x - m) / s
            for w, x, m, s in zip(self.weights, features, self.means, self.scales))
        return 1.0 / (1.0 + math.exp(-max(-60.0, min(60.0, z))))


def fit_logistic(development: Sequence[BenchmarkCase], columns: Sequence[str], *,
                 epochs: int = 4000, learning_rate: float = 0.15,
                 l2: float = 1e-4) -> LogisticReference:
    """Full-batch gradient descent. No RNG, so the fit is bit-reproducible."""
    matrix = [_features(case, columns) for case in development]
    labels = [case.label for case in development]
    if not matrix:
        raise ValueError("development split is empty")
    width = len(columns)
    means = [sum(row[j] for row in matrix) / len(matrix) for j in range(width)]
    scales = []
    for j in range(width):
        variance = sum((row[j] - means[j]) ** 2 for row in matrix) / len(matrix)
        scales.append(math.sqrt(variance) or 1.0)
    standardized = [[(row[j] - means[j]) / scales[j] for j in range(width)] for row in matrix]

    weights = [0.0] * width
    bias = 0.0
    for _ in range(epochs):
        gradient_w = [0.0] * width
        gradient_b = 0.0
        for row, label in zip(standardized, labels):
            z = bias + sum(w * x for w, x in zip(weights, row))
            error = 1.0 / (1.0 + math.exp(-max(-60.0, min(60.0, z)))) - label
            gradient_b += error
            for j in range(width):
                gradient_w[j] += error * row[j]
        n = len(standardized)
        bias -= learning_rate * gradient_b / n
        for j in range(width):
            weights[j] -= learning_rate * (gradient_w[j] / n + l2 * weights[j])
    return LogisticReference(tuple(columns), weights, bias, means, scales)


@dataclass
class TreeNode:
    column: int | None = None
    threshold: float = 0.0
    left: "TreeNode | None" = None
    right: "TreeNode | None" = None
    probability: float = 0.0

    def predict(self, features: Sequence[float]) -> float:
        if self.column is None:
            return self.probability
        branch = self.left if features[self.column] <= self.threshold else self.right
        return branch.predict(features) if branch else self.probability


def _gini(labels: Sequence[int]) -> float:
    if not labels:
        return 0.0
    p = sum(labels) / len(labels)
    return 2 * p * (1 - p)


def fit_tree(development: Sequence[BenchmarkCase], columns: Sequence[str], *,
             max_depth: int = 3, min_samples_leaf: int = 10) -> TreeNode:
    matrix = [_features(case, columns) for case in development]
    labels = [case.label for case in development]

    def build(rows: list[list[float]], targets: list[int], depth: int) -> TreeNode:
        probability = sum(targets) / len(targets) if targets else 0.0
        node = TreeNode(probability=probability)
        if depth >= max_depth or len(targets) < 2 * min_samples_leaf or _gini(targets) == 0:
            return node
        best = (0.0, None, 0.0)
        parent_impurity = _gini(targets)
        for column in range(len(columns)):
            values = sorted({row[column] for row in rows})
            for first, second in zip(values, values[1:]):
                threshold = (first + second) / 2
                left = [t for row, t in zip(rows, targets) if row[column] <= threshold]
                right = [t for row, t in zip(rows, targets) if row[column] > threshold]
                if len(left) < min_samples_leaf or len(right) < min_samples_leaf:
                    continue
                gain = parent_impurity - (
                    len(left) / len(targets) * _gini(left)
                    + len(right) / len(targets) * _gini(right))
                if gain > best[0]:
                    best = (gain, column, threshold)
        gain, column, threshold = best
        if column is None or gain <= 1e-9:
            return node
        left_rows = [(r, t) for r, t in zip(rows, targets) if r[column] <= threshold]
        right_rows = [(r, t) for r, t in zip(rows, targets) if r[column] > threshold]
        node.column, node.threshold = column, threshold
        node.left = build([r for r, _ in left_rows], [t for _, t in left_rows], depth + 1)
        node.right = build([r for r, _ in right_rows], [t for _, t in right_rows], depth + 1)
        return node

    return build(matrix, labels, 0)


def run_supervised_reference(development: Sequence[BenchmarkCase],
                             evaluation: Sequence[BenchmarkCase],
                             benchmark_name: str, kind: str = "logistic",
                             threshold: float = 0.5) -> list[ExperimentResult]:
    columns = FEATURE_SETS.get(benchmark_name)
    if not columns:
        raise KeyError(f"no supervised feature set defined for {benchmark_name!r}")
    method = f"{kind}_reference"
    run_id = f"{kind}-{uuid4().hex[:12]}"

    if kind == "logistic":
        model = fit_logistic(development, columns)
        scorer = model.probability
        describe = "logistic regression fitted on the development split"
    elif kind == "tree":
        tree = fit_tree(development, columns)
        scorer = tree.predict
        describe = "depth-3 decision tree fitted on the development split"
    else:
        raise ValueError(f"unknown supervised reference {kind!r}")

    results = []
    for case in evaluation:
        started = time.perf_counter_ns()
        probability = scorer(_features(case, columns))
        result = ExperimentResult(
            transaction_id=case.case_id, method=method,
            prediction=int(probability >= threshold),
            confidence=round(min(1.0, max(0.0, probability)), 6),
            explanation=f"{describe}; p(risk)={probability:.4f}",
            evidence_ids=list(case.evidence_ids), citations=[],
            latency_ms=(time.perf_counter_ns() - started) / 1_000_000,
            run_id=run_id, prompt_version=f"{kind}-ref-v1",
            model=f"{kind}-reference", provider="none")
        result.validate()
        results.append(result)
    return results
