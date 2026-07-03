"""Ground-truth review field -> real-time RAGAS scoring pipeline.

Covers app/api/routes/reviews.py's ground_truth handling and its hookup to
app/tasks/celery_app.py::score_investigation_ragas_task. The ragas judge LLM
calls are mocked (no real Anthropic API calls); judge_available() is forced
on so the scoring path actually runs instead of no-op'ing on a missing key.

POST /investigations only creates the bare intake record (no debate/evidence
yet - that comes from the crew pipeline, exercised separately in
test_executor.py), so these tests seed a completed-case's rows directly via
the `db` fixture: an evidence artifact, an adjudicator verdict transcript
(what app/evaluation/ragas_judge.py::_verdict_response reads), and an
LLMCallLog (what _scored_llm reads to attribute a score to a provider/model).
"""

from unittest.mock import AsyncMock, patch

from app.db.models import DebateTranscript, EvidenceArtifact, Investigation, LLMCallLog, RagasEvaluationResult


def _create(client, txn):
    r = client.post(
        "/api/v1/investigations",
        json={"transaction_id": txn, "vendor": "Acme", "category": "consulting", "amount": 80000.0},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _create_completed_case(client, db, txn):
    """Create an investigation and seed it with the evidence/debate/LLM-call
    rows a case would have after actually going through the crew pipeline."""
    inv_id = _create(client, txn)
    db.add(
        EvidenceArtifact(
            investigation_id=inv_id,
            source="ledger_row",
            content=f"Ledger detail for {txn}.",
            relevance_score=0.85,
        )
    )
    db.add(
        DebateTranscript(
            investigation_id=inv_id,
            round=1,
            speaker="adjudicator",
            message="Verdict: low risk at 90% confidence. Fully supported by policy.",
            token_count=12,
        )
    )
    db.add(
        LLMCallLog(
            investigation_id=inv_id,
            provider_name="anthropic",
            model_name="claude-sonnet-5",
            request_type="adjudication",
            success=True,
        )
    )
    db.commit()
    return inv_id


def _mock_all_ragas_metrics():
    targets = [
        "ragas.metrics.Faithfulness.single_turn_ascore",
        "ragas.metrics.LLMContextPrecisionWithoutReference.single_turn_ascore",
        "ragas.metrics.ResponseRelevancy.single_turn_ascore",
        "ragas.metrics.ToolCallAccuracy.multi_turn_ascore",
        "ragas.metrics.TopicAdherenceScore.multi_turn_ascore",
        "ragas.metrics.AgentGoalAccuracyWithoutReference.multi_turn_ascore",
        "ragas.metrics.ContextEntityRecall.single_turn_ascore",
        "ragas.metrics.FactualCorrectness.single_turn_ascore",
        "ragas.metrics.SemanticSimilarity.single_turn_ascore",
    ]
    return [patch(target, new=AsyncMock(return_value=0.88)) for target in targets]


def test_approve_without_ground_truth_does_not_score(client, db):
    inv_id = _create(client, txn="TXN-GT-1")
    r = client.post(f"/api/v1/reviews/{inv_id}/approve", json={"actor": "bob"})
    assert r.status_code == 200
    inv = db.get(Investigation, inv_id)
    assert inv.ground_truth_verdict is None
    rows = db.query(RagasEvaluationResult).filter(RagasEvaluationResult.investigation_id == inv_id).all()
    assert rows == []


def test_approve_with_ground_truth_stores_verdict_and_scores(client, db, monkeypatch):
    from app.evaluation import ragas_judge as rj

    monkeypatch.setattr(rj, "judge_available", lambda: True)
    patchers = _mock_all_ragas_metrics()
    for p in patchers:
        p.start()
    try:
        inv_id = _create_completed_case(client, db, txn="TXN-GT-2")
        r = client.post(
            f"/api/v1/reviews/{inv_id}/approve",
            json={
                "actor": "bob",
                "ground_truth": "This transaction was legitimate and properly authorized.",
            },
        )
        assert r.status_code == 200, r.text

        inv = db.get(Investigation, inv_id)
        assert inv.ground_truth_verdict == "This transaction was legitimate and properly authorized."
        assert inv.ground_truth_set_at is not None

        rows = (
            db.query(RagasEvaluationResult)
            .filter(RagasEvaluationResult.investigation_id == inv_id)
            .all()
        )
        # All 9 judge-scoreable metrics (Context Recall has no honest
        # no-reference formulation and stays proxy-only - see
        # app/evaluation/ragas_judge.py module docstring).
        assert {row.metric for row in rows} == {
            "Faithfulness",
            "Context Precision",
            "Response Relevancy",
            "Tool Call Accuracy",
            "Topic Adherence",
            "Agent Goal Accuracy",
            "Context Entity Recall",
            "Factual Correctness",
            "Semantic Similarity",
        }
        reference_rows = {row.metric for row in rows if row.is_reference_metric}
        assert reference_rows == {"Context Entity Recall", "Factual Correctness", "Semantic Similarity"}
        assert all(row.score == 0.88 for row in rows)
        assert all(row.scored_provider == "anthropic" for row in rows)
        assert all(row.scored_model == "claude-sonnet-5" for row in rows)
    finally:
        for p in patchers:
            p.stop()


def test_evaluation_case_endpoint_reflects_real_scores(client, db, monkeypatch):
    from app.evaluation import ragas_judge as rj

    monkeypatch.setattr(rj, "judge_available", lambda: True)
    patchers = _mock_all_ragas_metrics()
    for p in patchers:
        p.start()
    try:
        inv_id = _create_completed_case(client, db, txn="TXN-GT-3")
        r = client.post(
            f"/api/v1/reviews/{inv_id}/reject",
            json={"actor": "carol", "ground_truth": "Unauthorized vendor payment."},
        )
        assert r.status_code == 200, r.text

        r = client.get(f"/api/v1/evaluation/case/{inv_id}")
        assert r.status_code == 200, r.text
        metrics = {m["metric"]: m for m in r.json()["metrics"]}
        assert metrics["Faithfulness"]["source"] == "real"
        assert metrics["Faithfulness"]["score"] == 0.88
        assert metrics["Faithfulness"]["scored_provider"] == "anthropic"
        # Context Recall has no real-time judge formulation; must fall back
        # to the telemetry proxy rather than showing a blank/zero score.
        assert metrics["Context Recall"]["source"] == "proxy"
    finally:
        for p in patchers:
            p.stop()


def test_by_llm_breakdown_only_includes_real_scores(client, db, monkeypatch):
    from app.evaluation import ragas_judge as rj

    monkeypatch.setattr(rj, "judge_available", lambda: True)
    patchers = _mock_all_ragas_metrics()
    for p in patchers:
        p.start()
    try:
        inv_id = _create_completed_case(client, db, txn="TXN-GT-4")
        r = client.post(
            f"/api/v1/reviews/{inv_id}/approve",
            json={"actor": "dave", "ground_truth": "Legitimate."},
        )
        assert r.status_code == 200, r.text
    finally:
        for p in patchers:
            p.stop()

    r = client.get("/api/v1/evaluation/by-llm")
    assert r.status_code == 200, r.text
    body = r.json()
    assert isinstance(body, list)
    assert len(body) >= 9  # at least the 9 judge-scoreable metrics for this case's provider/model
    anthropic_rows = [row for row in body if row["provider"] == "anthropic" and row["model"] == "claude-sonnet-5"]
    assert len(anthropic_rows) >= 9
    for row in body:
        assert 0.0 <= row["mean_score"] <= 1.0
        assert row["cases_scored"] >= 1
