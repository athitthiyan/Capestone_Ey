import csv
import json
from pathlib import Path

import pytest

from experiments.annotation.agreement import cohens_kappa, fleiss_kappa, percentage_agreement
from experiments.evaluators.citation_correctness import score_citations
from experiments.evaluators.groundedness import score_groundedness
from experiments.metrics import classification_metrics
from experiments.runners import load_config
from experiments.runners.candidate import load_candidate
from experiments.runners.multi_agent import run as run_multi_agent
from experiments.runners.single_llm import run as run_single_llm
from experiments.schema import ExperimentResult
from experiments.statistics import bootstrap_ci, mcnemar_test, stratified_bootstrap_ci
from scripts.generate_benchmark_dataset import generate_rows


def test_benchmark_is_deterministic_balanced_and_leakage_fields_are_explicit():
    first, second = generate_rows(), generate_rows()
    assert first == second
    assert len(first) == 600
    assert sum(int(row["risk_label"]) for row in first) == 300
    assert {row["split"] for row in first} == {"development", "evaluation"}
    assert {"risk_label", "risk_category", "difficulty", "split"} <= set(first[0])


def test_metric_edge_cases_and_specificity():
    all_positive = classification_metrics([1, 1, 0, 0], [1, 1, 1, 1], [.9] * 4)
    assert all_positive["specificity"] == 0
    assert all_positive["balanced_accuracy"] == .5
    assert all_positive["mcc"] is None
    all_negative = classification_metrics([1, 0], [0, 0], [.1, .1])
    assert all_negative["recall"] == 0
    single_class = classification_metrics([1, 1], [1, 0], [.8, .2])
    assert single_class["roc_auc"] is None
    assert single_class["pr_auc"] is not None


def test_auc_perfect_ordering():
    result = classification_metrics([0, 1, 0, 1], [0, 1, 0, 1], [.1, .8, .2, .9])
    assert result["roc_auc"] == 1
    assert result["pr_auc"] == 1


def test_bootstrap_reproducibility_and_mcnemar_validation():
    assert bootstrap_ci([0, 1, 1], samples=100) == bootstrap_ci([0, 1, 1], samples=100)
    assert mcnemar_test([0, 1], [0, 0], [1, 1])["p_value"] == 1
    with pytest.raises(ValueError): mcnemar_test([], [], [])
    assert stratified_bootstrap_ci([0, 1, 1, 0], ["a", "a", "b", "b"], samples=100) == stratified_bootstrap_ci([0, 1, 1, 0], ["a", "a", "b", "b"], samples=100)


def test_annotation_agreement_metrics():
    assert percentage_agreement([0, 1], [0, 1]) == 1
    assert cohens_kappa([0, 1], [0, 1]) == 1
    assert cohens_kappa([0, 1, 2], [0, 1, 2], weights="quadratic") == 1
    assert fleiss_kappa({"a": [0, 0, 0], "b": [1, 1, 1]}) == 1


def test_groundedness_and_citation_rubrics_hide_classification_label():
    claims = [{"claim_id": "c1", "text": "invoice is missing", "citations": ["e1"]}]
    evidence = {"e1": "The invoice is missing from supplied documents."}
    assert score_groundedness(claims, evidence).score == 1
    assert score_citations(claims, evidence).score == 1
    assert "risk_label" not in score_groundedness.__annotations__


def _candidate_row(transaction_id="T1", prediction="1", **overrides):
    row = {"transaction_id": transaction_id, "method": "fixture", "prediction": prediction,
           "confidence": "0.8", "explanation": "x", "evidence_ids": "[]", "citations": "[]",
           "groundedness": "", "citation_correctness": "", "input_tokens": "1", "output_tokens": "1",
           "cost_usd": "0.01", "latency_ms": "2", "model": "mock", "provider": "mock",
           "prompt_version": "v1", "run_id": "r1", "experiment_timestamp": "2026-07-28T00:00:00Z",
           "random_seed": "20260728", "resolved_config_sha256": "abc", "error": ""}
    row.update(overrides); return row


def _write_csv(path: Path, rows: list[dict]):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)


@pytest.mark.parametrize("change", [
    lambda rows: rows + [rows[0].copy()],
    lambda rows: [{**rows[0], "transaction_id": "UNKNOWN"}],
    lambda rows: [{**rows[0], "prediction": "maybe"}],
    lambda rows: [{**rows[0], "groundedness": "1.5"}],
    lambda rows: [{**rows[0], "citation_correctness": "-1"}],
    lambda rows: [{**rows[0], "cost_usd": "-1"}],
    lambda rows: [{**rows[0], "latency_ms": "-1"}],
])
def test_candidate_validation_rejects_invalid_rows(tmp_path, change):
    path = tmp_path / "predictions.csv"; _write_csv(path, change([_candidate_row()]))
    with pytest.raises(ValueError): load_candidate(path, {"T1"})


def test_candidate_rejects_empty_and_missing_columns(tmp_path):
    empty = tmp_path / "empty.csv"; empty.write_text("", encoding="utf-8")
    with pytest.raises(ValueError): load_candidate(empty, {"T1"})
    short = tmp_path / "short.csv"; short.write_text("transaction_id,prediction\nT1,1\n", encoding="utf-8")
    with pytest.raises(ValueError): load_candidate(short, {"T1"})


def test_all_ablation_configs_validate():
    paths = list(Path("experiments/configs").glob("*.yaml"))
    assert len(paths) >= 6
    configs = [load_config(path) for path in paths]
    assert any(not c.verifier_enabled for c in configs)
    assert any(not c.challenger_enabled for c in configs)
    assert any(not c.retrieval_enabled for c in configs)


def test_single_llm_runner_with_mock_provider_hides_labels_and_serializes():
    seen = {}
    def mock(row):
        seen.update(row)
        return {"prediction": 1, "confidence": .8, "explanation": "supported", "citations": ["e1"]}
    row = generate_rows(500)[0]
    result = run_single_llm([row], mock, provider="mock", model="mock-v1")[0]
    assert result.prediction == 1 and result.provider == "mock"
    assert not {"risk_label", "risk_category", "difficulty", "split"} & set(seen)
    assert ExperimentResult(**result.to_dict()).to_dict() == result.to_dict()


def test_multi_agent_runner_with_mocked_orchestrator_honors_ablation():
    config = load_config(Path("experiments/configs/no_verifier.yaml"))
    def mock(row, received):
        assert received.verifier_enabled is False
        return {"prediction": 0, "confidence": .7, "explanation": "fixture"}
    result = run_multi_agent([generate_rows(500)[0]], mock, config)[0]
    assert result.method == "no_verifier" and result.error == ""


def test_generated_report_matches_summary_when_present():
    path = Path("experiments/results/summary.json")
    if not path.exists(): pytest.skip("generate reports first")
    summary = json.loads(path.read_text(encoding="utf-8"))
    report = Path("experiments/results/RESEARCH_REPORT.md").read_text(encoding="utf-8")
    assert f"{summary['classification']['accuracy']:.4f}" in report
    assert summary["executed_methods"] == ["rule_baseline"]
