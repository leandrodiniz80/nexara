import time
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_session, get_platform_container
from app.api.dependencies.common import get_db, get_request_id
from app.api.responses.api_response import ApiResponse
from app.core.config import settings
from app.models.leads.lead import Lead
from app.platform.bootstrap.platform_container import PlatformContainer
from app.services.leads.automation_engine import fire_stale_lead_automations

router = APIRouter(prefix=f"{settings.API_V1_PREFIX}/internal/jobs", tags=["Internal Jobs"])


def _require_admin(session: dict, container: PlatformContainer) -> str:
    """Same check and same rationale as cdn.py's own _require_admin: a
    self-registered account can't reach role=="admin" once any admin
    already exists on the platform, so trusting it here is safe. Needed
    because this endpoint, unlike every tenant-scoped one elsewhere in this
    codebase, spans every organization at once — the same class of access
    as cdn.py's role=="admin" platform-wide metrics views."""
    role = container.auth().get_user_role(session["email"])
    if role != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")
    return role


class CheckStaleLeadsResult(BaseModel):
    checked: int
    notified: int


@router.post("/check-stale-leads", response_model=ApiResponse[CheckStaleLeadsResult])
async def check_stale_leads(
    stale_after_days: int = Query(default=3, ge=1, le=90),
    request_id: str = Depends(get_request_id),
    session: dict = Depends(get_current_session),
    container: PlatformContainer = Depends(get_platform_container),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[CheckStaleLeadsResult]:
    """Manually-triggered stand-in for a future scheduled job — no cron
    infrastructure exists yet, so this is called by hand (or by whatever
    external scheduler is wired up later) rather than firing on its own.
    Sweeps every organization's contacted, stale leads and fires
    "lead_stale" — the exact same dedup/firing logic GET /leads/attention
    already uses per-org (fire_stale_lead_automations()), just without
    requiring someone to open that endpoint first. When a real scheduler
    lands, it can call this endpoint as-is; nothing here needs to change.
    """
    start = time.perf_counter()
    _require_admin(session, container)

    cutoff = datetime.now(timezone.utc) - timedelta(days=stale_after_days)
    stmt = select(Lead).where(
        Lead.deleted_at.is_(None),
        Lead.status == "contacted",
        Lead.updated_at < cutoff,
    )
    stale_leads = (await db.execute(stmt)).scalars().all()

    notified = await fire_stale_lead_automations(db, stale_leads, cutoff)
    await db.commit()

    return ApiResponse(
        success=True,
        data=CheckStaleLeadsResult(checked=len(stale_leads), notified=notified),
        request_id=request_id,
        execution_time=time.perf_counter() - start,
    )
