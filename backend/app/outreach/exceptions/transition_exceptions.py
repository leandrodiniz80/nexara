import uuid

from app.outreach.exceptions.base import OutreachError
from app.outreach.models.enums import MessageStatus


class InvalidMessageTransitionError(OutreachError):
    """Raised when an ApprovalService/OutreachEngine lifecycle method is called from a
    MessageStatus it doesn't allow (e.g. approve() on an asset that isn't
    PENDING_APPROVAL)."""

    def __init__(self, asset_id: uuid.UUID, current_status: MessageStatus, action: str) -> None:
        self.asset_id = asset_id
        self.current_status = current_status
        self.action = action
        super().__init__(f"Cannot {action} asset {asset_id}: it is '{current_status.value}'.")
