import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DomainEvent(BaseModel):
    """Base shape every domain event carries. Concrete events (MissionCreated,
    ResearchCompleted, ...) subclass this and override `event_name`/`aggregate_type`
    with their own fixed `Literal[...]` value, so the Python type and the serialized
    field always agree — that's what lets EventBus route purely on `event_name` as a
    string without needing to know the concrete class.

    Frozen: an event is a fact about something that already happened: it doesn't make
    sense to reassign its fields after construction. `frozen` only blocks that kind of
    reassignment though (`event.metadata = {...}` raises) — it does not deep-freeze
    `metadata`'s contents, and EventPublisher relies on that: it stamps the resolved
    correlation_id/trace_id into `metadata` in place right before dispatch, which is
    mutating the dict already stored in the field, not reassigning the field itself.

    Correlation convention: `metadata` isn't just a scratch pad — a handler emitting a
    follow-up event should carry `correlation_id`/`trace_id` forward and set
    `causation_id` to the triggering event's `event_id`. `derive_metadata()` does this
    for you; see EventPublisher for how the ids get into `metadata` in the first place.
    """

    model_config = ConfigDict(frozen=True)

    event_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    event_name: str
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    aggregate_type: str
    aggregate_id: uuid.UUID
    payload: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def derive_metadata(self) -> dict[str, Any]:
        """Metadata for an event caused by this one: correlation_id/trace_id (if any)
        keep flowing forward, causation_id is updated to point at this event."""
        return {**self.metadata, "causation_id": self.event_id}
