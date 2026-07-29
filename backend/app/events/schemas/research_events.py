from typing import Literal

from app.events.schemas.domain_event import DomainEvent


class ResearchStarted(DomainEvent):
    """Research Engine has no persisted aggregate of its own (no DB), so these events
    are reported against the Mission that requested the research — aggregate_id is a
    mission_id. Conventional payload: strategy ("city"/"segment"/"cnae"/"nearby"),
    criteria (the search parameters).
    """

    event_name: Literal["research.started"] = "research.started"
    aggregate_type: Literal["mission"] = "mission"


class ResearchCompleted(DomainEvent):
    """Conventional payload: results_found, duplicates_removed, average_score."""

    event_name: Literal["research.completed"] = "research.completed"
    aggregate_type: Literal["mission"] = "mission"


class ResearchFailed(DomainEvent):
    """Conventional payload: reason, source (which ResearchProvider failed)."""

    event_name: Literal["research.failed"] = "research.failed"
    aggregate_type: Literal["mission"] = "mission"
