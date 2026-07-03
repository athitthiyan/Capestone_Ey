"""RAGAS evaluation endpoint + scorer tests."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base, EvidenceArtifact, Investigation, InvestigationStatus, VerificationClaim
from app.evaluation.ragas import METRIC_CATALOG, compute_ragas_summary


def test_metric_catalog_endpoint(client):
    r = client.get("/api/v1/evaluation/metrics")
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body) == len(METRIC_CATALOG) == 10
    names = {m["metric"] for m in body}
    assert {"Faithfulness", "Context Recall", "Agent Goal Accuracy"} <= names
    for m in body:
        assert {"metric", "category", "score", "target", "pass", "helper"} <= set(m)
        assert m["category"] in ("retrieval", "generation", "agentic")


def test_summary_shape_is_valid(client):
    r = client.get("/api/v1/evaluation/summary")
    assert r.status_code == 200, r.text
    body = r.json()
    assert {"cases", "metrics", "conclusion"} <= set(body)
    assert isinstance(body["metrics"], list)


def test_summary_scores_when_data_present():
    """Score against an isolated in-memory DB so the result is deterministic
    (the shared suite DB is contaminated by other tests' claims)."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        inv = Investigation(
            transaction_id="EVAL-1",
            vendor="Acme",
            category="consulting",
            amount=1000.0,
            confidence=0.9,
            status=InvestigationStatus.CLOSED,
        )
        session.add(inv)
        session.commit()
        session.refresh(inv)
        session.add(
            EvidenceArtifact(
                investigation_id=inv.id,
                source="policy-kb",
                content="Approval matrix clause 4.2",
                relevance_score=0.9,
                citations=["clause-4.2"],
            )
        )
        session.add(
            VerificationClaim(
                investigation_id=inv.id,
                claim_text="Amount within approval limit",
                is_grounded=True,
            )
        )
        session.commit()

        summary = compute_ragas_summary(session)
        assert summary["cases"] == 1
        assert len(summary["metrics"]) == 10
        faithfulness = next(m for m in summary["metrics"] if m["metric"] == "Faithfulness")
        assert faithfulness["score"] == 1.0
        assert faithfulness["pass"] is True
        for m in summary["metrics"]:
            assert 0.0 <= m["score"] <= 1.0
    finally:
        session.close()


def test_summary_endpoint_returns_pass_key(client):
    r = client.get("/api/v1/evaluation/summary")
    assert r.status_code == 200, r.text
    assert all("pass" in m for m in r.json()["metrics"])


def test_metrics_default_to_proxy_source(client):
    """Before any real-time RAGAS judge score exists, every metric on the
    aggregate summary should be tagged as coming from the telemetry proxy."""
    r = client.get("/api/v1/evaluation/summary")
    assert r.status_code == 200, r.text
    assert all(m.get("source", "proxy") == "proxy" for m in r.json()["metrics"])


def test_overlay_real_scores_prefers_real_and_falls_back_to_proxy():
    from app.api.routes.evaluation import _overlay_real_scores
    from app.db.models import RagasEvaluationResult

    summary = {
        "cases": 1,
        "metrics": [
            {"metric": "Faithfulness", "category": "generation", "score": 0.5, "target": 0.9, "pass": False, "helper": "x"},
            {"metric": "Context Recall", "category": "retrieval", "score": 0.6, "target": 0.85, "pass": False, "helper": "y"},
        ],
        "conclusion": "",
    }
    real_rows = {
        "Faithfulness": RagasEvaluationResult(
            metric="Faithfulness", score=0.95, scored_provider="anthropic", scored_model="claude-sonnet-5"
        ),
        # Context Recall present in the table but with a null score (judge
        # failed/skipped) - must still fall back to the proxy value.
        "Context Recall": RagasEvaluationResult(metric="Context Recall", score=None),
    }
    result = _overlay_real_scores(summary, real_rows)
    by_metric = {m["metric"]: m for m in result["metrics"]}
    assert by_metric["Faithfulness"]["score"] == 0.95
    assert by_metric["Faithfulness"]["pass"] is True
    assert by_metric["Faithfulness"]["source"] == "real"
    assert by_metric["Faithfulness"]["scored_provider"] == "anthropic"
    assert by_metric["Context Recall"]["score"] == 0.6
    assert by_metric["Context Recall"]["source"] == "proxy"


def test_by_llm_endpoint_empty_when_no_real_scores(client):
    r = client.get("/api/v1/evaluation/by-llm")
    assert r.status_code == 200, r.text
    assert isinstance(r.json(), list)
