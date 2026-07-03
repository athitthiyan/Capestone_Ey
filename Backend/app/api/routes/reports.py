"""Report routes - report artifacts derived from completed investigations."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.models import Investigation, InvestigationStatus, RiskLevel
from app.db.session import get_db_session

router = APIRouter(prefix="/reports", tags=["reports"])

_STATUS_TO_REPORT = {
    InvestigationStatus.REPORT_READY.value: "ready",
    InvestigationStatus.CLOSED.value: "approved",
    InvestigationStatus.HUMAN_REVIEW.value: "draft",
    InvestigationStatus.VERIFICATION.value: "draft",
}


def _status_value(investigation: Investigation) -> str:
    raw = investigation.status
    return raw.value if hasattr(raw, "value") else str(raw)


def _risk_value(investigation: Investigation) -> str:
    raw = investigation.risk
    return (raw.value if hasattr(raw, "value") else str(raw)) if raw else "medium"


def _audience(risk: str) -> str:
    if risk in (RiskLevel.CRITICAL.value, RiskLevel.HIGH.value):
        return "Partner"
    if risk == RiskLevel.MEDIUM.value:
        return "Engagement team"
    return "Audit committee"


REPORTABLE_STATUSES = (
    InvestigationStatus.VERIFICATION,
    InvestigationStatus.HUMAN_REVIEW,
    InvestigationStatus.REPORT_READY,
    InvestigationStatus.CLOSED,
)
REPORTABLE_STATUS_VALUES = {status.value for status in REPORTABLE_STATUSES}


def report_payload(inv: Investigation) -> dict:
    status_value = _status_value(inv)
    risk = _risk_value(inv)
    report_status = _STATUS_TO_REPORT.get(status_value, "draft")
    updated = inv.completed_at or inv.updated_at or inv.created_at
    return {
        "id": f"RPT-{inv.id}",
        "investigation_id": inv.id,
        "title": f"{inv.vendor} - {inv.category} ({inv.transaction_id})",
        "status": report_status,
        "updated_at": updated.isoformat() if updated else None,
        "confidence": round(float(inv.confidence or 0.0), 4),
        "audience": _audience(risk),
        "risk_verdict": risk,
        "sections": [
            "Executive summary",
            "Evidence",
            "Debate transcript",
            "Verification",
            "Decision & audit trail",
        ],
        "executive_summary": (
            inv.description
            or f"{inv.vendor} transaction {inv.transaction_id} for "
            f"{inv.amount:,.2f} was assessed {risk} risk."
        ),
        "human_decision": (
            "Approved and closed"
            if status_value == InvestigationStatus.CLOSED.value
            else "Pending human review"
            if status_value == InvestigationStatus.HUMAN_REVIEW.value
            else "Auto-cleared - reviewer confirmation pending"
        ),
        "reviewer_signature": inv.reviewer or "Unsigned",
    }


@router.get("")
async def list_reports(
    investigation_id: str | None = None,
    limit: int = 100,
    db: Session = Depends(get_db_session),
    user=Depends(get_current_user),
):
    """Report artifacts for investigations that have reached a reportable stage."""
    del user
    limit = max(1, min(limit, 500))
    query = db.query(Investigation).filter(Investigation.status.in_(REPORTABLE_STATUSES))
    if investigation_id:
        query = query.filter(Investigation.id == investigation_id)
    rows = (
        query.order_by(Investigation.updated_at.desc(), Investigation.created_at.desc())
        .limit(limit)
        .all()
    )
    return [report_payload(inv) for inv in rows]
