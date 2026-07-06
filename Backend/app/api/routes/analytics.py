"""Analytics routes - aggregates derived from investigation and request telemetry."""

from collections import Counter, defaultdict
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.models import (
    Investigation,
    InvestigationStatus,
    LLMCallLog,
    RequestLog,
    VerificationClaim,
)
from app.db.session import get_db_session

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _week_label(value: datetime | None) -> str:
    dt = value or datetime.utcnow()
    iso = dt.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def _ratio(n: float, d: float) -> float:
    return float(n) / float(d) if d else 0.0


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * percentile)))
    return float(ordered[index])


def _llm_query(
    db: Session,
    *,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    provider: str | None = None,
    model: str | None = None,
    request_type: str | None = None,
):
    query = db.query(LLMCallLog)
    if date_from:
        query = query.filter(LLMCallLog.created_at >= date_from)
    if date_to:
        query = query.filter(LLMCallLog.created_at <= date_to)
    if provider:
        query = query.filter(LLMCallLog.provider_name == provider)
    if model:
        query = query.filter(LLMCallLog.model_name == model)
    if request_type:
        query = query.filter(LLMCallLog.request_type == request_type)
    return query


def _llm_rows(
    db: Session,
    *,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    provider: str | None = None,
    model: str | None = None,
    request_type: str | None = None,
    limit: int | None = None,
) -> list[LLMCallLog]:
    query = _llm_query(
        db,
        date_from=date_from,
        date_to=date_to,
        provider=provider,
        model=model,
        request_type=request_type,
    ).order_by(LLMCallLog.created_at.desc())
    query = query.limit(max(1, min(limit or 5000, 5000)))
    return query.all()


def _count_if(condition):
    return func.coalesce(func.sum(case((condition, 1), else_=0)), 0)


def _sum(query, column, default=0):
    return query.with_entities(func.coalesce(func.sum(column), default)).scalar() or default


def _llm_summary_from_query(query) -> dict:
    total_tokens = _sum(query, LLMCallLog.total_tokens)
    prompt_tokens = _sum(query, LLMCallLog.prompt_tokens)
    completion_tokens = _sum(query, LLMCallLog.completion_tokens)
    total_cost = _sum(query, LLMCallLog.estimated_cost_usd, 0.0)
    actual_cost = query.with_entities(func.sum(LLMCallLog.actual_cost_usd)).scalar()
    successful = query.with_entities(_count_if(LLMCallLog.success.is_(True))).scalar() or 0
    failed = query.with_entities(_count_if(LLMCallLog.success.is_(False))).scalar() or 0
    fallback_calls = (
        query.with_entities(_count_if(LLMCallLog.fallback_used.is_(True))).scalar() or 0
    )
    cache_hits = query.with_entities(_count_if(LLMCallLog.cache_hit.is_(True))).scalar() or 0
    average_latency = (
        query.filter(LLMCallLog.cache_hit.is_(False))
        .with_entities(func.avg(LLMCallLog.latency_ms))
        .scalar()
        or 0.0
    )
    expensive_rows = (
        query.with_entities(
            LLMCallLog.request_type,
            func.coalesce(func.sum(LLMCallLog.estimated_cost_usd), 0.0).label("cost"),
        )
        .group_by(LLMCallLog.request_type)
        .order_by(func.sum(LLMCallLog.estimated_cost_usd).desc())
        .limit(8)
        .all()
    )
    return {
        "total_tokens": int(total_tokens or 0),
        "prompt_tokens": int(prompt_tokens or 0),
        "completion_tokens": int(completion_tokens or 0),
        "total_estimated_cost_usd": round(float(total_cost or 0.0), 6),
        "total_actual_cost_usd": round(float(actual_cost), 6) if actual_cost is not None else None,
        "successful_calls": int(successful or 0),
        "failed_calls": int(failed or 0),
        "fallback_calls": int(fallback_calls or 0),
        "cache_hits": int(cache_hits or 0),
        "average_latency_ms": round(float(average_latency or 0.0), 2),
        "most_expensive_request_types": [
            {"request_type": key, "estimated_cost_usd": round(float(value or 0.0), 6)}
            for key, value in expensive_rows
        ],
    }


