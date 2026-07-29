from typing import Literal

from app.events.schemas.domain_event import DomainEvent


class MissionCreated(DomainEvent):
    """Conventional payload: name, objective, target_segment, target_city, target_state."""

    event_name: Literal["mission.created"] = "mission.created"
    aggregate_type: Literal["mission"] = "mission"


class MissionStarted(DomainEvent):
    """Conventional payload: started_at."""

    event_name: Literal["mission.started"] = "mission.started"
    aggregate_type: Literal["mission"] = "mission"


class MissionFinished(DomainEvent):
    """Conventional payload: finished_at, progress, contracts, won_value."""

    event_name: Literal["mission.finished"] = "mission.finished"
    aggregate_type: Literal["mission"] = "mission"


class MissionCancelled(DomainEvent):
    """Conventional payload: reason."""

    event_name: Literal["mission.cancelled"] = "mission.cancelled"
    aggregate_type: Literal["mission"] = "mission"
