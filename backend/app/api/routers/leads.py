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
from app.models.leads.automation_activity_log import AutomationActivityLog
from app.models.leads.lead import Lead
from app.models.leads.lead_activity_log import LeadActivityLog
from app.models.leads.lead_status_history import LeadStatusHistory
from app.models.platform_auth.user import PlatformUser
from app.models.platform_auth.user_organization import PlatformUserOrganization
from app.schemas.leads.lead import (
    LeadActivityFeedEntry,
    LeadCreate,
    LeadCreateResponse,
    LeadListResponse,
    LeadMetricsByStatus,
    LeadMetricsResponse,
    LeadResponse,
    LeadStatusUpdateResponse,
    LeadTaskCompleteResponse,
    LeadTimelineEntry,
    LeadUpdateStatus,
    UpdateLeadDetailsRequest,
    UpdateLeadOwnerRequest,
)
from app.services.leads.automation_engine import fire_stale_lead_automations, run_automations
from app.services.leads.scoring import score_leads

logger = logging.getLogger("app.api.routers.leads")

router = APIRouter(prefix=f"{settings.API_V1_PREFIX}/leads", tags=["Leads"])


def _describe_details_update(updates: dict) -> str:
    """Builds a human-readable message for the LeadActivityLog row PATCH
    /leads/{id}/details writes — the frontend autosaves one field per blur,
    so `updates` normally has exactly one key, but this handles more than
    one gracefully too."""
    parts = []
    if "notes" in updates:
        parts.append("Notes updated")
    if "next_action" in updates:
        parts.append(
            f"Next action set: {updates['next_action']}" if updates["next_action"] else "Next action cleared"
        )
    if "next_action_due_at" in updates:
        parts.append("Due date updated")
    return "; ".join(parts) if parts else "Lead details updated"


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
    leads = await score_leads(db, result.scalars().all())

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
    stale_leads = result.scalars().all()

    # Opportunistic "lead_stale" firing — no cron: piggybacks on this
    # existing, already-computed stale-leads query, evaluated whenever a
    # caller asks (typically the dashboard). Same dedup/firing logic
    # POST /internal/jobs/check-stale-leads uses for its cross-org sweep —
    # see fire_stale_lead_automations()'s own docstring.
    if await fire_stale_lead_automations(db, stale_leads, cutoff):
        await db.commit()

    leads = await score_leads(db, stale_leads)

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
    leads = await score_leads(db, result.scalars().all())

    return ApiResponse(
        success=True,
        data=leads,
        request_id=request_id,
        execution_time=time.perf_counter() - start,
    )


