import time
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_session
from app.api.dependencies.common import get_db, get_request_id
from app.api.responses.api_response import ApiResponse
from app.core.config import settings
from app.models.leads.automation_activity_log import AutomationActivityLog
from app.models.leads.lead_automation import LeadAutomation
from app.schemas.leads.lead_automation import (
    AutomationActivityEntry,
    LeadAutomationResponse,
    LeadAutomationUpdate,
)
from app.services.leads.automation_engine import seed_default_automations

router = APIRouter(prefix=f"{settings.API_V1_PREFIX}/automations", tags=["Automations"])


def _require_organization(session: dict) -> str:
    organization_id = session.get("organization_id")
    if organization_id is None:
        raise HTTPException(status_code=403, detail="Your account isn't part of an organization")
    return organization_id


@router.get("", response_model=ApiResponse[list[LeadAutomationResponse]])
async def list_automations(
    request_id: str = Depends(get_request_id),
    session: dict = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[list[LeadAutomationResponse]]:
    start = time.perf_counter()
    organization_id = _require_organization(session)

    # Idempotent (ON CONFLICT DO NOTHING against organization_id+name) — safe
    # to run on every call. This is what backfills a newly added default
    # automation (e.g. "Lead Created Notification") for organizations that
    # already had the older ones, not just brand-new orgs.
    await seed_default_automations(db, organization_id)

    stmt = select(LeadAutomation).where(
        LeadAutomation.organization_id == organization_id, LeadAutomation.deleted_at.is_(None)
    )
    result = await db.execute(stmt)
    automations = result.scalars().all()

    return ApiResponse(
        success=True,
        data=[LeadAutomationResponse.model_validate(automation) for automation in automations],
        request_id=request_id,
        execution_time=time.perf_counter() - start,
    )


@router.get("/activity", response_model=ApiResponse[list[AutomationActivityEntry]])
async def get_automation_activity(
    limit: int = Query(default=50, ge=1, le=200),
    request_id: str = Depends(get_request_id),
    session: dict = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[list[AutomationActivityEntry]]:
    start = time.perf_counter()
    organization_id = _require_organization(session)

    stmt = (
        select(AutomationActivityLog)
        .where(AutomationActivityLog.organization_id == organization_id)
        .order_by(AutomationActivityLog.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    entries = result.scalars().all()

    return ApiResponse(
        success=True,
        data=[AutomationActivityEntry.model_validate(entry) for entry in entries],
        request_id=request_id,
        execution_time=time.perf_counter() - start,
    )


@router.patch("/{automation_id}", response_model=ApiResponse[LeadAutomationResponse])
async def update_automation(
    automation_id: uuid.UUID,
    body: LeadAutomationUpdate,
    request_id: str = Depends(get_request_id),
    session: dict = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[LeadAutomationResponse]:
    start = time.perf_counter()
    organization_id = _require_organization(session)

    automation = await db.get(LeadAutomation, automation_id)
    if automation is None or automation.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Automation not found")

    automation.active = body.active
    await db.commit()
    await db.refresh(automation)

    return ApiResponse(
        success=True,
        data=LeadAutomationResponse.model_validate(automation),
        request_id=request_id,
        execution_time=time.perf_counter() - start,
    )
