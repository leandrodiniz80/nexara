import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from app.outreach.models.enums import AssetType, Channel, MessageStatus


class OutreachAsset(BaseModel):
    """One generated commercial asset for one prospect — an email, a WhatsApp
    message, a proposal, a call script, a video, whatever `asset_type` says it is.
    This is the generalization of the old GeneratedMessage: the system no longer
    assumes every asset is a written message.

    `prospect_id`/`template_id` are kept from the previous entity (not in Sprint 09's
    explicit field list) because behavior must not change: the repository still needs
    to look assets up by prospect, and OutreachEngine still needs to re-fetch the
    originating AssetTemplate to validate. `prospect_id` stays opaque (a bare UUID,
    not a Prospect reference) for the same module-decoupling reason as before.

    `title`/`content` replace `subject`/`body` — generic names that make sense for a
    PDF proposal or a video script, not just an email. `metadata` replaces
    `rendered_variables`: a free-form dict, since a video or PDF asset carries very
    different generation data than an email's placeholder values.

    `generated_by` records which AssetGenerator implementation produced this asset
    (e.g. "AssetRenderer" today, "CopyAgentGenerator" once that exists) — the
    traceability hook a future AI-generated-content audit would need.

    Mutable on purpose: ApprovalService/OutreachEngine update the same instance in
    place as it moves through MessageStatus.
    """

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    prospect_id: uuid.UUID
    template_id: uuid.UUID
    asset_type: AssetType
    channel: Channel | None = None
    status: MessageStatus = MessageStatus.DRAFT
    title: str | None = None
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    approved_at: datetime | None = None
    approved_by: uuid.UUID | None = None
    generated_by: str | None = None
    version: int = 1
