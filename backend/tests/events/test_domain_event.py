import uuid

import pytest
from pydantic import ValidationError

from app.events.schemas.mission_events import MissionCreated


def test_event_carries_the_base_fields():
    aggregate_id = uuid.uuid4()
    event = MissionCreated(aggregate_id=aggregate_id, payload={"name": "Missão Verão"})

    assert event.event_name == "mission.created"
    assert event.aggregate_type == "mission"
    assert event.aggregate_id == aggregate_id
    assert event.payload == {"name": "Missão Verão"}
    assert event.metadata == {}
    assert event.occurred_at is not None
    assert isinstance(event.event_id, uuid.UUID)


def test_event_is_frozen():
    event = MissionCreated(aggregate_id=uuid.uuid4())

    with pytest.raises(ValidationError):
        event.payload = {"changed": True}


def test_event_name_and_aggregate_type_cannot_be_overridden_to_something_else():
    with pytest.raises(ValidationError):
        MissionCreated(aggregate_id=uuid.uuid4(), event_name="something.else")


def test_derive_metadata_keeps_correlation_forward_and_updates_causation():
    correlation_id = uuid.uuid4()
    trigger = MissionCreated(
        aggregate_id=uuid.uuid4(), metadata={"correlation_id": correlation_id}
    )

    derived = trigger.derive_metadata()

    assert derived["correlation_id"] == correlation_id
    assert derived["causation_id"] == trigger.event_id
