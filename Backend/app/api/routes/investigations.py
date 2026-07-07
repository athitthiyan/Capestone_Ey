"""Investigation CRUD + execution routes."""

import asyncio
import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import get_current_user, require_elevated_role
from app.db.models import (
    AuditLog,
    DebateTranscript,
    EvidenceArtifact,
    Investigation,
    ReviewQueueItem,
    ThirdPartyEvidenceVerification,
    VerificationClaim,
)
from app.db.models import (
    InvestigationState as DBInvestigationState,
)
from app.db.session import get_db_session
from app.evaluation.ragas import compute_ragas_summary
from app.schemas import (
    AuditEventOut,
    ClaimEvidenceVerificationOut,
    DebateMessageOut,
    EvaluationSummaryOut,
    EvidenceOut,
    ExecuteResponse,
    InvestigationCreate,
    InvestigationDeleteResponse,
    InvestigationList,
    InvestigationOut,
    StatsSummary,
    VerificationOut,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/investigations", tags=["investigations"])


def _dump(model) -> dict:
    return model.model_dump(mode="json", by_alias=True)


def _case_report_payloads(investigation: Investigation) -> list[dict]:
    from app.api.routes.reports import REPORTABLE_STATUS_VALUES, report_payload

    status_value = (
        investigation.status.value
        if hasattr(investigation.status, "value")
        else str(investigation.status)
    )
    if status_value not in REPORTABLE_STATUS_VALUES:
        return []
    return [report_payload(investigation)]


async def _run_investigation_inline(investigation_id: str) -> None:
    """Run the investigation in-process when no Celery broker is available.

    Used as a graceful fallback so the platform works end-to-end in local dev
    without Redis/Celery. Uses its own DB session (the request session is gone
    by the time the background task runs).
    """
    from app.agents.executor import InvestigationExecutor
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        result = await InvestigationExecutor(db).execute_investigation(investigation_id)
        if isinstance(result, dict) and result.get("status") != "failed":
            _score_investigation_ragas_inline(investigation_id)
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Inline investigation {investigation_id} failed: {exc}", exc_info=True)
    finally:
        db.close()


def _score_investigation_ragas_inline(investigation_id: str) -> None:
    """Run RAGAS scoring synchronously (no broker) — mirrors the Celery hook in
    celery_app.execute_investigation_task for environments with no Redis/Celery.
    Never allowed to affect the investigation pipeline's own success/failure.
    """
    try:
        from app.tasks.celery_app import score_investigation_ragas_task

        # .run() executes the task body directly in-process, bypassing the
        # broker entirely - appropriate here since this whole path only
        # exists because no broker is available.
        score_investigation_ragas_task.run(investigation_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Inline RAGAS scoring failed for {investigation_id}: {exc}")


def _celery_broker_available() -> bool:
    """Avoid Celery's long Redis retry loop when local dev has no broker."""
    if not settings.CELERY_BROKER_URL.startswith("redis://"):
        return True

    try:
        import redis

        client = redis.Redis.from_url(
            settings.CELERY_BROKER_URL,
            socket_connect_timeout=settings.REDIS_SOCKET_TIMEOUT,
            socket_timeout=settings.REDIS_SOCKET_TIMEOUT,
        )
        client.ping()
        client.close()
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Celery broker preflight failed: {exc}")
        return False


@router.post("", response_model=InvestigationOut, status_code=status.HTTP_201_CREATED)
async def create_investigation(
    payload: InvestigationCreate,
    db: Session = Depends(get_db_session),
    user=Depends(get_current_user),
):
    posted_at = datetime.utcnow()
    investigation = Investigation(
        transaction_id=payload.transaction_id,
        vendor=payload.vendor,
        category=payload.category,
        amount=payload.amount,
        materiality=payload.materiality
        if payload.materiality is not None
        else settings.DEFAULT_MATERIALITY_THRESHOLD,
        description=payload.description,
        owner=payload.owner,
        posted_at=posted_at,
        due_at=posted_at + timedelta(days=7),
    )
    db.add(investigation)
    db.commit()
    db.refresh(investigation)
    logger.info(f"Investigation created: {investigation.id}")
    try:
        from app.audit.eventstore import log_case_created

        await log_case_created(
            investigation.id,
            actor=getattr(user, "username", None) or payload.owner or "system",
            details={
                "transaction_id": investigation.transaction_id,
                "vendor": investigation.vendor,
                "amount": investigation.amount,
                "source": "api",
            },
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Case-created audit write failed for {investigation.id}: {exc}")

    try:
        from app.api.routes.claims import record_evidence_verification_event
        from app.evidence_verification import EvidenceVerificationService

        # verify_investigation makes synchronous HTTP calls to FX/benchmark
        # providers; keep them off the event loop.
        verification = await asyncio.to_thread(
            EvidenceVerificationService().verify_investigation, db, investigation
        )
        await record_evidence_verification_event(
            verification,
            actor=getattr(user, "username", None) or payload.owner or "system",
        )
        db.refresh(investigation)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Auto evidence verification failed for %s: %s",
            investigation.id,
            exc,
            exc_info=True,
        )
    return investigation


@router.get("", response_model=InvestigationList)
async def list_investigations(
    skip: int = 0,
    limit: int = 100,
    status_filter: str | None = None,
    risk: str | None = None,
    has_debate: bool = False,
    db: Session = Depends(get_db_session),
    user=Depends(get_current_user),
):
    limit = max(1, min(limit, 500))
    query = db.query(Investigation, func.count(Investigation.id).over().label("total_count"))
    if status_filter:
        query = query.filter(Investigation.status == status_filter)
    if risk:
        query = query.filter(Investigation.risk == risk)
    if has_debate:
        # Only cases that actually have a recorded debate transcript.
        query = query.filter(
            db.query(DebateTranscript.id)
            .filter(DebateTranscript.investigation_id == Investigation.id)
            .exists()
        )

    # One round trip: a window-function total alongside the page instead of a
    # separate COUNT(*) query.
    page = query.order_by(Investigation.created_at.desc()).offset(skip).limit(limit).all()
    rows = [row for row, _ in page]
    if page:
        total = page[0][1]
    elif skip == 0:
        total = 0
    else:
        # Empty page beyond the last row (skip too large) - the window
        # function has nothing to attach a count to, so ask separately.
        # Rare path (only hit when the caller pages past the end).
        count_query = db.query(func.count(Investigation.id))
        if status_filter:
            count_query = count_query.filter(Investigation.status == status_filter)
        if risk:
            count_query = count_query.filter(Investigation.risk == risk)
        if has_debate:
            count_query = count_query.filter(
                db.query(DebateTranscript.id)
                .filter(DebateTranscript.investigation_id == Investigation.id)
                .exists()
            )
        total = count_query.scalar() or 0

    return InvestigationList(
        total=total,
        skip=skip,
        limit=limit,
        investigations=[InvestigationOut.model_validate(r) for r in rows],
    )


@router.delete("/all", response_model=InvestigationDeleteResponse)
async def delete_all_investigations(
    db: Session = Depends(get_db_session),
    user=Depends(require_elevated_role),
):
    """Full data reset: delete ALL business and telemetry data.

    Destructive and irreversible. Wipes every table EXCEPT ``users`` and
    ``runtime_settings`` - so operator accounts and configuration survive.
    Removes investigations and all their children, employee transactions,
    telemetry logs (LLM calls, RAGAS results, request logs), the audit trail,
    the review queue, and the knowledge-base index (which is re-synced on the
    next startup). Iterating the model metadata means any future table is
    included automatically, so "delete everything" stays comprehensive.
    """
    from app.db.models import Base

    investigation_ids = [row.id for row in db.query(Investigation.id).all()]

    # Wipe every table except the two we preserve, in reverse dependency order
    # (children before parents) so foreign keys are never violated. Driving this
    # off Base.metadata means new tables are covered without touching this code.
    preserved_tables = {"users", "runtime_settings"}
    for table in reversed(Base.metadata.sorted_tables):
        if table.name in preserved_tables:
            continue
        db.execute(table.delete())
    db.commit()

    try:
        from app.audit import eventstore

        await eventstore.log_case_created(
            "all-investigations-delete",
            actor=getattr(user, "username", None) or "system",
            details={
                "action": "delete_all_investigations",
                "deleted_count": len(investigation_ids),
                "source": "api",
            },
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Delete-all audit write failed: {exc}")

    return InvestigationDeleteResponse(
        deleted_count=len(investigation_ids),
        investigation_ids=investigation_ids,
        message=(
            f"Full reset complete. Deleted all data including {len(investigation_ids)} "
            "investigation(s), employee transactions, telemetry, audit, review queue, and "
            "the knowledge-base index. Users and settings were preserved."
        ),
    )


@router.delete("/imported", response_model=InvestigationDeleteResponse)
async def delete_imported_investigations(
    db: Session = Depends(get_db_session),
    user=Depends(require_elevated_role),
):
    """Delete cases created from ledger intake uploads and their generated data."""
    investigations = (
        db.query(Investigation)
        .filter(Investigation.owner == "intake")
        .order_by(Investigation.created_at.asc())
        .all()
    )
    investigation_ids = [row.id for row in investigations]

    if not investigation_ids:
        return InvestigationDeleteResponse(
            deleted_count=0,
            investigation_ids=[],
            message="No imported intake investigations were found.",
        )

    for model in (
        EvidenceArtifact,
        DebateTranscript,
        VerificationClaim,
        DBInvestigationState,
        ReviewQueueItem,
        AuditLog,
    ):
        db.query(model).filter(model.investigation_id.in_(investigation_ids)).delete(
            synchronize_session=False
        )

    db.query(ThirdPartyEvidenceVerification).filter(
        ThirdPartyEvidenceVerification.claim_id.in_(investigation_ids)
    ).delete(synchronize_session=False)

    db.query(Investigation).filter(Investigation.id.in_(investigation_ids)).delete(
        synchronize_session=False
    )
    db.commit()

    try:
        from app.audit import eventstore

        await eventstore.log_case_created(
            "intake-import-delete",
            actor=getattr(user, "username", None) or "system",
            details={
                "action": "delete_imported_investigations",
                "deleted_count": len(investigation_ids),
                "source": "api",
            },
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Imported-delete audit write failed: {exc}")

    return InvestigationDeleteResponse(
        deleted_count=len(investigation_ids),
        investigation_ids=investigation_ids,
        message=f"Deleted {len(investigation_ids)} imported intake investigation(s).",
    )


@router.get("/{investigation_id}", response_model=InvestigationOut)
async def get_investigation(
    investigation_id: str,
    db: Session = Depends(get_db_session),
    user=Depends(get_current_user),
):
    investigation = db.get(Investigation, investigation_id)
    if not investigation:
        raise HTTPException(status_code=404, detail="Investigation not found")
    return investigation


@router.get("/{investigation_id}/workspace")
async def get_investigation_workspace(
    investigation_id: str,
    db: Session = Depends(get_db_session),
    user=Depends(get_current_user),
):
    """One-shot workspace payload to avoid a cascade of client requests."""
    del user
    investigation = db.get(Investigation, investigation_id)
    if not investigation:
        raise HTTPException(status_code=404, detail="Investigation not found")

    evidence_rows = (
        db.query(EvidenceArtifact)
        .filter(EvidenceArtifact.investigation_id == investigation_id)
        .order_by(EvidenceArtifact.created_at.asc())
        .all()
    )
    debate_rows = (
        db.query(DebateTranscript)
        .filter(DebateTranscript.investigation_id == investigation_id)
        .order_by(DebateTranscript.round.asc(), DebateTranscript.created_at.asc())
        .all()
    )
    verification_rows = (
        db.query(VerificationClaim)
        .filter(VerificationClaim.investigation_id == investigation_id)
        .order_by(VerificationClaim.created_at.asc())
        .all()
    )

    async def _load_audit_events() -> list:
        try:
            from app.audit.eventstore import get_audit_log

            log = await get_audit_log()
            return await log.get_events(investigation_id, limit=50)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Workspace audit load failed for %s: %s", investigation_id, exc)
            return []

    def _load_evidence_verification():
        try:
            from app.evidence_verification import EvidenceVerificationService

            return EvidenceVerificationService().get_latest(db, investigation_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Workspace evidence verification load failed for %s: %s",
                investigation_id,
                exc,
            )
            return None

    # Two independent reads (event store + a sync ORM query) - run them
    # concurrently instead of serially awaiting one after the other.
    audit_events, latest_evidence_verification = await asyncio.gather(
        _load_audit_events(),
        asyncio.to_thread(_load_evidence_verification),
    )

    return {
        "investigation": _dump(InvestigationOut.model_validate(investigation)),
        "evidence": [
            _dump(EvidenceOut.model_validate(row))
            for row in evidence_rows
        ],
        "debate": [
            _dump(
                DebateMessageOut(
                    id=row.id,
                    round=row.round,
                    speaker=row.speaker,
                    message=row.message,
                    token_count=row.token_count or 0,
                    confidence=investigation.confidence
                    if row.speaker.lower() == "adjudicator"
                    else None,
                    created_at=row.created_at,
                )
            )
            for row in debate_rows
        ],
        "verification": [
            _dump(VerificationOut.model_validate(row))
            for row in verification_rows
        ],
        "evidence_verification": (
            _dump(ClaimEvidenceVerificationOut.model_validate(latest_evidence_verification))
            if latest_evidence_verification
            else None
        ),
        "audit": [_dump(AuditEventOut(**event)) for event in audit_events],
        "reports": _case_report_payloads(investigation),
        "evaluation": _dump(
            EvaluationSummaryOut(
                **compute_ragas_summary(
                    db,
                    investigation_id=investigation_id,
                    # Already loaded above for this same response - skip the
                    # 4 duplicate SELECTs compute_ragas_summary would otherwise
                    # issue against the same rows.
                    preloaded_investigations=[investigation],
                    preloaded_claims=verification_rows,
                    preloaded_evidence=evidence_rows,
                    preloaded_debates=debate_rows,
                )
            )
        ),
    }


@router.get("/stats/summary", response_model=StatsSummary)
async def investigation_stats(
    db: Session = Depends(get_db_session),
    user=Depends(get_current_user),
):
    """Aggregate statistics powering the dashboard."""
    total = db.query(func.count(Investigation.id)).scalar() or 0
    avg_conf = db.query(func.avg(Investigation.confidence)).scalar() or 0.0

    by_risk: dict[str, int] = {}
    for value, count in (
        db.query(Investigation.risk, func.count(Investigation.id))
        .group_by(Investigation.risk)
        .all()
    ):
        key = value.value if hasattr(value, "value") else str(value)
        by_risk[key] = count

    by_status: dict[str, int] = {}
    for value, count in (
        db.query(Investigation.status, func.count(Investigation.id))
        .group_by(Investigation.status)
        .all()
    ):
        key = value.value if hasattr(value, "value") else str(value)
        by_status[key] = count

    return StatsSummary(
        total=total,
        avg_confidence=round(float(avg_conf), 4),
        by_risk=by_risk,
        by_status=by_status,
        auto_cleared=by_status.get("closed", 0),
        in_review=by_status.get("human_review", 0),
        manual=by_status.get("verification", 0) + by_status.get("agent_debate", 0),
    )


@router.get("/{investigation_id}/debate", response_model=list[DebateMessageOut])
async def get_debate(
    investigation_id: str,
    db: Session = Depends(get_db_session),
    user=Depends(get_current_user),
):
    investigation = db.get(Investigation, investigation_id)
    if not investigation:
        raise HTTPException(status_code=404, detail="Investigation not found")
    rows = (
        db.query(DebateTranscript)
        .filter(DebateTranscript.investigation_id == investigation_id)
        .order_by(DebateTranscript.round.asc(), DebateTranscript.created_at.asc())
        .all()
    )
    return [
        DebateMessageOut(
            id=row.id,
            round=row.round,
            speaker=row.speaker,
            message=row.message,
            token_count=row.token_count or 0,
            confidence=investigation.confidence
            if row.speaker.lower() == "adjudicator"
            else None,
            created_at=row.created_at,
        )
        for row in rows
    ]


@router.get("/{investigation_id}/evidence", response_model=list[EvidenceOut])
async def get_evidence(
    investigation_id: str,
    db: Session = Depends(get_db_session),
    user=Depends(get_current_user),
):
    if not db.get(Investigation, investigation_id):
        raise HTTPException(status_code=404, detail="Investigation not found")
    return (
        db.query(EvidenceArtifact)
        .filter(EvidenceArtifact.investigation_id == investigation_id)
        .order_by(EvidenceArtifact.created_at.asc())
        .all()
    )


@router.get("/{investigation_id}/verification", response_model=list[VerificationOut])
async def get_verification(
    investigation_id: str,
    db: Session = Depends(get_db_session),
    user=Depends(get_current_user),
):
    if not db.get(Investigation, investigation_id):
        raise HTTPException(status_code=404, detail="Investigation not found")
    return (
        db.query(VerificationClaim)
        .filter(VerificationClaim.investigation_id == investigation_id)
        .order_by(VerificationClaim.created_at.asc())
        .all()
    )


@router.get("/{investigation_id}/audit", response_model=list[AuditEventOut])
async def get_audit_trail(
    investigation_id: str,
    limit: int = 200,
    db: Session = Depends(get_db_session),
    user=Depends(get_current_user),
):
    if not db.get(Investigation, investigation_id):
        raise HTTPException(status_code=404, detail="Investigation not found")
    from app.audit.eventstore import get_audit_log

    limit = max(1, min(limit, 500))
    log = await get_audit_log()
    events = await log.get_events(investigation_id, limit=limit)
    return [AuditEventOut(**event) for event in events]


_REPLAY_PHASE_META = {
    "evidence_collection": ("Evidence collection", "evidence_agent"),
    "debate": ("Debate round", "agent_crew"),
    "adjudication": ("Adjudication", "adjudicator"),
    "verification": ("Verification", "verifier"),
    "confidence_gate": ("Confidence gate", "confidence_gate"),
    "report_and_audit": ("Report & audit", "supervisor"),
    "escalation": ("Escalated to human review", "supervisor"),
}


def _replay_io_for(base: str, state_json: dict, checkpoint_hash: str) -> tuple[str, str, str]:
    title, _agent = _REPLAY_PHASE_META.get(
        base,
        (base.replace("_", " ").title(), "supervisor"),
    )
    vendor = state_json.get("vendor", "case")

    if base == "confidence_gate":
        gate = state_json.get("confidence_gate") or {}
        reasons = gate.get("reasons") or []
        decision = str(gate.get("decision") or "unknown").replace("_", " ")
        assigned_to = gate.get("assigned_to")
        queue = gate.get("queue")
        routing = (
            f"Assigned to {assigned_to} in {queue} queue."
            if assigned_to and queue
            else "Cleared for report generation."
        )
        return (
            f"Apply confidence gate for {vendor}",
            (
                f"Risk {gate.get('risk', 'unknown')}; confidence "
                f"{float(gate.get('confidence') or 0):.2f}; third-party status "
                f"{gate.get('third_party_status', 'unknown')}."
            ),
            f"Decision: {decision}. {routing} Reasons: {', '.join(reasons) or 'none'}.",
        )

    if base == "escalation":
        return (
            f"Escalate {vendor} to human review",
            state_json.get("evidence_summary", "") or "",
            "Verifier could not ground the verdict inside the retry budget.",
        )

    return (
        f"{title} phase for {vendor}",
        state_json.get("evidence_summary", "") or "",
        (
            state_json.get("adjudication", {}).get("reasoning", "")
            or (state_json.get("verification_results", {}) or {}).get("verification_report", "")
            or f"Checkpoint hash {checkpoint_hash[:12]}"
        ),
    )


@router.get("/{investigation_id}/replay")
async def get_replay(
    investigation_id: str,
    db: Session = Depends(get_db_session),
    user=Depends(get_current_user),
):
    """Step-by-step replay frames from the investigation's state checkpoints."""
    if not db.get(Investigation, investigation_id):
        raise HTTPException(status_code=404, detail="Investigation not found")
    checkpoints = (
        db.query(DBInvestigationState)
        .filter(DBInvestigationState.investigation_id == investigation_id)
        .order_by(DBInvestigationState.created_at.asc())
        .all()
    )
    frames = []
    for cp in checkpoints:
        # phase is like "evidence_collection_1" / "debate_2"; strip the attempt suffix
        base = cp.phase.rsplit("_", 1)[0] if cp.phase[-1:].isdigit() else cp.phase
        title, agent = _REPLAY_PHASE_META.get(base, (base.replace("_", " ").title(), "supervisor"))
        state_json = cp.state_json or {}
        evidence = state_json.get("evidence", []) or []
        citations = [
            c
            for item in evidence
            if isinstance(item, dict)
            for c in (item.get("citations") or [])
        ]
        prompt, frame_input, output = _replay_io_for(base, state_json, cp.checkpoint_hash)
        is_review_gate = (
            base == "confidence_gate"
            and (state_json.get("confidence_gate") or {}).get("decision") == "human_review"
        )
        frames.append(
            {
                "id": cp.id,
                "title": title,
                "agent": agent,
                "timestamp": cp.created_at.isoformat() if cp.created_at else None,
                "state": (
                    "review" if is_review_gate else "failed" if base == "escalation" else "done"
                ),
                "prompt": prompt,
                "input": frame_input,
                "output": output,
                "citations": citations[:8],
                "token_usage": 0,
                "cost": 0.0,
            }
        )
    return frames


@router.post("/{investigation_id}/execute", response_model=ExecuteResponse)
async def execute_investigation(
    investigation_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db_session),
    user=Depends(get_current_user),
):
    investigation = db.get(Investigation, investigation_id)
    if not investigation:
        raise HTTPException(status_code=404, detail="Investigation not found")
    if not settings.USE_CELERY:
        logger.info(f"Investigation {investigation_id} running inline (USE_CELERY=false)")
        background_tasks.add_task(_run_investigation_inline, investigation_id)
        return ExecuteResponse(
            investigation_id=investigation_id,
            task_id=None,
            status="running",
            message="Investigation running in-process",
        )
    if not await asyncio.to_thread(_celery_broker_available):
        logger.info(f"Investigation {investigation_id} running inline (Celery broker unavailable)")
        background_tasks.add_task(_run_investigation_inline, investigation_id)
        return ExecuteResponse(
            investigation_id=investigation_id,
            task_id=None,
            status="running",
            message="Investigation running in-process (Celery broker unavailable)",
        )
    try:
        from app.tasks.celery_app import execute_investigation_task

        task = execute_investigation_task.delay(investigation_id)
        task_id = str(task.id)
        logger.info(f"Investigation {investigation_id} queued (task {task_id})")
        return ExecuteResponse(
            investigation_id=investigation_id,
            task_id=task_id,
            status="queued",
            message="Investigation execution queued",
        )
    except Exception as e:  # noqa: BLE001
        # No broker/worker available - fall back to running in-process so the
        # platform still works end-to-end (local dev, demos, single-node).
        logger.warning(
            f"Celery broker unavailable for {investigation_id} ({e}); running inline"
        )
        background_tasks.add_task(_run_investigation_inline, investigation_id)
        return ExecuteResponse(
            investigation_id=investigation_id,
            task_id=None,
            status="running",
            message="Investigation running in-process (no task broker configured)",
        )
