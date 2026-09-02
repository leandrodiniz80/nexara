import logging
import time
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_session
from app.api.dependencies.common import get_db, get_request_id
from app.api.responses.api_response import ApiResponse
from app.core.config import settings
from app.models.leads.lead import Lead
from app.models.leads.lead_status_history import LeadStatusHistory
from app.models.platform_auth.user import PlatformUser
from app.models.platform_auth.user_organization import PlatformUserOrganization
from app.schemas.leads.lead import (
    LeadCreate,
    LeadCreateResponse,
    LeadListResponse,
    LeadMetricsByStatus,
    LeadMetricsResponse,
    LeadResponse,
    LeadStatusUpdateResponse,
    LeadTimelineEntry,
    LeadUpdateStatus,
    UpdateLeadDetailsRequest,
    UpdateLeadOwnerRequest,
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


@router.get("", response_model=ApiResponse[list[LeadResponse] | LeadListResponse])
async def list_leads(
    # Optional, generous defaults — every existing caller (no query params
    # at all) gets exactly the same full list as before at today's data
    # volumes. limit/offset alone only bound the query; with_meta=true is
    # what opts into the {data, total, limit, offset, has_more} shape below
    # — default response stays the bare array, byte-for-byte as before.
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    with_meta: bool = Query(default=False),
    request_id: str = Depends(get_request_id),
    session: dict = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[list[LeadResponse] | LeadListResponse]:
    start = time.perf_counter()
    organization_id = _require_organization(session)

    stmt = (
        select(Lead)
        .where(Lead.organization_id == organization_id, Lead.deleted_at.is_(None))
        .order_by(Lead.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    leads = [LeadResponse.model_validate(lead) for lead in result.scalars().all()]

    if not with_meta:
        return ApiResponse(
            success=True,
            data=leads,
            request_id=request_id,
            execution_time=time.perf_counter() - start,
        )

    # Same WHERE as the query above (organization_id + deleted_at IS NULL),
    # so it uses the leading column of ix_leads_org_id_created_at too — a
    # plain COUNT doesn't need the created_at part of that index at all.
    # Only runs when a caller actually asked for metadata.
    total_stmt = select(func.count(Lead.id)).where(
        Lead.organization_id == organization_id, Lead.deleted_at.is_(None)
    )
    total = (await db.execute(total_stmt)).scalar_one()

    return ApiResponse(
        success=True,
        data=LeadListResponse(
            data=leads,
            total=total,
            limit=limit,
            offset=offset,
            has_more=offset + len(leads) < total,
        ),
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

    # Single round trip: one COUNT(*) FILTER (WHERE ...) per status bucket
    # plus the overall COUNT/AVG, all in one aggregate query — was two
    # separate queries (a GROUP BY + a totals query) before. Still zero
    # Python-side looping over lead rows either way; this only cuts the
    # number of DB round trips per call.
    stmt = select(
        func.count(Lead.id),
        func.count(Lead.id).filter(Lead.status == "new"),
        func.count(Lead.id).filter(Lead.status == "contacted"),
        func.count(Lead.id).filter(Lead.status == "converted"),
        func.avg(Lead.score),
    ).where(Lead.organization_id == organization_id, Lead.deleted_at.is_(None))

    total, new_count, contacted_count, converted_count, avg_score = (
        await db.execute(stmt)
    ).one()

    by_status = LeadMetricsByStatus(
        new=new_count, contacted=contacted_count, converted=converted_count
    )
    conversion_rate = round(converted_count / total * 100, 1) if total else 0.0

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


@router.get("/attention", response_model=ApiResponse[list[LeadResponse]])
async def get_leads_needing_attention(
    stale_after_days: int = Query(default=3, ge=1, le=90),
    limit: int = Query(default=20, ge=1, le=100),
    request_id: str = Depends(get_request_id),
    session: dict = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[list[LeadResponse]]:
    """Leads still in the active pipeline (not yet converted) that haven't
    had a status change — or any other edit, since updated_at bumps on any
    column write — in at least stale_after_days. Ordered oldest-touched
    first, so the most neglected lead surfaces at the top."""
    start = time.perf_counter()
    organization_id = _require_organization(session)

    cutoff = datetime.now(timezone.utc) - timedelta(days=stale_after_days)
    stmt = (
        select(Lead)
        .where(
            Lead.organization_id == organization_id,
            Lead.deleted_at.is_(None),
            Lead.status.in_(["new", "contacted"]),
            Lead.updated_at < cutoff,
        )
        .order_by(Lead.updated_at.asc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    leads = [LeadResponse.model_validate(lead) for lead in result.scalars().all()]

    return ApiResponse(
        success=True,
        data=leads,
        request_id=request_id,
        execution_time=time.perf_counter() - start,
    )


@router.get("/tasks", response_model=ApiResponse[list[LeadResponse]])
async def get_lead_tasks(
    limit: int = Query(default=50, ge=1, le=200),
    request_id: str = Depends(get_request_id),
    session: dict = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[list[LeadResponse]]:
    """Leads with a next_action set, soonest due first — backs the
    dashboard's Upcoming Tasks card."""
    start = time.perf_counter()
    organization_id = _require_organization(session)

    stmt = (
        select(Lead)
        .where(
            Lead.organization_id == organization_id,
            Lead.deleted_at.is_(None),
            Lead.next_action_due_at.isnot(None),
        )
        .order_by(Lead.next_action_due_at.asc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    leads = [LeadResponse.model_validate(lead) for lead in result.scalars().all()]

    return ApiResponse(
        success=True,
        data=leads,
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


@router.get("/{lead_id}/timeline", response_model=ApiResponse[list[LeadTimelineEntry]])
async def get_lead_timeline(
    lead_id: uuid.UUID,
    limit: int = Query(default=50, ge=1, le=200),
    request_id: str = Depends(get_request_id),
    session: dict = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[list[LeadTimelineEntry]]:
    start = time.perf_counter()
    organization_id = _require_organization(session)

    # Same ownership check as update_lead_status — a guessed lead_id from
    # another org 404s instead of returning an empty (ambiguous) timeline.
    lead = await db.get(Lead, lead_id)
    if lead is None or lead.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Lead not found")

    stmt = (
        select(LeadStatusHistory)
        .where(LeadStatusHistory.lead_id == lead_id, LeadStatusHistory.organization_id == organization_id)
        .order_by(LeadStatusHistory.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    history = result.scalars().all()

    return ApiResponse(
        success=True,
        data=[
            LeadTimelineEntry(
                type="status_changed",
                from_=entry.from_status,
                to=entry.to_status,
                created_at=entry.created_at,
            )
            for entry in history
        ],
        request_id=request_id,
        execution_time=time.perf_counter() - start,
    )


@router.patch("/{lead_id}/details", response_model=ApiResponse[LeadResponse])
async def update_lead_details(
    lead_id: uuid.UUID,
    body: UpdateLeadDetailsRequest,
    request_id: str = Depends(get_request_id),
    session: dict = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[LeadResponse]:
    """Partial update for notes/next_action/next_action_due_at — only fields
    actually present in the request body are touched (exclude_unset), so the
    frontend can autosave one field on blur without clobbering the others."""
    start = time.perf_counter()
    organization_id = _require_organization(session)

    lead = await db.get(Lead, lead_id)
    if lead is None or lead.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Lead not found")

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(lead, field, value)

    await db.commit()
    await db.refresh(lead)

    return ApiResponse(
        success=True,
        data=LeadResponse.model_validate(lead),
        request_id=request_id,
        execution_time=time.perf_counter() - start,
    )


@router.patch("/{lead_id}/owner", response_model=ApiResponse[LeadResponse])
async def update_lead_owner(
    lead_id: uuid.UUID,
    body: UpdateLeadOwnerRequest,
    request_id: str = Depends(get_request_id),
    session: dict = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[LeadResponse]:
    """owner_email references platform_users.email (this codebase's real
    user identity — there is no users.id UUID table). A non-null value must
    both exist in platform_users and belong to the lead's organization
    (checked against PlatformUser.organization_id — a user's primary org —
    OR a PlatformUserOrganization row, since a user can belong to more than
    one org); owner_email=null always succeeds (unassign, no user to
    validate). updated_at bumps automatically via AuditMixin's onupdate."""
    start = time.perf_counter()
    organization_id = _require_organization(session)

    lead = await db.get(Lead, lead_id)
    if lead is None or lead.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Lead not found")

    if body.owner_email is not None:
        owner = await db.get(PlatformUser, body.owner_email)
        if owner is None:
            raise HTTPException(status_code=400, detail="No such user")

        is_member = owner.organization_id == organization_id
        if not is_member:
            membership = await db.get(
                PlatformUserOrganization, (body.owner_email, organization_id)
            )
            is_member = membership is not None

        if not is_member:
            raise HTTPException(
                status_code=400, detail="User does not belong to this organization"
            )

    lead.owner_email = body.owner_email
    await db.commit()
    await db.refresh(lead)

    return ApiResponse(
        success=True,
        data=LeadResponse.model_validate(lead),
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
