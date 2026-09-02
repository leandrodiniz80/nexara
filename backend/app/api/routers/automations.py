import time
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_session
from app.api.dependencies.common import get_db, get_request_id
from app.api.responses.api_response import ApiResponse
from app.core.config import settings
from app.models.leads.lead_automation import LeadAutomation
from app.schemas.leads.lead_automation import LeadAutomationResponse, LeadAutomationUpdate
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

    stmt = select(LeadAutomation).where(
        LeadAutomation.organization_id == organization_id, LeadAutomation.deleted_at.is_(None)
    )
    result = await db.execute(stmt)
    automations = result.scalars().all()

    if not automations:
        # First time this organization ever asks for its automations — seed
        # the two defaults and re-query. seed_default_automations() is
        # ON-CONFLICT-safe (see its docstring), so this never duplicates
        # rows even if two requests race here for the same brand-new org.
        await seed_default_automations(db, organization_id)
        result = await db.execute(stmt)
        automations = result.scalars().all()

    return ApiResponse(
        success=True,
        data=[LeadAutomationResponse.model_validate(automation) for automation in automations],
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