def _llm_summary(rows: list[LLMCallLog]) -> dict:
    durations = [float(row.latency_ms or 0.0) for row in rows if not row.cache_hit]
    successful = sum(1 for row in rows if row.success)
    failed = sum(1 for row in rows if not row.success)
    fallback_calls = sum(1 for row in rows if row.fallback_used)
    total_cost = sum(float(row.estimated_cost_usd or 0.0) for row in rows)
    actual_costs = [float(row.actual_cost_usd) for row in rows if row.actual_cost_usd is not None]
    expensive_by_type: dict[str, float] = defaultdict(float)
    for row in rows:
        expensive_by_type[row.request_type] += float(row.estimated_cost_usd or 0.0)
    return {
        "total_tokens": sum(int(row.total_tokens or 0) for row in rows),
        "prompt_tokens": sum(int(row.prompt_tokens or 0) for row in rows),
        "completion_tokens": sum(int(row.completion_tokens or 0) for row in rows),
        "total_estimated_cost_usd": round(total_cost, 6),
        "total_actual_cost_usd": round(sum(actual_costs), 6) if actual_costs else None,
        "successful_calls": successful,
        "failed_calls": failed,
        "fallback_calls": fallback_calls,
        "cache_hits": sum(1 for row in rows if row.cache_hit),
        "average_latency_ms": round(_ratio(sum(durations), len(durations)), 2),
        "most_expensive_request_types": [
            {"request_type": key, "estimated_cost_usd": round(value, 6)}
            for key, value in sorted(
                expensive_by_type.items(),
                key=lambda item: item[1],
                reverse=True,
            )[:8]
        ],
    }


def _aggregate_llm(rows: list[LLMCallLog], key: str) -> list[dict]:
    grouped: dict[str, list[LLMCallLog]] = defaultdict(list)
    for row in rows:
        grouped[str(getattr(row, key) or "unknown")].append(row)
    return [
        {
            key: group_key,
            **_llm_summary(group_rows),
            "calls": len(group_rows),
        }
        for group_key, group_rows in sorted(grouped.items())
    ]


def _aggregate_llm_from_query(query, key: str) -> list[dict]:
    column = getattr(LLMCallLog, key)
    rows = (
        query.with_entities(
            column.label("group_key"),
            func.count(LLMCallLog.id).label("calls"),
            func.coalesce(func.sum(LLMCallLog.total_tokens), 0).label("total_tokens"),
            func.coalesce(func.sum(LLMCallLog.prompt_tokens), 0).label("prompt_tokens"),
            func.coalesce(func.sum(LLMCallLog.completion_tokens), 0).label("completion_tokens"),
            func.coalesce(func.sum(LLMCallLog.estimated_cost_usd), 0.0).label("estimated_cost"),
            func.sum(LLMCallLog.actual_cost_usd).label("actual_cost"),
            _count_if(LLMCallLog.success.is_(True)).label("successful"),
            _count_if(LLMCallLog.success.is_(False)).label("failed"),
            _count_if(LLMCallLog.fallback_used.is_(True)).label("fallback_calls"),
            _count_if(LLMCallLog.cache_hit.is_(True)).label("cache_hits"),
            func.avg(
                case((LLMCallLog.cache_hit.is_(False), LLMCallLog.latency_ms), else_=None)
            ).label("average_latency"),
        )
        .group_by(column)
        .order_by(column.asc())
        .all()
    )
    return [
        {
            key: group_key or "unknown",
            "total_tokens": int(total_tokens or 0),
            "prompt_tokens": int(prompt_tokens or 0),
            "completion_tokens": int(completion_tokens or 0),
            "total_estimated_cost_usd": round(float(estimated_cost or 0.0), 6),
            "total_actual_cost_usd": round(float(actual_cost), 6)
            if actual_cost is not None
            else None,
            "successful_calls": int(successful or 0),
            "failed_calls": int(failed or 0),
            "fallback_calls": int(fallback_calls or 0),
            "cache_hits": int(cache_hits or 0),
            "average_latency_ms": round(float(average_latency or 0.0), 2),
            "most_expensive_request_types": [],
            "calls": int(calls or 0),
        }
        for (
            group_key,
            calls,
            total_tokens,
            prompt_tokens,
            completion_tokens,
            estimated_cost,
            actual_cost,
            successful,
            failed,
            fallback_calls,
            cache_hits,
            average_latency,
        ) in rows
    ]


