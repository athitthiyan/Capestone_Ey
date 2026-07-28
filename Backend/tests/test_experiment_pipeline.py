"""Tests for the experiment pipeline.

The point of these tests is not coverage for its own sake. Each one pins down a way the
reported numbers could be quietly wrong: a label reaching a predictor, a partial run
being scored as if complete, a metric with a hand-rolled denominator, a cost silently
reported as zero. If one of these fails, a number in RESULTS.md is not trustworthy.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from experiments import benchmarks
from experiments.benchmarks import LABEL_FIELDS, BenchmarkCase
from experiments.evaluators.judge import JUDGE_SYSTEM, Judgment, _parse_scores, reconcile
from experiments.harness import (
    CostLimitExceeded,
    estimate_calls,
    project_cost,
    resolved_config_sha256,
    run_method,
)
from experiments.llm import (
    PRICE_TABLE,
    Completion,
    LLMConfig,
    Provider,
    ProviderError,
    ResponseCache,
    _cost,
    parse_verdict,
)
from experiments.metrics import classification_metrics, operational_metrics
from experiments.runners.base import ExperimentConfig, load_config
from experiments.runners.baselines import FEATURE_SETS, fit_logistic, run_rule_baseline
from experiments.runners.candidate import load_candidate
from experiments.runners.llm_agents import prompt_version, render_case
from experiments.schema import ExperimentResult
from experiments.statistics import (
    bootstrap_ci,
    bootstrap_metric_ci,
    holm_bonferroni,
    mcnemar_test,
)

ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "experiments" / "configs"

CANDIDATE_COLUMNS = [
    "transaction_id", "method", "prediction", "confidence", "explanation", "evidence_ids",
    "citations", "groundedness", "citation_correctness", "input_tokens", "output_tokens",
    "cost_usd", "latency_ms", "model", "provider", "prompt_version", "run_id",
    "experiment_timestamp", "random_seed", "resolved_config_sha256", "error",
]


def _candidate_row(transaction_id: str, **overrides) -> dict:
    row = {
        "transaction_id": transaction_id, "method": "single_llm", "prediction": "1",
        "confidence": "0.8", "explanation": "because", "evidence_ids": '["e1"]',
        "citations": '["e1"]', "groundedness": "", "citation_correctness": "",
        "input_tokens": "10", "output_tokens": "5", "cost_usd": "0.001",
        "latency_ms": "12.5", "model": "m", "provider": "p", "prompt_version": "v",
        "run_id": "r", "experiment_timestamp": "2026-07-28T00:00:00+00:00",
        "random_seed": "20260728", "resolved_config_sha256": "abc", "error": "",
    }
    row.update(overrides)
    return row


def _write_candidate(path: Path, rows: list[dict], columns=None) -> Path:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns or CANDIDATE_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return path


def _case(case_id="C-1", label=1, **fields) -> BenchmarkCase:
    base = {"transaction_id": case_id, "risk_label": str(label), "amount_usd": "100",
            "split": "evaluation", "risk_category": "normal", "difficulty": "standard"}
    base.update({k: str(v) for k, v in fields.items()})
    return BenchmarkCase(case_id=case_id, label=label, category="normal",
                         difficulty="standard", split="evaluation", fields=base,
                         evidence_ids=("e1",))


# ---------------------------------------------------------------------------
# Candidate-file validation: partial or malformed runs must not be scorable
# ---------------------------------------------------------------------------

def test_missing_prediction_rows_are_rejected(tmp_path):
    path = _write_candidate(tmp_path / "c.csv", [_candidate_row("A"), _candidate_row("B")])
    with pytest.raises(ValueError, match="do not match frozen split"):
        load_candidate(path, {"A", "B", "C"})


def test_duplicate_transaction_ids_are_rejected(tmp_path):
    path = _write_candidate(tmp_path / "c.csv", [_candidate_row("A"), _candidate_row("A")])
    with pytest.raises(ValueError, match="duplicate"):
        load_candidate(path, {"A"})


def test_unknown_transaction_ids_are_rejected(tmp_path):
    path = _write_candidate(tmp_path / "c.csv", [_candidate_row("A"), _candidate_row("Z")])
    with pytest.raises(ValueError, match="do not match frozen split"):
        load_candidate(path, {"A"})


def test_empty_prediction_file_is_rejected(tmp_path):
    path = _write_candidate(tmp_path / "c.csv", [])
    with pytest.raises(ValueError, match="empty"):
        load_candidate(path, {"A"})


def test_missing_metadata_columns_are_rejected(tmp_path):
    columns = [c for c in CANDIDATE_COLUMNS if c not in {"run_id", "random_seed"}]
    row = {k: v for k, v in _candidate_row("A").items() if k in columns}
    path = _write_candidate(tmp_path / "c.csv", [row], columns=columns)
    with pytest.raises(ValueError, match="missing required columns"):
        load_candidate(path, {"A"})


@pytest.mark.parametrize("bad", ["2", "-1", "maybe", "", "0.5"])
def test_invalid_prediction_values_are_rejected(tmp_path, bad):
    path = _write_candidate(tmp_path / "c.csv", [_candidate_row("A", prediction=bad)])
    with pytest.raises(ValueError):
        load_candidate(path, {"A"})


@pytest.mark.parametrize("field,value", [
    ("groundedness", "1.5"), ("groundedness", "-0.2"),
    ("citation_correctness", "2"), ("confidence", "1.4"), ("cost_usd", "-0.01"),
    ("latency_ms", "-5"),
])
def test_out_of_range_numeric_fields_are_rejected(tmp_path, field, value):
    path = _write_candidate(tmp_path / "c.csv", [_candidate_row("A", **{field: value})])
    with pytest.raises(ValueError):
        load_candidate(path, {"A"})


def test_valid_candidate_file_loads(tmp_path):
    path = _write_candidate(tmp_path / "c.csv",
                            [_candidate_row("A"), _candidate_row("B", prediction="0")])
    loaded = load_candidate(path, {"A", "B"})
    assert [r.transaction_id for r in loaded] == ["A", "B"]
    assert [r.prediction for r in loaded] == [1, 0]


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def test_specificity_is_true_negative_rate():
    labels = [0, 0, 0, 0, 1, 1]
    predictions = [0, 0, 1, 1, 1, 1]
    metrics = classification_metrics(labels, predictions)
    assert metrics["specificity"] == pytest.approx(2 / 4)
    assert metrics["confusion_matrix"] == {"tp": 2, "fp": 2, "fn": 0, "tn": 2}
    assert metrics["recall"] == pytest.approx(1.0)


def test_all_negative_predictions_give_zero_recall_and_full_specificity():
    labels = [1, 1, 0, 0, 0]
    metrics = classification_metrics(labels, [0] * 5)
    assert metrics["recall"] == pytest.approx(0.0)
    assert metrics["specificity"] == pytest.approx(1.0)
    assert metrics["precision"] is None      # undefined, not silently 0
    assert metrics["f1"] == pytest.approx(0.0)
    assert metrics["accuracy"] == pytest.approx(3 / 5)


def test_all_positive_predictions_expose_zero_specificity():
    """The failure mode that made the old rule baseline look good."""
    labels = [1] * 9 + [0]
    metrics = classification_metrics(labels, [1] * 10)
    assert metrics["f1"] > 0.9
    assert metrics["specificity"] == pytest.approx(0.0)
    assert metrics["mcc"] is None


def test_metrics_reject_mismatched_inputs():
    with pytest.raises(ValueError):
        classification_metrics([1, 0], [1])
    with pytest.raises(ValueError):
        classification_metrics([], [])


def test_operational_metrics_ignore_errored_rows_for_latency():
    rows = [
        {"latency_ms": 10, "cost_usd": 0.1, "confidence": 0.5, "evidence_ids": ["e"],
         "error": ""},
        {"latency_ms": 9999, "cost_usd": 0.0, "confidence": 0.0, "evidence_ids": [],
         "error": "provider_failure:boom"},
    ]
    operational = operational_metrics(rows)
    assert operational["mean_latency_ms"] == pytest.approx(10)
    assert operational["failure_rate"] == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------

def test_mcnemar_is_symmetric_and_significant_when_one_side_dominates():
    labels = [1] * 20
    first = [1] * 20      # every case right
    second = [0] * 20     # every case wrong
    test = mcnemar_test(labels, first, second)
    # discordant_first_only == "first argument right, second wrong", which is how
    # analyze_results labels the column: reference right, method wrong.
    assert test["discordant_first_only"] == 20
    assert test["discordant_second_only"] == 0
    assert test["p_value"] < 0.001
    flipped = mcnemar_test(labels, second, first)
    assert flipped["p_value"] == pytest.approx(test["p_value"])


def test_mcnemar_returns_unity_when_methods_never_differ():
    labels = [1, 0, 1, 0]
    assert mcnemar_test(labels, labels, labels)["p_value"] == 1.0


def test_bootstrap_metric_ci_brackets_the_point_estimate():
    labels = [1, 1, 1, 0, 0, 0, 1, 0, 1, 0] * 5
    predictions = [1, 1, 0, 0, 0, 1, 1, 0, 1, 0] * 5
    interval = bootstrap_metric_ci(
        labels, predictions, None,
        lambda y, p, s: classification_metrics(y, p)["accuracy"], samples=300)
    assert interval["lower"] <= interval["estimate"] <= interval["upper"]
    assert interval["valid_samples"] > 0


def test_bootstrap_is_deterministic_for_a_fixed_seed():
    values = [1.0, 2.0, 3.0, 4.0, 5.0]
    assert bootstrap_ci(values, samples=200) == bootstrap_ci(values, samples=200)


def test_holm_adjusts_upward_and_stays_monotone():
    corrected = holm_bonferroni({"a": 0.001, "b": 0.02, "c": 0.04, "d": 0.9})
    assert corrected["a"]["p_adjusted"] == pytest.approx(0.004)
    assert corrected["a"]["significant"] is True
    assert corrected["d"]["significant"] is False
    ordered = sorted(corrected.values(), key=lambda item: item["rank"])
    adjusted = [item["p_adjusted"] for item in ordered]
    assert adjusted == sorted(adjusted)


def test_holm_on_empty_family_is_empty():
    assert holm_bonferroni({}) == {}


# ---------------------------------------------------------------------------
# Split integrity
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name", ["uci_audit_v1", "gl_synthetic_v1"])
def test_splits_partition_the_dataset_without_overlap(name):
    benchmark = benchmarks.load(name)
    development = {c.case_id for c in benchmark.development}
    evaluation = {c.case_id for c in benchmark.evaluation}
    assert not development & evaluation
    assert len(development) + len(evaluation) == len(benchmark.cases)
    assert len(evaluation) > 0 and len(development) > 0


def test_uci_split_counts_are_the_documented_ones():
    benchmark = benchmarks.load("uci_audit_v1")
    records = benchmark.manifest["records"]
    assert len(benchmark.cases) == records["total"] == 776
    assert len(benchmark.development) == records["development"]
    assert len(benchmark.evaluation) == records["evaluation"]
    assert records["evaluation"] >= 300, "held-out set must stay large enough to report on"
    assert records["evaluation_negative"] >= 100
    assert records["evaluation_hard_negatives"] > 0


def test_uci_split_is_content_addressed_and_stable():
    from scripts.build_uci_audit_benchmark import deterministic_split
    assert deterministic_split("UCIA-0000") == deterministic_split("UCIA-0000")
    benchmark = benchmarks.load("uci_audit_v1")
    for case in benchmark.cases:
        assert deterministic_split(case.case_id) == case.split


def test_case_ids_are_unique_across_the_benchmark():
    for name in ("uci_audit_v1", "gl_synthetic_v1"):
        benchmark = benchmarks.load(name)
        ids = [c.case_id for c in benchmark.cases]
        assert len(ids) == len(set(ids))


# ---------------------------------------------------------------------------
# Label isolation: the core integrity guarantee
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name", ["uci_audit_v1", "gl_synthetic_v1"])
def test_model_view_never_exposes_the_label(name):
    benchmark = benchmarks.load(name)
    for case in benchmark.evaluation[:50]:
        view = case.model_view()
        assert not LABEL_FIELDS & set(view)
        assert "risk_label" not in view


def test_rendered_prompt_contains_no_label_token():
    benchmark = benchmarks.load("uci_audit_v1")
    for case in benchmark.evaluation[:25]:
        rendered = render_case(case, benchmark.corpus, include_evidence=True)
        assert "risk_label" not in rendered
        assert "label_source" not in rendered
        assert case.category not in rendered or case.category in {"unknown"}


def test_no_rag_condition_actually_withholds_evidence():
    benchmark = benchmarks.load("uci_audit_v1")
    case = benchmark.evaluation[0]
    with_evidence = render_case(case, benchmark.corpus, include_evidence=True)
    without = render_case(case, benchmark.corpus, include_evidence=False)
    assert "[" + case.evidence_ids[0] + "]" in with_evidence
    assert case.evidence_ids[0] not in without


def test_uci_builder_drops_every_label_derived_column():
    from scripts.build_uci_audit_benchmark import DROPPED_LEAKING_COLUMNS
    benchmark = benchmarks.load("uci_audit_v1")
    columns = set(benchmark.cases[0].fields)
    lowered = {c.lower() for c in columns}
    for leaked in DROPPED_LEAKING_COLUMNS:
        assert leaked.lower() not in lowered
    assert "audit_risk" not in lowered and "inherent_risk" not in lowered


def test_rule_baseline_prediction_does_not_depend_on_the_label():
    benchmark = benchmarks.load("uci_audit_v1")
    cases = list(benchmark.evaluation[:40])
    original = run_rule_baseline(cases, benchmark.name)
    flipped_cases = [
        BenchmarkCase(case_id=c.case_id, label=1 - c.label, category=c.category,
                      difficulty=c.difficulty, split=c.split,
                      fields=c.fields | {"risk_label": str(1 - c.label)},
                      evidence_ids=c.evidence_ids)
        for c in cases
    ]
    flipped = run_rule_baseline(flipped_cases, benchmark.name)
    assert [r.prediction for r in original] == [r.prediction for r in flipped]


def test_supervised_reference_only_sees_development_labels():
    benchmark = benchmarks.load("uci_audit_v1")
    columns = FEATURE_SETS["uci_audit_v1"]
    model = fit_logistic(benchmark.development, columns)
    assert len(model.weights) == len(columns)
    assert all(abs(w) < 100 for w in model.weights)


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("field,value", [
    ("prediction", 2), ("prediction", -1), ("confidence", 1.2), ("confidence", -0.1),
    ("groundedness", 1.5), ("citation_correctness", -0.5), ("cost_usd", -1.0),
    ("latency_ms", -1.0), ("transaction_id", ""),
])
def test_result_schema_rejects_invalid_values(field, value):
    result = ExperimentResult(transaction_id="A", method="m", prediction=1, confidence=0.5)
    setattr(result, field, value)
    with pytest.raises(ValueError):
        result.validate()


def test_result_schema_accepts_unscored_evidence_metrics():
    result = ExperimentResult(transaction_id="A", method="m", prediction=1, confidence=0.5)
    assert result.groundedness is None
    result.validate()
    assert result.to_dict()["groundedness"] is None


# ---------------------------------------------------------------------------
# Cost, configuration and the cost guard
# ---------------------------------------------------------------------------

def test_cost_is_measured_from_token_counts():
    assert _cost(1_000_000, 0, (3.0, 15.0)) == pytest.approx(3.0)
    assert _cost(0, 1_000_000, (3.0, 15.0)) == pytest.approx(15.0)
    assert _cost(0, 0, (3.0, 15.0)) == 0.0


def test_unknown_model_refuses_to_report_a_fabricated_cost():
    config = LLMConfig(provider="anthropic", model="not-a-real-model")
    with pytest.raises(ProviderError, match="no price entry"):
        config.prices()
    override = LLMConfig(provider="anthropic", model="not-a-real-model",
                         price_per_mtok_in=1.0, price_per_mtok_out=2.0)
    assert override.prices() == (1.0, 2.0)


def test_every_configured_model_has_a_price():
    for path in CONFIG_DIR.glob("*.yaml"):
        config = load_config(path)
        if config.provider in {"none", "environment"}:
            continue
        assert config.model in PRICE_TABLE, f"{path.name} uses an unpriced model"


def test_call_counts_match_the_declared_architecture():
    def make(**kwargs) -> ExperimentConfig:
        base = dict(method="full_multi_agent", provider="anthropic", model="m",
                    temperature=0.0, max_tokens=100, retrieval_enabled=True,
                    challenger_enabled=True, defender_enabled=True, verifier_enabled=True,
                    debate_rounds=2, confidence_threshold=0.5, prompt_version="v",
                    dataset_version="d", split_seed=1, timeout_seconds=10, retries=1)
        base.update(kwargs)
        return ExperimentConfig(**base)

    # detective + 2 rounds x (challenger + defender) + verifier = 6
    assert estimate_calls(make(), 1) == 6
    assert estimate_calls(make(challenger_enabled=False), 1) == 4
    assert estimate_calls(make(verifier_enabled=False), 1) == 5
    assert estimate_calls(make(debate_rounds=1), 1) == 4
    assert estimate_calls(make(method="single_llm"), 10) == 10
    assert estimate_calls(make(method="rule_baseline"), 10) == 0


def test_cost_guard_blocks_a_run_over_the_ceiling():
    benchmark = benchmarks.load("uci_audit_v1")
    config = load_config(CONFIG_DIR / "full_multi_agent.yaml")
    llm = LLMConfig(provider="anthropic", model=config.model)
    assert project_cost(config, llm, len(benchmark.evaluation)) > 0.01
    with pytest.raises(CostLimitExceeded):
        run_method(benchmark, config, llm=llm, max_cost_usd=0.0001)


def test_resolved_config_hash_changes_with_any_setting():
    config = load_config(CONFIG_DIR / "full_multi_agent.yaml")
    llm = LLMConfig(provider="anthropic", model=config.model)
    first = resolved_config_sha256(config, "uci_audit_v1", llm)
    assert first == resolved_config_sha256(config, "uci_audit_v1", llm)
    assert first != resolved_config_sha256(config, "gl_synthetic_v1", llm)
    other = LLMConfig(provider="anthropic", model=config.model, temperature=0.7)
    assert first != resolved_config_sha256(config, "uci_audit_v1", other)


def test_ablation_configs_differ_from_the_full_system_in_exactly_one_way():
    full = load_config(CONFIG_DIR / "full_multi_agent.yaml")
    expected = {
        "no_challenger": "challenger_enabled",
        "no_defender": "defender_enabled",
        "no_verifier": "verifier_enabled",
        "no_rag": "retrieval_enabled",
    }
    for name, switch in expected.items():
        ablated = load_config(CONFIG_DIR / f"{name}.yaml")
        differences = {
            field for field in vars(full)
            if field not in {"method", "prompt_version"}
            and getattr(full, field) != getattr(ablated, field)
        }
        assert differences == {switch}, f"{name} changes {differences}, expected {{{switch}}}"
        assert getattr(ablated, switch) is False


def test_config_loader_ignores_documentation_keys(tmp_path):
    payload = json.loads((CONFIG_DIR / "rule_baseline.yaml").read_text(encoding="utf-8"))
    payload["_note"] = "ignore me"
    path = tmp_path / "c.yaml"
    path.write_text(json.dumps(payload), encoding="utf-8")
    assert load_config(path).method == "rule_baseline"


# ---------------------------------------------------------------------------
# Prompts and response parsing
# ---------------------------------------------------------------------------

def test_prompt_version_tracks_prompt_content():
    first = prompt_version("single_llm_v1", "output_contract_v1")
    assert first == prompt_version("single_llm_v1", "output_contract_v1")
    assert first != prompt_version("detective_v1", "output_contract_v1")


def test_prompt_version_fails_loudly_on_a_missing_prompt():
    with pytest.raises(FileNotFoundError):
        prompt_version("no_such_prompt")


def test_verdict_parsing_survives_prose_and_fences():
    text = ('Here is my assessment.\n```json\n'
            '{"prediction": 1, "confidence": 0.82, "explanation": "x", '
            '"citations": ["e1"]}\n```\nHope that helps.')
    verdict = parse_verdict(text)
    assert verdict.prediction == 1
    assert verdict.confidence == pytest.approx(0.82)
    assert verdict.citations == ["e1"]


def test_verdict_parsing_drops_invented_citations():
    text = '{"prediction": 0, "confidence": 0.4, "citations": ["real", "fabricated"]}'
    verdict = parse_verdict(text, allowed_citations={"real"})
    assert verdict.citations == ["real"]


@pytest.mark.parametrize("text", [
    "no json here",
    '{"confidence": 0.5}',
    '{"prediction": 7, "confidence": 0.5}',
    '{"prediction": 1, "confidence": 3}',
    '{"prediction": 1, "confidence": 0.5, "citations": "e1"}',
    '{"prediction": "definitely", "confidence": 0.5}',
])
def test_unparseable_verdicts_raise_rather_than_guess(text):
    with pytest.raises(ValueError):
        parse_verdict(text)


def test_json_containing_braces_in_strings_is_parsed():
    text = '{"prediction": 1, "confidence": 0.5, "explanation": "a } brace {"}'
    assert parse_verdict(text).prediction == 1


# ---------------------------------------------------------------------------
# Judges
# ---------------------------------------------------------------------------

def test_judge_prompt_is_label_blind():
    lowered = JUDGE_SYSTEM.lower()
    assert "risk_label" not in lowered
    assert "not told what the correct answer is" in lowered


@pytest.mark.parametrize("text", [
    '{"groundedness": 0.7, "citation_correctness": 1}',   # off-rubric value
    '{"groundedness": 1}',                                # missing metric
    "no json",
])
def test_off_rubric_judge_output_is_rejected(text):
    with pytest.raises(ValueError):
        _parse_scores(text)


def test_judges_within_one_step_are_averaged_and_wider_gaps_escalate():
    close = {"A": [Judgment("A", "judge_a", "m", 1.0, 1.0),
                   Judgment("A", "judge_b", "m", 0.5, 1.0)]}
    far = {"B": [Judgment("B", "judge_a", "m", 1.0, 1.0),
                 Judgment("B", "judge_b", "m", 0.0, 1.0)]}
    resolved = reconcile(close, "groundedness")[0]
    assert resolved.needs_human is False
    assert resolved.resolved == pytest.approx(0.75)
    escalated = reconcile(far, "groundedness")[0]
    assert escalated.needs_human is True
    assert escalated.resolved is None


def test_reconcile_flags_items_no_judge_could_score():
    failed = {"C": [Judgment("C", "judge_a", "m", None, None, error="boom")]}
    row = reconcile(failed, "groundedness")[0]
    assert row.needs_human is True
    assert row.scores == {}


# ---------------------------------------------------------------------------
# Provider behaviour
# ---------------------------------------------------------------------------

class _StubProvider(Provider):
    """Records calls so architecture tests do not need a network."""

    def __init__(self, config, cache, response: str):
        super().__init__(config, cache)
        self.response = response
        self.calls: list[tuple[str, str]] = []

    def complete(self, system: str, user: str) -> Completion:
        self.calls.append((system, user))
        return Completion(text=self.response, input_tokens=100, output_tokens=20,
                          cost_usd=_cost(100, 20, self.config.prices()),
                          latency_ms=1.0, model=self.config.model,
                          provider=self.config.provider)


def test_missing_api_key_aborts_instead_of_fixturing(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    from experiments.llm import AnthropicProvider
    provider = AnthropicProvider(LLMConfig(provider="anthropic",
                                           model="claude-haiku-4-5-20251001"))
    with pytest.raises(ProviderError, match="not set"):
        provider.api_key()


def test_multi_agent_makes_the_expected_number_of_calls(tmp_path):
    from experiments.runners.llm_agents import run_multi_agent
    benchmark = benchmarks.load("uci_audit_v1")
    config = load_config(CONFIG_DIR / "full_multi_agent.yaml")
    llm = LLMConfig(provider="anthropic", model=config.model, use_cache=False)
    provider = _StubProvider(llm, ResponseCache(tmp_path),
                             '{"prediction": 1, "confidence": 0.7, '
                             '"explanation": "e", "citations": []}')
    cases = benchmark.evaluation[:3]
    results = run_multi_agent(cases, provider, benchmark.corpus, config)
    assert len(results) == 3
    assert len(provider.calls) == estimate_calls(config, len(cases))
    assert all(r.input_tokens == 600 for r in results)   # 6 calls x 100 tokens
    assert all(not r.error for r in results)


def test_unparseable_model_output_is_recorded_as_an_error_not_a_guess(tmp_path):
    from experiments.runners.llm_agents import run_single_llm
    benchmark = benchmarks.load("uci_audit_v1")
    config = load_config(CONFIG_DIR / "single_llm.yaml")
    llm = LLMConfig(provider="anthropic", model=config.model, use_cache=False)
    provider = _StubProvider(llm, ResponseCache(tmp_path), "I would rather not say.")
    results = run_single_llm(benchmark.evaluation[:2], provider, benchmark.corpus, config)
    assert all(r.error.startswith("parse_failure") for r in results)
    assert all(r.prediction == 0 for r in results)
    assert all(r.confidence == 0.0 for r in results)


def test_response_cache_round_trips(tmp_path):
    cache = ResponseCache(tmp_path)
    assert cache.get("missing") is None
    cache.put("k", {"text": "hello", "input_tokens": 1, "output_tokens": 2,
                    "latency_ms": 3.0})
    assert cache.get("k")["text"] == "hello"
    assert cache.hits == 1 and cache.misses == 1


# ---------------------------------------------------------------------------
# End-to-end on the committed artifacts
# ---------------------------------------------------------------------------

def test_rule_baseline_on_real_data_reproduces_the_documented_screen():
    benchmark = benchmarks.load("uci_audit_v1")
    results = run_rule_baseline(benchmark.evaluation, benchmark.name)
    labels = [c.label for c in benchmark.evaluation]
    predictions = [r.prediction for r in results]
    metrics = classification_metrics(labels, predictions)
    # The audit office's screen is recall-complete by construction; if this ever fails,
    # the dataset's nesting invariant has broken.
    assert metrics["recall"] == pytest.approx(1.0)
    assert 0.5 < metrics["specificity"] < 0.9


def test_uci_manifest_matches_the_committed_csv():
    benchmark = benchmarks.load("uci_audit_v1")
    records = benchmark.manifest["records"]
    evaluation = benchmark.evaluation
    assert sum(c.label for c in evaluation) == records["evaluation_positive"]
    assert sum(1 - c.label for c in evaluation) == records["evaluation_negative"]


def test_every_referenced_evidence_id_resolves():
    for name in ("uci_audit_v1", "gl_synthetic_v1"):
        benchmark = benchmarks.load(name)
        assert benchmark.corpus, f"{name} has no evidence corpus"
        for case in benchmark.cases[:100]:
            for evidence_id in case.evidence_ids:
                assert evidence_id in benchmark.corpus, f"{name}: dangling {evidence_id}"
