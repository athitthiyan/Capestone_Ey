"""Tests for stats, sub-resource, review, and auth endpoints."""

from app.core.config import settings
from app.db.models import (
    AuditLog,
    DebateTranscript,
    EvidenceArtifact,
    Investigation,
    InvestigationState,
    ReviewQueueItem,
    ThirdPartyEvidenceVerification,
    VerificationClaim,
)


def _create(client, txn="TXN-EP", amount=80000.0):
    r = client.post(
        "/api/v1/investigations",
        json={"transaction_id": txn, "vendor": "Acme", "category": "consulting", "amount": amount},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_stats_summary(client):
    _create(client, txn="TXN-STATS")
    r = client.get("/api/v1/investigations/stats/summary")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] >= 1
    assert "by_risk" in body and "by_status" in body
    assert body["by_status"].get("intake", 0) >= 1


def test_subresources_empty_for_new_case(client):
    inv_id = _create(client, txn="TXN-SUB")
    for sub in ("debate", "evidence", "verification", "audit"):
        r = client.get(f"/api/v1/investigations/{inv_id}/{sub}")
        assert r.status_code == 200, (sub, r.text)
        assert isinstance(r.json(), list)


def test_delete_imported_investigations_removes_cases_and_generated_data(client, db):
    imported_id = _create(client, txn="TXN-IMPORTED")
    manual_id = _create(client, txn="TXN-MANUAL")
    imported = db.get(Investigation, imported_id)
    imported.owner = "intake"
    db.add_all(
        [
            EvidenceArtifact(investigation_id=imported_id, source="ledger", content="source row"),
            DebateTranscript(
                investigation_id=imported_id,
                round=1,
                speaker="challenger",
                message="challenge",
                token_count=1,
            ),
            VerificationClaim(investigation_id=imported_id, claim_text="claim", is_grounded=True),
            InvestigationState(
                investigation_id=imported_id,
                phase="test",
                state_json={"ok": True},
                checkpoint_hash="abc",
            ),
            ReviewQueueItem(investigation_id=imported_id, status="pending"),
            ThirdPartyEvidenceVerification(
                claim_id=imported_id,
                category="generic",
                claimed_amount=1000,
                fetched_amount=None,
                tolerance_percentage=0.3,
                provider_name="test_provider",
                verification_status="NEEDS_MANUAL_REVIEW",
                confidence_score=0.3,
                reason="test",
                raw_provider_response_json={},
            ),
            AuditLog(
                investigation_id=imported_id,
                event_type="case_created",
                actor="test",
                details={},
                hash="hash",
                sequence=1,
            ),
        ]
    )
    db.commit()

    r = client.delete("/api/v1/investigations/imported")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["deleted_count"] == 1
    assert imported_id in body["investigation_ids"]

    db.expire_all()
    assert db.get(Investigation, imported_id) is None
    assert db.get(Investigation, manual_id) is not None
    for model in (
        EvidenceArtifact,
        DebateTranscript,
        VerificationClaim,
        InvestigationState,
        ReviewQueueItem,
        AuditLog,
    ):
        assert db.query(model).filter(model.investigation_id == imported_id).count() == 0
    assert db.query(ThirdPartyEvidenceVerification).filter_by(claim_id=imported_id).count() == 0


def test_debate_response_marks_adjudicator_confidence(client, db):
    inv_id = _create(client, txn="TXN-DEBATE")
    investigation = db.get(Investigation, inv_id)
    investigation.confidence = 0.84
    db.add_all(
        [
            DebateTranscript(
                investigation_id=inv_id,
                round=1,
                speaker="challenger",
                message="Amount exceeds materiality without corroboration.",
                token_count=5,
            ),
            DebateTranscript(
                investigation_id=inv_id,
                round=2,
                speaker="adjudicator",
                message="Verdict: high risk at 84% confidence.",
                token_count=7,
            ),
        ]
    )
    db.commit()

    r = client.get(f"/api/v1/investigations/{inv_id}/debate")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body[0]["speaker"] == "challenger"
    assert body[0]["confidence"] is None
    assert body[1]["speaker"] == "adjudicator"
    assert body[1]["confidence"] == 0.84


def test_subresource_404_for_missing_case(client):
    r = client.get("/api/v1/investigations/nope/debate")
    assert r.status_code == 404


def test_execute_runs_inline_without_broker(client):
    """With no Celery broker, execute falls back to in-process execution."""
    inv_id = _create(client, txn="TXN-RUN")
    r = client.post(f"/api/v1/investigations/{inv_id}/execute")
    assert r.status_code == 200, r.text
    assert r.json()["status"] in ("queued", "running")


def test_execute_falls_back_when_celery_broker_preflight_fails(client, monkeypatch):
    from app.api.routes import investigations as investigation_routes

    previous = settings.USE_CELERY
    settings.USE_CELERY = True
    monkeypatch.setattr(investigation_routes, "_celery_broker_available", lambda: False)

    async def fake_inline(_investigation_id: str) -> None:
        return None

    monkeypatch.setattr(investigation_routes, "_run_investigation_inline", fake_inline)

    try:
        inv_id = _create(client, txn="TXN-CELERY-FALLBACK")
        r = client.post(f"/api/v1/investigations/{inv_id}/execute")
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "running"
        assert r.json()["task_id"] is None
        assert "Celery broker unavailable" in r.json()["message"]
    finally:
        settings.USE_CELERY = previous


def test_review_queue_and_actions(client):
    inv_id = _create(client, txn="TXN-REVIEW")
    # Escalate moves it into the queue (critical / human_review).
    r = client.post(f"/api/v1/reviews/{inv_id}/escalate", json={"actor": "alice"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "human_review"

    q = client.get("/api/v1/reviews/queue")
    assert q.status_code == 200
    assert any(item["investigation_id"] == inv_id for item in q.json())
    queued = next(item for item in q.json() if item["investigation_id"] == inv_id)
    assert queued["queue"] == "partner"
    assert queued["assigned_to"] == "engagement_partner"
    assert queued["priority"] == 1

    r = client.post(
        f"/api/v1/reviews/{inv_id}/request-evidence",
        json={"actor": "bob", "comment": "Attach the signed SOW."},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "collecting_evidence"

    r = client.post(f"/api/v1/reviews/{inv_id}/approve", json={"actor": "bob"})
    assert r.status_code == 200
    assert r.json()["status"] == "closed"


def test_review_action_404(client):
    r = client.post("/api/v1/reviews/missing/approve", json={})
    assert r.status_code == 404


def test_auth_register_and_me(client):
    r = client.post(
        "/api/v1/auth/register",
        json={"username": "analyst1", "password": "password123", "role": "analyst"},
    )
    assert r.status_code == 201, r.text
    assert r.json()["username"] == "analyst1"

    # Duplicate registration is rejected.
    r2 = client.post(
        "/api/v1/auth/register",
        json={"username": "analyst1", "password": "password123"},
    )
    assert r2.status_code == 409

    token = client.post(
        "/api/v1/auth/token",
        data={"username": "analyst1", "password": "password123"},
    )
    assert token.status_code == 200, token.text

    previous = settings.AUTH_REQUIRED
    settings.AUTH_REQUIRED = True
    try:
        me = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token.json()['access_token']}"},
        )
        assert me.status_code == 200, me.text
        assert me.json()["username"] == "analyst1"
    finally:
        settings.AUTH_REQUIRED = previous
