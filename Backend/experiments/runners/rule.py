from __future__ import annotations

import time
from uuid import uuid4

from experiments.schema import ExperimentResult


def predict(row: dict[str, str]) -> tuple[int, float, list[str]]:
    reasons = []
    if float(row["amount_usd"]) >= 50_000: reasons.append("materiality")
    if row["related_party_flag"] == "Y": reasons.append("related_party")
    if row["posted_by"] == row["approved_by"]: reasons.append("segregation_of_duties")
    if not row["po_number"] or row["document_status"] != "complete": reasons.append("document_gap")
    if row["duplicate_of"]: reasons.append("duplicate")
    prediction = int(bool(reasons)); confidence = min(0.99, 0.55 + 0.1 * len(reasons)) if prediction else 0.25
    return prediction, confidence, reasons


def run(rows: list[dict[str, str]], method: str = "rule_baseline") -> list[ExperimentResult]:
    run_id = f"rule-{uuid4().hex[:12]}"; output = []
    for row in rows:
        started = time.perf_counter_ns(); prediction, confidence, reasons = predict(row)
        output.append(ExperimentResult(transaction_id=row["transaction_id"], method=method,
            prediction=prediction, confidence=confidence, explanation="; ".join(reasons) or "no rule fired",
            evidence_ids=row["evidence_ids"].split(";"), citations=row["evidence_ids"].split(";"),
            latency_ms=(time.perf_counter_ns() - started) / 1_000_000, run_id=run_id,
            prompt_version="rules-v1"))
    return output
