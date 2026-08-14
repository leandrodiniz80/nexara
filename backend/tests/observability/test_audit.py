import uuid

import pytest

from app.observability.audit.audit_builder import AuditBuilder
from app.observability.audit.audit_service import AuditService
from app.observability.repositories.observability_repository import ObservabilityRepository


def test_audit_builder_builds_a_frozen_entry():
    entity_id = uuid.uuid4()

    entry = AuditBuilder.build(entity_type="mission", entity_id=entity_id, action="created")

    assert entry.entity_type == "mission"
    assert entry.entity_id == entity_id
    assert entry.action == "created"
    assert entry.metadata == {}
    with pytest.raises(Exception):
        entry.action = "changed"  # frozen — must not allow mutation


def test_audit_service_record_persists_through_the_repository():
    repository = ObservabilityRepository()
    service = AuditService(repository)
    mission_id = uuid.uuid4()

    service.record(entity_type="mission", entity_id=mission_id, action="created")

    entries = repository.list_audit_entries_by_entity("mission", mission_id)
    assert len(entries) == 1


@pytest.mark.parametrize(
    "method_name,entity_type,action",
    [
        ("mission_created", "mission", "created"),
        ("mission_paused", "mission", "paused"),
        ("mission_resumed", "mission", "resumed"),
        ("mission_cancelled", "mission", "cancelled"),
        ("prospect_created", "prospect", "created"),
        ("asset_generated", "asset", "generated"),
        ("asset_approved", "asset", "approved"),
        ("asset_rejected", "asset", "rejected"),
        ("job_started", "job", "started"),
        ("job_completed", "job", "completed"),
        ("task_executed", "task", "executed"),
    ],
)
def test_every_convenience_method_records_the_right_entity_type_and_action(
    method_name, entity_type, action
):
    repository = ObservabilityRepository()
    service = AuditService(repository)
    entity_id = uuid.uuid4()

    entry = getattr(service, method_name)(entity_id)

    assert entry.entity_type == entity_type
    assert entry.action == action
    assert entry.entity_id == entity_id


def test_convenience_methods_accept_performed_by_and_metadata():
    repository = ObservabilityRepository()
    service = AuditService(repository)
    mission_id = uuid.uuid4()
    performed_by = uuid.uuid4()

    entry = service.mission_paused(
        mission_id, performed_by=performed_by, metadata={"reason": "cliente pediu"}
    )

    assert entry.performed_by == performed_by
    assert entry.metadata == {"reason": "cliente pediu"}


def test_build_timeline_returns_entries_in_order_for_one_entity():
    repository = ObservabilityRepository()
    service = AuditService(repository)
    mission_id = uuid.uuid4()
    other_mission_id = uuid.uuid4()

    service.mission_created(mission_id)
    service.mission_paused(mission_id)
    service.mission_created(other_mission_id)

    timeline = service.build_timeline("mission", mission_id)

    assert timeline.entity_id == mission_id
    assert [entry.action for entry in timeline.entries] == ["created", "paused"]
