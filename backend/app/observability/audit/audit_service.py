import uuid
from typing import Any

from app.observability.audit.audit_builder import AuditBuilder
from app.observability.models.audit_entry import AuditEntry
from app.observability.repositories.observability_repository import ObservabilityRepository
from app.observability.schemas.audit_timeline import AuditTimeline


class AuditService:
    """Records what happened to an entity and can play its history back as an
    AuditTimeline. The eleven named methods below are convenience wrappers over
    `record()` for the specific events this sprint was asked to cover — each is
    just a fixed (entity_type, action) pair, no logic beyond that.
    """

    def __init__(
        self, repository: ObservabilityRepository, builder: AuditBuilder | None = None
    ) -> None:
        self.repository = repository
        self.builder = builder or AuditBuilder()

    def record(
        self,
        *,
        entity_type: str,
        entity_id: uuid.UUID,
        action: str,
        performed_by: uuid.UUID | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AuditEntry:
        entry = self.builder.build(
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            performed_by=performed_by,
            metadata=metadata,
        )
        return self.repository.save_audit_entry(entry)

    def mission_created(self, mission_id: uuid.UUID, **kwargs: Any) -> AuditEntry:
        return self.record(entity_type="mission", entity_id=mission_id, action="created", **kwargs)

    def mission_paused(self, mission_id: uuid.UUID, **kwargs: Any) -> AuditEntry:
        return self.record(entity_type="mission", entity_id=mission_id, action="paused", **kwargs)

    def mission_resumed(self, mission_id: uuid.UUID, **kwargs: Any) -> AuditEntry:
        return self.record(entity_type="mission", entity_id=mission_id, action="resumed", **kwargs)

    def mission_cancelled(self, mission_id: uuid.UUID, **kwargs: Any) -> AuditEntry:
        return self.record(
            entity_type="mission", entity_id=mission_id, action="cancelled", **kwargs
        )

    def prospect_created(self, prospect_id: uuid.UUID, **kwargs: Any) -> AuditEntry:
        return self.record(
            entity_type="prospect", entity_id=prospect_id, action="created", **kwargs
        )

    def asset_generated(self, asset_id: uuid.UUID, **kwargs: Any) -> AuditEntry:
        return self.record(entity_type="asset", entity_id=asset_id, action="generated", **kwargs)

    def asset_approved(self, asset_id: uuid.UUID, **kwargs: Any) -> AuditEntry:
        return self.record(entity_type="asset", entity_id=asset_id, action="approved", **kwargs)

    def asset_rejected(self, asset_id: uuid.UUID, **kwargs: Any) -> AuditEntry:
        return self.record(entity_type="asset", entity_id=asset_id, action="rejected", **kwargs)

    def job_started(self, job_id: uuid.UUID, **kwargs: Any) -> AuditEntry:
        return self.record(entity_type="job", entity_id=job_id, action="started", **kwargs)

    def job_completed(self, job_id: uuid.UUID, **kwargs: Any) -> AuditEntry:
        return self.record(entity_type="job", entity_id=job_id, action="completed", **kwargs)

    def task_executed(self, task_id: uuid.UUID, **kwargs: Any) -> AuditEntry:
        return self.record(entity_type="task", entity_id=task_id, action="executed", **kwargs)

    def build_timeline(self, entity_type: str, entity_id: uuid.UUID) -> AuditTimeline:
        entries = self.repository.list_audit_entries_by_entity(entity_type, entity_id)
        return AuditTimeline(entity_type=entity_type, entity_id=entity_id, entries=entries)