@router.get("/priority", response_model=ApiResponse[list[LeadResponse]])
async def get_leads_priority(
    limit: int = Query(default=10, ge=1, le=50),
    request_id: str = Depends(get_request_id),
    session: dict = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[list[LeadResponse]]:
    """"Foco do dia" — leads in the worst situation right now: soonest
    overdue/due task first, then (among leads with no next_action at all,
    where due date can't rank them) the lowest computed score. Score is
    computed dynamically, not stored, so the final ranking can't be done in
    SQL alone: fetches a generous candidate pool via the one ordering SQL
    *can* express (next_action_due_at ASC NULLS LAST, backed by
    ix_leads_org_id_next_action_due_at), scores that whole pool in one
    extra query (score_leads), then re-sorts by the true composite order
    before slicing to `limit`. 200 is comfortably above any realistic
    per-org lead count at this product stage; revisit if that stops being
    true."""
    start = time.perf_counter()
    organization_id = _require_organization(session)

    candidate_pool_stmt = (
        select(Lead)
        .where(
            Lead.organization_id == organization_id,
            Lead.deleted_at.is_(None),
            Lead.status != "converted",
        )
        .order_by(Lead.next_action_due_at.asc().nulls_last())
        .limit(200)
    )
    result = await db.execute(candidate_pool_stmt)
    candidates = result.scalars().all()

    scored = await score_leads(db, candidates)
    scored.sort(
        key=lambda response: (
            response.next_action_due_at is None,
            response.next_action_due_at,
            response.score,
        )
    )
    leads = scored[:limit]

    return ApiResponse(
        success=True,
        data=leads,
        request_id=request_id,
        execution_time=time.perf_counter() - start,
    )


@router.get("/activity", response_model=ApiResponse[list[LeadActivityFeedEntry]])
async def get_leads_activity_feed(
    limit: int = Query(default=50, ge=1, le=200),
    request_id: str = Depends(get_request_id),
    session: dict = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[list[LeadActivityFeedEntry]]:
    """Org-wide counterpart to GET /leads/{id}/timeline — same three
    sources (LeadStatusHistory, AutomationActivityLog, LeadActivityLog),
    merged across every lead in the organization instead of just one. Backs
    the dashboard's Recent Activity card."""
    start = time.perf_counter()
    organization_id = _require_organization(session)

    status_stmt = (
        select(LeadStatusHistory, Lead.name)
        .join(Lead, Lead.id == LeadStatusHistory.lead_id)
        .where(LeadStatusHistory.organization_id == organization_id)
        .order_by(LeadStatusHistory.created_at.desc())
        .limit(limit)
    )
    automation_stmt = (
        select(AutomationActivityLog)
        .where(AutomationActivityLog.organization_id == organization_id)
        .order_by(AutomationActivityLog.created_at.desc())
        .limit(limit)
    )
    activity_stmt = (
        select(LeadActivityLog)
        .where(LeadActivityLog.organization_id == organization_id)
        .order_by(LeadActivityLog.created_at.desc())
        .limit(limit)
    )

    status_rows = (await db.execute(status_stmt)).all()
    automation_rows = (await db.execute(automation_stmt)).scalars().all()
    activity_rows = (await db.execute(activity_stmt)).scalars().all()

    entries = (
        [
            LeadActivityFeedEntry(
                lead_id=history.lead_id,
                lead_name=lead_name,
                type="status_changed",
                message=(
                    f"Status changed from {history.from_status} to {history.to_status}"
                    if history.from_status
                    else f"Status set to {history.to_status}"
                ),
                created_at=history.created_at,
            )
            for history, lead_name in status_rows
        ]
        + [
            LeadActivityFeedEntry(
                lead_id=row.lead_id,
                lead_name=row.lead_name,
                type="automation_fired",
                message=f"{row.automation_name} — {row.message}",
                created_at=row.created_at,
            )
            for row in automation_rows
        ]
        + [
            LeadActivityFeedEntry(
                lead_id=row.lead_id,
                lead_name=row.lead_name,
                type=row.event_type,
                message=row.message,
                created_at=row.created_at,
            )
            for row in activity_rows
        ]
    )
    entries.sort(key=lambda entry: entry.created_at, reverse=True)
    entries = entries[:limit]

    return ApiResponse(
        success=True,
        data=entries,
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

    (scored_lead,) = await score_leads(db, [lead])

    return ApiResponse(
        success=True,
        data=LeadCreateResponse(lead=scored_lead, notifications=notifications),
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
    """Single source of truth for everything that's happened to this lead:
    status changes (LeadStatusHistory), automation firings
    (AutomationActivityLog), and owner/notes/next_action/task-completion
    events (LeadActivityLog) — merged and re-sorted by created_at DESC.
    Fetching top-`limit` from each source before merging is sufficient for a
    correct overall top-`limit`: any entry outside a source's own top-`limit`
    can't be in the global top-`limit` either, since limit-1 entries from
    that same source already outrank it."""
    start = time.perf_counter()
    organization_id = _require_organization(session)

    # Same ownership check as update_lead_status — a guessed lead_id from
    # another org 404s instead of returning an empty (ambiguous) timeline.
    lead = await db.get(Lead, lead_id)
    if lead is None or lead.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Lead not found")

    status_stmt = (
        select(LeadStatusHistory)
        .where(LeadStatusHistory.lead_id == lead_id, LeadStatusHistory.organization_id == organization_id)
        .order_by(LeadStatusHistory.created_at.desc())
        .limit(limit)
    )
    automation_stmt = (
        select(AutomationActivityLog)
        .where(AutomationActivityLog.lead_id == lead_id, AutomationActivityLog.organization_id == organization_id)
        .order_by(AutomationActivityLog.created_at.desc())
        .limit(limit)
    )
    activity_stmt = (
        select(LeadActivityLog)
        .where(LeadActivityLog.lead_id == lead_id, LeadActivityLog.organization_id == organization_id)
        .order_by(LeadActivityLog.created_at.desc())
        .limit(limit)
    )

    status_rows = (await db.execute(status_stmt)).scalars().all()
    automation_rows = (await db.execute(automation_stmt)).scalars().all()
    activity_rows = (await db.execute(activity_stmt)).scalars().all()

    entries = (
        [
            LeadTimelineEntry(
                type="status_changed",
                from_=row.from_status,
                to=row.to_status,
                created_at=row.created_at,
            )
            for row in status_rows
        ]
        + [
            LeadTimelineEntry(
                type="automation_fired",
                message=f"{row.automation_name} — {row.message}",
                created_at=row.created_at,
            )
            for row in automation_rows
        ]
        + [
            LeadTimelineEntry(
                type=row.event_type,
                message=row.message,
                created_at=row.created_at,
            )
            for row in activity_rows
        ]
    )
    entries.sort(key=lambda entry: entry.created_at, reverse=True)
    entries = entries[:limit]

    return ApiResponse(
        success=True,
        data=entries,
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

    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(lead, field, value)

    if updates:
        db.add(
            LeadActivityLog(
                organization_id=organization_id,
                lead_id=lead.id,
                lead_name=lead.name,
                event_type="details_updated",
                message=_describe_details_update(updates),
                user_email=session.get("email"),
            )
        )

    await db.commit()
    await db.refresh(lead)

    (scored_lead,) = await score_leads(db, [lead])

    return ApiResponse(
        success=True,
        data=scored_lead,
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
    db.add(
        LeadActivityLog(
            organization_id=organization_id,
            lead_id=lead.id,
            lead_name=lead.name,
            event_type="owner_changed",
            message=(
                f"Owner changed to {body.owner_email}" if body.owner_email else "Owner unassigned"
            ),
            user_email=session.get("email"),
        )
    )
    await db.commit()
    await db.refresh(lead)

    (scored_lead,) = await score_leads(db, [lead])

    return ApiResponse(
        success=True,
        data=scored_lead,
        request_id=request_id,
        execution_time=time.perf_counter() - start,
    )


@router.post("/{lead_id}/complete-task", response_model=ApiResponse[LeadTaskCompleteResponse])
async def complete_lead_task(
    lead_id: uuid.UUID,
    request_id: str = Depends(get_request_id),
    session: dict = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[LeadTaskCompleteResponse]:
    """Marks the lead's current next_action done: logs it to LeadActivityLog
    (captured before clearing, so the timeline still shows what was
    completed), then clears next_action/next_action_due_at. No automation
    fires from this event today — notifications is always [], kept for
    response-shape consistency with the other lead mutation endpoints.

    Workday mode: if the caller is the one who currently has this lead in
    focus, this is also what ends that focus session — in_focus/focused_at/
    focused_by_email clear, and the elapsed time since focused_at is
    recorded on the activity log entry as duration_seconds. Completing a
    lead nobody has in focus (the normal, non-workday path) behaves exactly
    as before: duration_seconds stays null."""
    start = time.perf_counter()
    organization_id = _require_organization(session)
    user_email = session.get("email")

    lead = await db.get(Lead, lead_id)
    if lead is None or lead.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Lead not found")

    if lead.next_action is None:
        raise HTTPException(status_code=400, detail="This lead has no next action to complete")

    duration_seconds = None
    if lead.in_focus and lead.focused_by_email == user_email and lead.focused_at is not None:
        duration_seconds = int((datetime.now(timezone.utc) - lead.focused_at).total_seconds())
        lead.in_focus = False
        lead.focused_at = None
        lead.focused_by_email = None

    db.add(
        LeadActivityLog(
            organization_id=organization_id,
            lead_id=lead.id,
            lead_name=lead.name,
            event_type="task_completed",
            message=f"Completed: {lead.next_action}",
            user_email=user_email,
            duration_seconds=duration_seconds,
        )
    )
    lead.next_action = None
    lead.next_action_due_at = None

    await db.commit()
    await db.refresh(lead)

    (scored_lead,) = await score_leads(db, [lead])

    return ApiResponse(
        success=True,
        data=LeadTaskCompleteResponse(lead=scored_lead, notifications=[]),
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

    # A converted lead can't stay anyone's workday focus — GET /workday/next
    # already treats "converted" as resolved and would clear this lazily on
    # its own next call, but clearing it here too means the lock frees up
    # immediately rather than sitting stale until someone happens to ask.
    if lead.status == "converted" and lead.in_focus:
        lead.in_focus = False
        lead.focused_at = None
        lead.focused_by_email = None

    await db.commit()
    await db.refresh(lead)

    logger.info(
        "Lead status changed: %s %s -> %s (org=%s)",
        lead.id,
        from_status,
        lead.status,
        organization_id,
    )

    (scored_lead,) = await score_leads(db, [lead])

    return ApiResponse(
        success=True,
        data=LeadStatusUpdateResponse(lead=scored_lead, notifications=notifications),
        request_id=request_id,
        execution_time=time.perf_counter() - start,
    )
