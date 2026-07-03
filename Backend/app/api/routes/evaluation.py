"""RAGAS evaluation routes.

Exposes the RAGAS metric catalog and a computed evaluation summary for the
/evaluation dashboard. Replaces the former A/B (single-prompt vs. crew) harness.

Per-case scores prefer the real-time LLM-judge results computed by
app/evaluation/ragas_judge.py (persisted to RagasEvaluationResult by the
Celery task in app/tasks/celery_app.py::score_investigation_ragas_task) and
fall back to the telemetry-derived proxy in app/evaluation/ragas.py for any
metric the judge hasn't scored yet.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.models import Investigation, RagasEvaluationResult
from app.db.session import get_db_session
from app.evaluation.ragas import compute_ragas_summary, metric_catalog
from app.schemas import EvaluationSummaryOut, LlmMetricBreakdownOut, RagasMetricOut

router = APIRouter(prefix="/evaluation", tags=["evaluation"])


def _overlay_real_scores(summary: dict, real_rows: dict[str, RagasEvaluationResult]) -> dict:
    """Replace proxy metric scores with real LLM-judge scores where available.

    A metric stays on the telemetry proxy (source="proxy") until the judge has
    produced a real score for it (source="real"); judge failures/timeouts
    (score is null) also fall back to the proxy rather than showing a blank
    or zero score on the dashboard.
    """
    for row in summary.get("metrics", []):
        real = real_rows.get(row["metric"])
        if real is not None and real.score is not None:
            row["score"] = round(real.score, 4)
            row["pass"] = real.score >= row["target"]
            row["source"] = "real"
            row["scored_provider"] = real.scored_provider
            row["scored_model"] = real.scored_model
            row["judge_model"] = real.judge_model
        else:
            row["source"] = "proxy"
    return summary


@router.get("/summary", response_model=EvaluationSummaryOut)
async def evaluation_summary(
    db: Session = Depends(get_db_session),
    user=Depends(get_current_user),
):
    """RAGAS scores derived from stored investigation telemetry (aggregate
    proxy across every case; per-case real judge scores are available via
    /evaluation/case/{id}, and per-provider comparisons via /evaluation/by-llm).
    """
    del user
    return compute_ragas_summary(db)


@router.get("/case/{investigation_id}", response_model=EvaluationSummaryOut)
async def evaluation_for_case(
    investigation_id: str,
    db: Session = Depends(get_db_session),
    user=Depends(get_current_user),
):
    """RAGAS scores scoped to a single investigation.

    Metrics the real-time LLM judge has scored take precedence over the
    telemetry proxy; see module docstring.
    """
    del user
    exists = db.query(Investigation.id).filter(Investigation.id == investigation_id).first()
    if not exists:
        raise HTTPException(status_code=404, detail="Investigation not found")
    summary = compute_ragas_summary(db, investigation_id=investigation_id)
    real_rows = {
        row.metric: row
        for row in db.query(RagasEvaluationResult)
        .filter(RagasEvaluationResult.investigation_id == investigation_id)
        .all()
    }
    return _overlay_real_scores(summary, real_rows)


@router.get("/metrics", response_model=list[RagasMetricOut])
async def evaluation_metrics(
    user=Depends(get_current_user),
):
    """The canonical RAGAS metric catalog (definitions + targets)."""
    del user
    return metric_catalog()


@router.get("/by-llm", response_model=list[LlmMetricBreakdownOut])
async def evaluation_by_llm(
    db: Session = Depends(get_db_session),
    user=Depends(get_current_user),
):
    """Mean real (LLM-judge) RAGAS score per metric, broken down by which
    provider/model produced the judged response.

    Answers "which LLM scores best on which metric" across every case the
    real-time judge has scored so far. Only real scores are included (no
    proxy fallback here - mixing proxy telemetry into a per-LLM comparison
    would make providers with more/less telemetry look artificially
    better/worse rather than reflecting actual judged quality).
    """
    del user
    rows = (
        db.query(RagasEvaluationResult)
        .filter(RagasEvaluationResult.score.isnot(None))
        .filter(RagasEvaluationResult.scored_provider.isnot(None))
        .all()
    )
    buckets: dict[tuple[str, str, str], list[float]] = {}
    for row in rows:
        key = (row.scored_provider, row.scored_model, row.metric)
        buckets.setdefault(key, []).append(row.score)

    breakdown = [
        LlmMetricBreakdownOut(
            provider=provider,
            model=model,
            metric=metric,
            mean_score=round(sum(scores) / len(scores), 4),
            cases_scored=len(scores),
        )
        for (provider, model, metric), scores in buckets.items()
    ]
    breakdown.sort(key=lambda item: (item.metric, -item.mean_score))
    return breakdown
