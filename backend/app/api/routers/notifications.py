import time
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_session
from app.api.dependencies.common import get_db, get_request_id
from app.api.responses.api_response import ApiResponse
from app.core.config import settings
from app.models.notifications.user_notification import UserNotification
from app.schemas.notifications import NotificationListResponse, NotificationResponse

router = APIRouter(prefix=f"{settings.API_V1_PREFIX}/notifications", tags=["Notifications"])


def _require_caller(session: dict) -> tuple[str, str]:
    """Every route below is scoped to (organization_id, user_email) — a
    notification belongs to one specific person, not just one tenant."""
    organization_id = session.get("organization_id")
    if organization_id is None:
        raise HTTPException(status_code=403, detail="Your account isn't part of an organization")

    user_email = session.get("email")
    if user_email is None:
        raise HTTPException(status_code=403, detail="Your session has no email on record")

    return organization_id, user_email


@router.get("", response_model=ApiResponse[NotificationListResponse])
async def list_notifications(
    limit: int = Query(default=20, ge=1, le=100),
    request_id: str = Depends(get_request_id),
    session: dict = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[NotificationListResponse]:
    start = time.perf_counter()
    organization_id, user_email = _require_caller(session)

    stmt = (
        select(UserNotification)
        .where(
            UserNotification.organization_id == organization_id,
            UserNotification.user_email == user_email,
        )
        .order_by(UserNotification.created_at.desc())
        .limit(limit)
    )
    notifications = (await db.execute(stmt)).scalars().all()

    # A separate COUNT(*), not len(notifications) — the list above is
    # capped at `limit`, so counting the page itself would undercount
    # whenever unread notifications outnumber it.
    unread_stmt = select(func.count(UserNotification.id)).where(
        UserNotification.organization_id == organization_id,
        UserNotification.user_email == user_email,
        UserNotification.read.is_(False),
    )
    unread_count = (await db.execute(unread_stmt)).scalar_one()

    return ApiResponse(
        success=True,
        data=NotificationListResponse(
            data=[NotificationResponse.model_validate(n) for n in notifications],
            unread_count=unread_count,
        ),
        request_id=request_id,
        execution_time=time.perf_counter() - start,
    )


@router.patch("/{notification_id}/read", response_model=ApiResponse[NotificationResponse])
async def mark_notification_read(
    notification_id: uuid.UUID,
    request_id: str = Depends(get_request_id),
    session: dict = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[NotificationResponse]:
    start = time.perf_counter()
    organization_id, user_email = _require_caller(session)

    notification = await db.get(UserNotification, notification_id)
    if (
        notification is None
        or notification.organization_id != organization_id
        or notification.user_email != user_email
    ):
        raise HTTPException(status_code=404, detail="Notification not found")

    notification.read = True
    await db.commit()
    await db.refresh(notification)

    return ApiResponse(
        success=True,
        data=NotificationResponse.model_validate(notification),
        request_id=request_id,
        execution_time=time.perf_counter() - start,
    )
