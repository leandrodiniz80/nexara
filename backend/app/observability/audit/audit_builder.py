import uuid
from datetime import datetime, timezone
from typing import Any

from app.observability.models.audit_entry import AuditEntry


class AuditBuilder:
    """Deterministic construction of AuditEntry — a pure function of its inputs
    (aside from the timestamp it stamps when the caller doesn't supply one)."""

    @staticmethod
    def build(
        *,
        entity_type: str,
        entity_id: uuid.UUID,
        action: str,
        performed_by: uuid.UUID | None = None,
        metadata: dict[str, Any] | None = None,
        occurred_at: datetime | None = None,
    ) -> AuditEntry:
        return AuditEntry(
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            performed_by=performed_by,
            occurred_at=occurred_at or datetime.now(timezone.utc),
            metadata=metadata or {},
        )
