import uuid
from datetime import datetime, timezone

from app.outreach.exceptions.transition_exceptions import InvalidMessageTransitionError
from app.outreach.models.enums import MessageStatus
from app.outreach.models.outreach_asset import OutreachAsset


class ApprovalService:
    """Owns the approval state machine for an OutreachAsset — any commercial asset,
    not just a written message:
    DRAFT -> submit() -> PENDING_APPROVAL -> approve() -> APPROVED
                                           -> reject()  -> REJECTED -> reopen() -> DRAFT
    """

    @staticmethod
    def _ensure_status(asset: OutreachAsset, allowed: set[MessageStatus], action: str) -> None:
        if asset.status not in allowed:
            raise InvalidMessageTransitionError(asset.id, asset.status, action)

    def submit(self, asset: OutreachAsset) -> OutreachAsset:
        self._ensure_status(asset, {MessageStatus.DRAFT}, "submit")
        asset.status = MessageStatus.PENDING_APPROVAL
        return asset

    def approve(
        self, asset: OutreachAsset, *, approved_by: uuid.UUID | None = None
    ) -> OutreachAsset:
        self._ensure_status(asset, {MessageStatus.PENDING_APPROVAL}, "approve")
        asset.status = MessageStatus.APPROVED
        asset.approved_at = datetime.now(timezone.utc)
        asset.approved_by = approved_by
        return asset

    def reject(self, asset: OutreachAsset, *, reason: str | None = None) -> OutreachAsset:
        """`reason` isn't stored on OutreachAsset (no such field in the spec) — it
        exists only so a caller can pass one through to its own logging without this
        service silently discarding it earlier in the call chain."""
        self._ensure_status(asset, {MessageStatus.PENDING_APPROVAL}, "reject")
        asset.status = MessageStatus.REJECTED
        return asset

    def reopen(self, asset: OutreachAsset) -> OutreachAsset:
        self._ensure_status(asset, {MessageStatus.REJECTED}, "reopen")
        asset.status = MessageStatus.DRAFT
        asset.approved_at = None
        asset.approved_by = None
        return asset
