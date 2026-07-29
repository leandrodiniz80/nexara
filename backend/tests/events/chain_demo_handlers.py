"""Demonstration handlers proving the MissionCreated -> ... -> EmailSent chain works
end-to-end purely through EventBus.

These are NOT production wiring: MissionEngine/ResearchEngine/ProspectEngine don't
publish any of these events yet (that integration is future work). Each handler here
stands in for what a real one would eventually do, documented in its own docstring.
"""

import uuid

from app.events.handlers.event_handler import EventHandler
from app.events.publishers.event_publisher import EventPublisher
from app.events.schemas.domain_event import DomainEvent
from app.events.schemas.email_events import EmailApproved, EmailGenerated, EmailSent
from app.events.schemas.prospect_events import ProspectCreated
from app.events.schemas.research_events import ResearchCompleted, ResearchStarted
from app.events.schemas.workflow_events import WorkflowStarted


class ResearchStarterHandler(EventHandler):
    """MissionCreated -> ResearchStarted. A real version would call
    ResearchEngine.search_by_segment()/search_by_city() with the mission's own
    target_segment/target_city instead of just relaying the payload."""

    event_name = "mission.created"

    def __init__(self, publisher: EventPublisher) -> None:
        self.publisher = publisher

    async def handle(self, event: DomainEvent) -> None:
        await self.publisher.publish(
            ResearchStarted(
                aggregate_id=event.aggregate_id,
                payload={"strategy": "segment", "criteria": event.payload},
                metadata=event.derive_metadata(),
            )
        )


class ResearchCompletionHandler(EventHandler):
    """ResearchStarted -> ResearchCompleted. A real version would call
    ResearchEngine.remove_duplicates()/calculate_scores() and report the true counts;
    this simulates a finished run."""

    event_name = "research.started"

    def __init__(self, publisher: EventPublisher) -> None:
        self.publisher = publisher

    async def handle(self, event: DomainEvent) -> None:
        await self.publisher.publish(
            ResearchCompleted(
                aggregate_id=event.aggregate_id,
                payload={"results_found": 12, "duplicates_removed": 3, "average_score": 68},
                metadata=event.derive_metadata(),
            )
        )


class ProspectCreationHandler(EventHandler):
    """ResearchCompleted -> ProspectCreated. A real version would call
    ProspectEngine.create_prospect() once per qualifying ResearchResult; this
    simulates opening a single prospect."""

    event_name = "research.completed"

    def __init__(self, publisher: EventPublisher) -> None:
        self.publisher = publisher

    async def handle(self, event: DomainEvent) -> None:
        await self.publisher.publish(
            ProspectCreated(
                aggregate_id=uuid.uuid4(),
                payload={"mission_id": str(event.aggregate_id), "origin": "research"},
                metadata=event.derive_metadata(),
            )
        )


class WorkflowStarterHandler(EventHandler):
    """ProspectCreated -> WorkflowStarted: an outreach workflow kicking off for the
    new prospect."""

    event_name = "prospect.created"

    def __init__(self, publisher: EventPublisher) -> None:
        self.publisher = publisher

    async def handle(self, event: DomainEvent) -> None:
        await self.publisher.publish(
            WorkflowStarted(
                aggregate_id=uuid.uuid4(),
                payload={"workflow_name": "cold_outreach", "prospect_id": str(event.aggregate_id)},
                metadata=event.derive_metadata(),
            )
        )


class EmailGenerationHandler(EventHandler):
    """WorkflowStarted -> EmailGenerated. In the real platform this is where CopyAgent
    (via AIOrchestrator) would run — deliberately not called here: events/ knows
    nothing about ai/ either, same rule as every other module."""

    event_name = "workflow.started"

    def __init__(self, publisher: EventPublisher) -> None:
        self.publisher = publisher

    async def handle(self, event: DomainEvent) -> None:
        await self.publisher.publish(
            EmailGenerated(
                aggregate_id=event.aggregate_id,
                payload={"template_name": "cold_outreach_v1", "subject": "Uma ideia para sua empresa"},
                metadata=event.derive_metadata(),
            )
        )


class EmailApprovalHandler(EventHandler):
    """EmailGenerated -> EmailApproved. A real handler would wait on a human/
    ReviewAgent decision instead of approving unconditionally."""

    event_name = "email.generated"

    def __init__(self, publisher: EventPublisher) -> None:
        self.publisher = publisher

    async def handle(self, event: DomainEvent) -> None:
        await self.publisher.publish(
            EmailApproved(
                aggregate_id=event.aggregate_id,
                payload={"approved_by": "demo"},
                metadata=event.derive_metadata(),
            )
        )


class EmailSenderHandler(EventHandler):
    """EmailApproved -> EmailSent."""

    event_name = "email.approved"

    def __init__(self, publisher: EventPublisher) -> None:
        self.publisher = publisher

    async def handle(self, event: DomainEvent) -> None:
        await self.publisher.publish(
            EmailSent(
                aggregate_id=event.aggregate_id,
                payload={"provider": "demo"},
                metadata=event.derive_metadata(),
            )
        )


class EmailSentCollectorHandler(EventHandler):
    """Terminal handler of the demo chain — just records what it saw, so a test can
    assert the whole cascade actually reached the end."""

    event_name = "email.sent"

    def __init__(self) -> None:
        self.received: list[DomainEvent] = []

    async def handle(self, event: DomainEvent) -> None:
        self.received.append(event)
