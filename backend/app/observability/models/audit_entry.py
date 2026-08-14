import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AuditEntry(BaseModel):
    """One historical fact: who did what to which entity, and when. Frozen — an
    audit trail is append-only by definition; nothing here is ever mutated after
    creation, the same convention as MissionEvent/JobExecutionLog/AIExecutionLog.

    `entity_type`/`action` are free strings (open vocabularies — "mission"/
    "created", "asset"/"approved", and so on) rather than closed enums, since this
    module has no opinion on the full set of entities/actions the rest of the
    platform might ever want audited.
    """

    model_config = ConfigDict(frozen=True)

    entity_type: str
    entity_id: uuid.UUID
    action: str
    performed_by: uuid.UUID | None = None
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)