def _llm_call_payload(row: LLMCallLog) -> dict:
    return {
        "id": row.id,
        "provider_name": row.provider_name,
        "model_name": row.model_name,
        "request_type": row.request_type,
        "prompt_tokens": row.prompt_tokens or 0,
        "completion_tokens": row.completion_tokens or 0,
        "total_tokens": row.total_tokens or 0,
        "estimated_cost_usd": row.estimated_cost_usd or 0.0,
        "actual_cost_usd": row.actual_cost_usd,
        "latency_ms": row.latency_ms or 0.0,
        "success": bool(row.success),
        "error_message": row.error_message,
        "fallback_used": bool(row.fallback_used),
        "fallback_provider": row.fallback_provider,
        "cache_hit": bool(row.cache_hit),
        "model_tier": row.model_tier,
        "routing_reason": row.routing_reason,
        "quality_guardrail": row.quality_guardrail,
        "user_id": row.user_id,
        "session_id": row.session_id,
        "request_id": row.request_id,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


@router.get("/trend")
async def analytics_trend(
    limit: int = Query(5000, ge=1, le=20000),
    db: Session = Depends(get_db_session),
    user=Depends(get_current_user),
):
    """Weekly confidence + verifier-grounding trend (last 26 weeks)."""
    del user
    since = datetime.utcnow() - timedelta(weeks=26)
    investigations = (
        db.query(Investigation.created_at, Investigation.confidence)
        .filter(Investigation.created_at >= since)
        .order_by(Investigation.created_at.desc())
        .limit(limit)
        .all()
    )
    claims = (
        db.query(VerificationClaim.created_at, VerificationClaim.is_grounded)
        .filter(VerificationClaim.created_at >= since)
        .order_by(VerificationClaim.created_at.desc())
        .limit(limit)
        .all()
    )
    if not investigations:
        return []

    conf_by_week: dict[str, list[float]] = defaultdict(list)
    for created_at, confidence in investigations:
        conf_by_week[_week_label(created_at)].append(float(confidence or 0.0))

    claims_by_week: dict[str, list[bool]] = defaultdict(list)
    for created_at, is_grounded in claims:
        claims_by_week[_week_label(created_at)].append(bool(is_grounded))

    weeks = sorted(set(conf_by_week) | set(claims_by_week))
    points = []
    for week in weeks:
        confs = conf_by_week.get(week, [])
        grounded = claims_by_week.get(week, [])
        points.append(
            {
                "week": week,
                "confidence": round(_ratio(sum(confs), len(confs)), 4),
                "verifier_rate": round(_ratio(sum(1 for g in grounded if g), len(grounded)), 4)
                if grounded
                else 0.0,
            }
        )
    return points


@router.get("/agent-accuracy")
async def agent_accuracy(
    db: Session = Depends(get_db_session),
    user=Depends(get_current_user),
):
    """Per-agent accuracy proxies derived from run telemetry."""
    total = db.query(func.count(Investigation.id)).scalar() or 0
    if not total:
        return []

    mean_conf = float(db.query(func.avg(Investigation.confidence)).scalar() or 0.0)
    claims_total = db.query(func.count(VerificationClaim.id)).scalar() or 0
    grounded = (
        db.query(func.count(VerificationClaim.id))
        .filter(VerificationClaim.is_grounded.is_(True))
        .scalar()
        or 0
    )
    grounded_rate = _ratio(grounded, claims_total)
    completed = (
        db.query(func.count(Investigation.id))
        .filter(
            Investigation.status.in_(
                (InvestigationStatus.REPORT_READY, InvestigationStatus.CLOSED)
            )
        )
        .scalar()
        or 0
    )
    goal_rate = _ratio(completed, total)

    return [
        {"agent": "Evidence", "accuracy": round(min(1.0, mean_conf + 0.05), 4)},
        {"agent": "Challenger", "accuracy": round(mean_conf, 4)},
        {"agent": "Defender", "accuracy": round(mean_conf, 4)},
        {"agent": "Adjudicator", "accuracy": round(mean_conf, 4)},
        {"agent": "Verifier", "accuracy": round(grounded_rate, 4)},
        {"agent": "Supervisor", "accuracy": round(goal_rate, 4)},
    ]


@router.get("/kpis")
async def analytics_kpis(
    db: Session = Depends(get_db_session),
    user=Depends(get_current_user),
):
    """Headline analytics KPI cards."""
    total = db.query(func.count(Investigation.id)).scalar() or 0
    if total == 0:
        return []

    mean_conf = float(db.query(func.avg(Investigation.confidence)).scalar() or 0.0)
    claims_total = db.query(func.count(VerificationClaim.id)).scalar() or 0
    grounded = (
        db.query(func.count(VerificationClaim.id))
        .filter(VerificationClaim.is_grounded.is_(True))
        .scalar()
        or 0
    )
    grounded_rate = _ratio(grounded, claims_total)
    in_review = (
        db.query(func.count(Investigation.id))
        .filter(Investigation.status == InvestigationStatus.HUMAN_REVIEW)
        .scalar()
        or 0
    )
    closed = (
        db.query(func.count(Investigation.id))
        .filter(
            Investigation.status.in_(
                (InvestigationStatus.REPORT_READY, InvestigationStatus.CLOSED)
            )
        )
        .scalar()
        or 0
    )

    return [
        {
            "label": "Cases analysed",
            "value": str(total),
            "helper": f"{closed} completed",
            "tone": "default",
        },
        {
            "label": "Avg confidence",
            "value": f"{mean_conf * 100:.0f}%",
            "helper": "across all verdicts",
            "tone": "success" if mean_conf >= 0.8 else "warning",
        },
        {
            "label": "Grounding rate",
            "value": f"{grounded_rate * 100:.0f}%",
            "helper": "verifier-passed claims",
            "tone": "success" if grounded_rate >= 0.9 else "warning",
        },
        {
            "label": "In human review",
            "value": str(in_review),
            "helper": "awaiting reviewer action",
            "tone": "warning" if in_review else "success",
        },
    ]


@router.get("/requests")
async def request_analytics(
    limit: int = 200,
    db: Session = Depends(get_db_session),
    user=Depends(get_current_user),
):
    """Request logging analytics for production operations."""
    del user
    limit = max(1, min(limit, 1000))
    rows = (
        db.query(RequestLog)
        .order_by(RequestLog.created_at.desc())
        .limit(limit)
        .all()
    )
    if not rows:
        return {
            "total_requests": 0,
            "error_rate": 0.0,
            "avg_duration_ms": 0.0,
            "p95_duration_ms": 0.0,
            "by_status": {},
            "top_paths": [],
            "recent": [],
        }

    durations = [float(row.duration_ms or 0) for row in rows]
    status_counts = Counter(str(row.status_code) for row in rows)
    path_counts = Counter(row.path for row in rows)
    errors = sum(1 for row in rows if int(row.status_code or 0) >= 500)

    return {
        "total_requests": len(rows),
        "error_rate": round(_ratio(errors, len(rows)), 4),
        "avg_duration_ms": round(_ratio(sum(durations), len(durations)), 2),
        "p95_duration_ms": round(_percentile(durations, 0.95), 2),
        "by_status": dict(sorted(status_counts.items())),
        "top_paths": [
            {"path": path, "count": count}
            for path, count in path_counts.most_common(8)
        ],
        "recent": [
            {
                "request_id": row.request_id,
                "method": row.method,
                "path": row.path,
                "status_code": row.status_code,
                "duration_ms": row.duration_ms,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows[:20]
        ],
    }


@router.get("/llm/summary")
async def llm_summary(
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    provider: str | None = None,
    model: str | None = None,
    request_type: str | None = None,
    db: Session = Depends(get_db_session),
    user=Depends(get_current_user),
):
    """LLM token, cost, fallback, and latency totals."""
    del user
    query = _llm_query(
        db,
        date_from=date_from,
        date_to=date_to,
        provider=provider,
        model=model,
        request_type=request_type,
    )
    return _llm_summary_from_query(query)


@router.get("/llm/by-provider")
async def llm_by_provider(
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    request_type: str | None = None,
    db: Session = Depends(get_db_session),
    user=Depends(get_current_user),
):
    """LLM usage and cost grouped by provider."""
    del user
    query = _llm_query(db, date_from=date_from, date_to=date_to, request_type=request_type)
    return _aggregate_llm_from_query(query, "provider_name")


@router.get("/llm/by-model")
async def llm_by_model(
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    provider: str | None = None,
    request_type: str | None = None,
    db: Session = Depends(get_db_session),
    user=Depends(get_current_user),
):
    """LLM usage and cost grouped by model."""
    del user
    query = _llm_query(
        db,
        date_from=date_from,
        date_to=date_to,
        provider=provider,
        request_type=request_type,
    )
    return _aggregate_llm_from_query(query, "model_name")


@router.get("/llm/recent-calls")
async def llm_recent_calls(
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    provider: str | None = None,
    model: str | None = None,
    request_type: str | None = None,
    limit: int = 50,
    db: Session = Depends(get_db_session),
    user=Depends(get_current_user),
):
    """Recent LLM calls with routing, fallback, and cost metadata."""
    del user
    rows = _llm_rows(
        db,
        date_from=date_from,
        date_to=date_to,
        provider=provider,
        model=model,
        request_type=request_type,
        limit=limit,
    )
    return [_llm_call_payload(row) for row in rows]


@router.get("/llm/cost-trends")
async def llm_cost_trends(
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    provider: str | None = None,
    model: str | None = None,
    request_type: str | None = None,
    grain: str = "daily",
    db: Session = Depends(get_db_session),
    user=Depends(get_current_user),
):
    """LLM cost and token trends, grouped daily, weekly, or monthly."""
    del user
    rows = _llm_rows(
        db,
        date_from=date_from,
        date_to=date_to,
        provider=provider,
        model=model,
        request_type=request_type,
        limit=5000,
    )
    grouped: dict[str, list[LLMCallLog]] = defaultdict(list)
    for row in rows:
        created = row.created_at or datetime.utcnow()
        if grain == "monthly":
            label = created.strftime("%Y-%m")
        elif grain == "weekly":
            label = _week_label(created)
        else:
            label = created.strftime("%Y-%m-%d")
        grouped[label].append(row)

    return [
        {
            "period": period,
            "calls": len(period_rows),
            "total_tokens": sum(int(row.total_tokens or 0) for row in period_rows),
            "estimated_cost_usd": round(
                sum(float(row.estimated_cost_usd or 0.0) for row in period_rows),
                6,
            ),
            "fallback_calls": sum(1 for row in period_rows if row.fallback_used),
            "average_latency_ms": round(
                _ratio(
                    sum(float(row.latency_ms or 0.0) for row in period_rows),
                    len(period_rows),
                ),
                2,
            ),
        }
        for period, period_rows in sorted(grouped.items())
    ]
