import uuid

from pydantic import BaseModel, Field

from app.observability.models.audit_entry import AuditEntry


class AuditTimeline(BaseModel):
    """Every AuditEntry recorded for one entity, in occurrence order — "what
    happened to this Mission/Prospect/Asset over its whole lifetime"."""

    entity_type: str
    entity_id: uuid.UUID
    entries: list[AuditEntry] = Field(default_factory=list)
