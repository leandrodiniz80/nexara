import logging
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_session
from app.api.dependencies.common import get_db, get_request_id
from app.api.responses.api_response import ApiResponse
from app.core.config import settings
from app.models.leads.lead import Lead
from app.models.leads.lead_status_history import LeadStatusHistory
from app.schemas.leads.lead import (
    LeadCreate,
    LeadCreateResponse,
    LeadMetricsByStatus,
    LeadMetricsResponse,
    LeadResponse,
    LeadStatusUpdateResponse,
    LeadUpdateStatus,
)
from app.services.leads.automation_engine import run_automations

logger = logging.getLogger("app.api.routers.leads")

router = APIRouter(prefix=f"{settings.API_V1_PREFIX}/leads", tags=["Leads"])


def _require_organization(session: dict) -> str:
    """Every route below needs a real tenant to scope its query to — a user
    with no organization (shouldn't normally happen; register_user() always
    creates one) gets a friendly 403 instead of every lead in the database."""
    organization_id = session.get("organization_id")
    if organization_id is None:
        raise HTTPException(status_code=403, detail="Your account isn't part of an organization")
    return organization_id


@router.get("", response_model=ApiResponse[list[LeadResponse]])
async def list_leads(
    request_id: str = Depends(get_request_id),
    session: dict = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[list[LeadResponse]]:
    start = time.perf_counter()
    organization_id = _require_organization(session)

    stmt = (
        select(Lead)
        .where(Lead.organization_id == organization_id, Lead.deleted_at.is_(None))
        .order_by(Lead.created_at.desc())
    )
    result = await db.execute(stmt)
    leads = result.scalars().all()

    return ApiResponse(
        success=True,
        data=[LeadResponse.model_validate(lead) for lead in leads],
        request_id=request_id,
        execution_time=time.perf_counter() - start,
    )


@router.get("/metrics", response_model=ApiResponse[LeadMetricsResponse])
async def get_lead_metrics(
    request_id: str = Depends(get_request_id),
    session: dict = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[LeadMetricsResponse]:
    start = time.perf_counter()
    organization_id = _require_organization(session)

    # Two small aggregate queries (COUNT/AVG, one GROUP BY) — no Python loop
    # over lead rows either way.
    status_stmt = (
        select(Lead.status, func.count(Lead.id))
        .where(Lead.organization_id == organization_id, Lead.deleted_at.is_(None))
        .group_by(Lead.status)
    )
    status_counts = dict((await db.execute(status_stmt)).all())

    totals_stmt = select(func.count(Lead.id), func.avg(Lead.score)).where(
        Lead.organization_id == organization_id, Lead.deleted_at.is_(None)
    )
    total, avg_score = (await db.execute(totals_stmt)).one()

    by_status = LeadMetricsByStatus(
        new=status_counts.get("new", 0),
        contacted=status_counts.get("contacted", 0),
        converted=status_counts.get("converted", 0),
    )
    conversion_rate = round(by_status.converted / total * 100, 1) if total else 0.0

    return ApiResponse(
        success=True,
        data=LeadMetricsResponse(
            total=total,
            by_status=by_status,
            conversion_rate=conversion_rate,
            avg_score=round(float(avg_score), 1) if avg_score is not None else 0.0,
        ),
        request_id=request_id,
        execution_time=time.perf_counter() - start,
    )


@router.post("", response_model=ApiResponse[LeadCreateResponse])
async def create_lead(
    body: LeadCreate,
    request_id: str = Depends(get_request_id),
    session: dict = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[LeadCreateResponse]:
    start = time.perf_counter()
    organization_id = _require_organization(session)

    lead = Lead(
        organization_id=organization_id,
        name=body.name,
        email=body.email,
        phone=body.phone,
        status="new",
        # Matches the frontend's own prior default for a freshly created,
        # not-yet-qualified lead (see git history of lib/mocks/leads.ts) —
        # now the single source of truth instead of duplicated client-side.
        score=20,
    )
    db.add(lead)

    # lead.id is already set (AuditMixin generates it client-side via
    # uuid.uuid4()), so run_automations() can read it before the commit
    # below — same single-commit shape as update_lead_status.
    notifications = await run_automations(db, {"type": "lead_created", "lead": lead})

    await db.commit()
    await db.refresh(lead)

    logger.info("Lead created: %s (org=%s)", lead.id, organization_id)

    return ApiResponse(
        success=True,
        data=LeadCreateResponse(
            lead=LeadResponse.model_validate(lead), notifications=notifications
        ),
        request_id=request_id,
        execution_time=time.perf_counter() - start,
    )


@router.patch("/{lead_id}/status", response_model=ApiResponse[LeadStatusUpdateResponse])
async def update_lead_status(
    lead_id: uuid.UUID,
    body: LeadUpdateStatus,
    request_id: str = Depends(get_request_id),
    session: dict = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[LeadStatusUpdateResponse]:
    start = time.perf_counter()
    organization_id = _require_organization(session)

    lead = await db.get(Lead, lead_id)
    if lead is None or lead.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Lead not found")

    from_status = lead.status
    lead.status = body.status

    # run_automations() only reads (LeadAutomation table) before this
    # single commit — no separate write, so the lead's status change and
    # whatever the automation match observed land atomically together.
    notifications: list[str] = []
    if from_status != lead.status:
        notifications = await run_automations(
            db,
            {
                "type": "lead_status_changed",
                "lead": lead,
                "fromStatus": from_status,
                "toStatus": lead.status,
            },
        )
        db.add(
            LeadStatusHistory(
                lead_id=lead.id,
                organization_id=organization_id,
                from_status=from_status,
                to_status=lead.status,
            )
        )

    await db.commit()
    await db.refresh(lead)

    logger.info(
        "Lead status changed: %s %s -> %s (org=%s)",
        lead.id,
        from_status,
        lead.status,
        organization_id,
    )

    return ApiResponse(
        success=True,
        data=LeadStatusUpdateResponse(
            lead=LeadResponse.model_validate(lead), notifications=notifications
        ),
        request_id=request_id,
        execution_time=time.perf_counter() - start,
    )
