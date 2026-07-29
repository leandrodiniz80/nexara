from typing import Literal

from app.events.schemas.domain_event import DomainEvent


class ProspectCreated(DomainEvent):
    """Conventional payload: company_id, campaign_id, mission_id, origin."""

    event_name: Literal["prospect.created"] = "prospect.created"
    aggregate_type: Literal["prospect"] = "prospect"


class ProspectQualified(DomainEvent):
    """Conventional payload: qualified_at, score."""

    event_name: Literal["prospect.qualified"] = "prospect.qualified"
    aggregate_type: Literal["prospect"] = "prospect"


class ProspectConverted(DomainEvent):
    """Fired on ProspectEngine.mark_as_won(). Conventional payload: converted_at, estimated_value."""

    event_name: Literal["prospect.converted"] = "prospect.converted"
    aggregate_type: Literal["prospect"] = "prospect"
